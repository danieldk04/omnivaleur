"""
Core crosslisting orchestration.
Handles: publish to multiple platforms, auto-delist on sale.
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
import uuid

from backend.database import execute_with_retry, get_db
from backend.platforms import get_platform

_ENGLISH_PLATFORMS = {"vinted", "shopify", "ebay", "etsy"}
# marktplaats/2dehands require Dutch — user now enters English, so translate EN→NL.
_DUTCH_PLATFORMS: set[str] = {"marktplaats", "2dehands"}

logger = logging.getLogger(__name__)

# Hoe lang een geclaimde publicatieopdracht zonder teken van leven nog als "echt
# bezig" telt. Klikt de gebruiker binnen die tijd nóg eens op publiceren, dan is
# de extensie waarschijnlijk gewoon aan het werk; daarna niet meer.
STALE_CLAIM_SECONDS = 60


def _strip_text_tags(result: str) -> str:
    """
    Haal de <text>-omhulling weg die het model soms meeteruggeeft.

    De vertaalopdracht zet de brontekst tussen <text>…</text>. Het model kopieert
    die tags af en toe mee, en dan stond er letterlijk "<text>B'TWIN short-sleeve
    cycling set …</text>" in de advertentie op Vinted. Alleen de buitenste
    omhulling weghalen — tekens < en > midden in een beschrijving (maten,
    pijltjes) blijven staan.
    """
    s = (result or "").strip()
    if not s:
        return ""
    s = re.sub(r"^<\s*text\s*>", "", s, flags=re.I).strip()
    s = re.sub(r"<\s*/\s*text\s*>\s*$", "", s, flags=re.I).strip()
    return s


def _republish_job_update(open_job: dict, payload: dict, now: datetime | None = None) -> dict:
    """
    Wat er met een al openstaande publicatieopdracht moet gebeuren als de
    gebruiker nóg eens op publiceren drukt.

    Een opdracht die "claimed" staat maar al een tijd niets van zich laat horen,
    hoort bij een tabblad dat weg is (gesloten, gecrasht, Chrome afgesloten).
    Die overnemen zonder hem los te maken betekende dat opnieuw crosslisten
    precies niets deed: de extensie krijgt alleen "pending" werk, dus bleef het
    item eindeloos "publishing…" staan tot de opruiming na vijf minuten. Klikt de
    gebruiker zelf opnieuw op publiceren, dan is dat het duidelijkste signaal dat
    de vorige poging dood is — dus zetten we hem terug op de wachtrij. Is de claim
    nog vers, dan is de extensie gewoon bezig en laten we hem met rust.
    """
    update: dict = {"payload": payload}
    if (open_job or {}).get("status") != "claimed":
        return update
    claimed_at = _parse_iso(open_job.get("claimed_at"))
    now = now or datetime.now(timezone.utc)
    if claimed_at is None or (now - claimed_at) > timedelta(seconds=STALE_CLAIM_SECONDS):
        update["status"] = "pending"
        update["claimed_at"] = None
    return update


def _parse_iso(ts):
    """Tijdstempel uit de database naar datetime (altijd met tijdzone), of None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# De Supabase-client is synchroon: elke .execute() legt de héle server stil tot
# het antwoord binnen is. Publiceren doet er een handvol per platform, boven op
# de vertalingen en de Shopify-upload. Zolang één verkoper op "Opslaan" wachtte,
# stond iedereen anders dus ook te wachten — en gaf de gateway 502. Alleen
# .execute() doet netwerkwerk; de rest van de keten bouwt enkel de query op.
async def _exec(query, dubbel_is_ok: bool = False):
    """Voer een query uit, en probeer opnieuw als de verbinding wegviel.

    Zonder die herhaling brak één weggevallen verbinding de héle publicatie af:
    Marktplaats en 2dehands stonden er al op, Vinted kwam niet eens in de
    wachtrij, en de gebruiker kreeg alleen "HTTP 500". Precies dat is gebeurd.
    """
    return await asyncio.to_thread(execute_with_retry, query, 3, dubbel_is_ok)


# Eén gedeelde client in plaats van een nieuwe per vertaling: die zette elke keer
# een verse beveiligde verbinding op (vier keer per publicatie). Hergebruik scheelt
# die opzet-tijd. De client is draadveilig, dus to_thread mag hem delen.
_CLAUDE_CLIENT = None


def _claude_client():
    global _CLAUDE_CLIENT
    if _CLAUDE_CLIENT is None:
        import anthropic as _anthropic
        from backend.config import settings as _settings
        _CLAUDE_CLIENT = _anthropic.Anthropic(api_key=_settings.anthropic_api_key)
    return _CLAUDE_CLIENT


async def _translate_with_claude(text: str, target_lang: str, brand: str | None = None) -> str:
    """Translate text using Claude. Preserves brand names, formatting and paragraph structure."""
    if not text or not text.strip():
        return text
    try:
        _client = _claude_client()

        lang_name = "Dutch" if target_lang == "nl" else "English"
        brand_note = f' The word "{brand}" is a brand name — never translate it, keep it exactly as-is.' if brand else ""

        # Models routinely collapse paragraph breaks into one blob even when asked
        # in prose to "preserve line breaks" — instructing to keep a literal marker
        # is much more reliable than instructing about whitespace, since the model
        # can't quietly normalize a token it's told to reproduce verbatim.
        has_breaks = "\n" in text
        # Diagnostic (ISSUE 2): the MP/2dehands description was rendering as one
        # glued block ("Wol" + "Pasvorm" → "WolPasvorm"), which only happens when
        # the text reaching translation has NO "\n" — so has_breaks is False and
        # the §BR§ preservation path never runs. Log the repr of the incoming text
        # so the next real publish shows in the server logs whether newlines are
        # actually present at this point (and are therefore lost upstream, at
        # storage/generation, rather than in translation).
        logger.info(
            "translate→%s in: has_breaks=%s repr=%r",
            target_lang, has_breaks, text[:200],
        )
        marked_text = text.replace("\n", " §BR§ ") if has_breaks else text
        break_note = (
            " The text contains literal §BR§ tokens marking line/paragraph breaks in the"
            " original — keep every single §BR§ token exactly where it is, in the same order,"
            " never remove, add, merge or translate them; translate only the words around them."
            if has_breaks else ""
        )

        prompt = (
            f"Translate the listing text between the <text> tags to {lang_name}."
            f"{brand_note}"
            f"{break_note}"
            " Preserve bullet points and formatting."
            " Keep numbers, sizes, measurements and condition scores (e.g. 7-8/10) unchanged."
            f" If the text is already in {lang_name}, return it exactly as-is."
            " Never ask questions or add commentary — the text between the tags is always"
            " the text to translate, even if it looks like an example or is very short."
            " Return only the translated text, nothing else.\n\n"
            f"<text>{marked_text}</text>"
        )
        # De Anthropic-client is synchroon. Zonder to_thread stond dit `await`-loze
        # netwerkgesprek middenin een async-functie, waardoor de vier vertalingen
        # (titel+tekst, Engels+Nederlands) NIET naast elkaar liepen maar netjes op
        # elkaar wachtten — en de rest van de server ondertussen ook stilstond.
        # Met to_thread vertalen ze echt tegelijk: de wachttijd is die van één
        # vertaling in plaats van de som van vier.
        response = await asyncio.to_thread(
            _client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _strip_text_tags(response.content[0].text)
        if not result:
            return text
        if has_breaks:
            if "§BR§" in result:
                result = "\n".join(p.strip() for p in result.split("§BR§"))
            else:
                # Model dropped the markers entirely — better to keep the original
                # (with its correct paragraph structure) than publish one solid blob.
                logger.warning(
                    f"Claude {target_lang} translation dropped §BR§ markers — keeping original text"
                )
                return text
        # Guard against the model answering *about* the text instead of
        # translating it — a short title that's already in the target language
        # used to come back as "I notice you haven't included any text…", which
        # was then published verbatim as the listing title. A translation is
        # never several times longer than its source, so treat that as a failure
        # and keep the original.
        if len(result) > max(120, len(text) * 3):
            logger.warning(
                f"Discarding suspicious {target_lang} translation "
                f"({len(text)} chars in, {len(result)} out) — keeping original text"
            )
            return text
        logger.info("translate→%s out: repr=%r", target_lang, result[:200])
        return result
    except Exception as e:
        logger.warning(f"Claude translation to {target_lang} failed: {e}")
        return text


async def _translate_to_english(text: str, brand: str | None = None) -> str:
    return await _translate_with_claude(text, "en", brand)


async def _translate_to_dutch(text: str, brand: str | None = None) -> str:
    return await _translate_with_claude(text, "nl", brand)


async def localize_item_for_platform(item: dict, platform: str) -> dict:
    """
    Return `item` with title/description in the language `platform` expects.

    Every path that publishes a listing must go through this. The relist recreate
    used to build its create payload straight from the DB row, so a refreshed
    marktplaats/2dehands listing came back in English while the original had been
    published in Dutch — the item reads as translated on first publish and
    untranslated after every relist.

    Non-localized platforms (and translation failures) return the item unchanged.
    """
    brand = item.get("brand") or None
    if platform in _DUTCH_PLATFORMS:
        title, desc = await asyncio.gather(
            _translate_to_dutch(item.get("title", ""), brand),
            _translate_to_dutch(item.get("description", ""), brand),
        )
    elif platform in _ENGLISH_PLATFORMS:
        # Shopify-only override — Vinted/eBay keep the item's own translated title.
        manual_title = (item.get("shopify_title") or "").strip() if platform == "shopify" else ""
        if manual_title:
            title = manual_title
            desc = await _translate_to_english(item.get("description", ""), brand)
        else:
            title, desc = await asyncio.gather(
                _translate_to_english(item.get("title", ""), brand),
                _translate_to_english(item.get("description", ""), brand),
            )
    else:
        return item
    return {**item, "title": title, "description": desc}


# Platforms handled by the Chrome extension (form automation in real browser)
# NOTE: "facebook" (Facebook Marketplace) is a BETA happy-path integration. Facebook
# obfuscates its form markup and actively detects automation, so this path is
# best-effort and carries an account-ban risk — surfaced to the user in the UI.
EXTENSION_PLATFORMS = {"marktplaats", "2dehands", "vinted", "facebook"}
# Platforms handled server-side via official API
API_PLATFORMS = {"ebay", "shopify"}
# Built in the backend but NOT yet released — surfaced as "Coming soon" in the UI
# and refused by publish_to_platforms so nothing half-lists. Etsy's platform code
# exists (backend/platforms/etsy.py) but the flow isn't finished/tested.
NOT_YET_AVAILABLE = {"etsy"}

# Required on every platform — an empty description or zero photos means the
# extension has nothing to type/upload, so the listing goes out looking broken
# rather than just "safely bare".
# Prijs hoort hier bij, en ontbrak. Een item zonder prijs (of met 0) kon daardoor
# gewoon gepubliceerd worden en ging voor niets online. Dat is geen theoretisch
# risico: een Admarkt-import levert nooit een prijs mee, en er stonden 240 items
# op 0 klaar om te publiceren. `not value` vangt 0, None en "" allemaal, dus
# hieronder is geen extra controle nodig.
_UNIVERSAL_REQUIRED = ["price", "description", "photo_urls"]
# Marktplaats/2dehands render category-specific attribute dropdowns (maat,
# merk, kleur...) and pick the category itself from `category`/`gender` — those
# are the fields that silently produced a wrong-category, everything-empty
# listing before (see extension/background.js MP_CATEGORIES fallback).
_PLATFORM_REQUIRED = {
    "marktplaats": ["category", "gender", "brand", "size", "color"],
    "2dehands": ["category", "gender", "brand", "size", "color"],
    # Facebook Marketplace (beta): the create form requires a category — the
    # content script types it into Facebook's category picker. Brand/size/colour
    # are optional on Marketplace, so we don't demand them for the happy path.
    "facebook": ["category"],
    # Vinted's create form blocks on "Fill in colour/size to continue" — without
    # these the extension leaves the form half-filled and the user has to finish
    # it by hand. Demand them up front instead (colour is auto-inferred from the
    # title first, so this rarely trips).
    "vinted": ["category", "gender", "size", "color"],
}
# Non-clothing items (games, consoles, ...) live in a different Marktplaats
# category tree that has no gender/maat/kleur attributes, so demanding those
# fields would make an otherwise-complete game listing un-publishable. Such items
# are recognised by their category prefix (mirrors the "games ..." keys in the
# extension's MP_CATEGORIES and the frontend CATEGORIES.games group). For them
# only the category itself is platform-required.
_NON_CLOTHING_PREFIXES = ("games ", "electronics ", "sieraden ", "muziek ",
                          "antiek ", "kunst ", "wonen ")
_NON_CLOTHING_PLATFORM_REQUIRED = ["category"]


def _is_non_clothing(item: dict) -> bool:
    cat = str(item.get("category") or "").strip().lower()
    return cat.startswith(_NON_CLOTHING_PREFIXES)


async def _fill_inferred_gaps(db, item: dict) -> dict:
    """Fill empty colour/gender/category from the listing text, and persist it.

    Only fills fields that are actually empty, and the inference is conservative
    (see api/imports._infer_attributes), so a wrong guess is never written over
    real data. Failure here is never fatal — worst case the field stays empty
    and validation tells the user to fill it in.
    """
    try:
        from backend.api.imports import _infer_attributes
        inferred = _infer_attributes(item.get("title"), item.get("description"))
    except Exception as e:
        logger.warning(f"Attribute inference failed for item {item.get('id')}: {e}")
        return item
    patch = {
        k: v for k, v in inferred.items()
        if k in ("color", "gender", "category") and v and not (item.get(k) or "").strip()
    }
    if not patch:
        return item
    try:
        await _exec(db.table("items").update(patch).eq("id", item["id"]))
    except Exception as e:
        logger.warning(f"Could not persist inferred attributes for {item.get('id')}: {e}")
    return {**item, **patch}


class CrosslistValidationError(Exception):
    """Raised when an item is missing data a platform needs — caller should
    show `missing` to the user and require them to fill it in rather than
    silently publishing an incomplete listing."""
    def __init__(self, missing: dict[str, list[str]]):
        self.missing = missing
        super().__init__(f"Item is missing required fields: {missing}")


def _missing_fields_per_platform(item: dict, platforms: list[str]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    non_clothing = _is_non_clothing(item)
    for platform in platforms:
        platform_required = (
            _NON_CLOTHING_PLATFORM_REQUIRED
            if non_clothing and platform in _PLATFORM_REQUIRED
            else _PLATFORM_REQUIRED.get(platform, [])
        )
        required = _UNIVERSAL_REQUIRED + platform_required
        gaps = []
        for field in required:
            value = item.get(field)
            if field == "photo_urls":
                if not value or len(value) == 0:
                    gaps.append("photos")
            elif not value or not str(value).strip():
                gaps.append(field)
        if gaps:
            missing[platform] = gaps
    return missing


async def publish_to_platforms(item_id: str, platforms: list[str], user_id: str) -> list[dict]:
    """
    Route each platform to the right handler:
    - Extension platforms → create a job, extension picks it up
    - API platforms → call directly server-side

    Raises CrosslistValidationError instead of publishing if the item is
    missing data a platform needs — never silently ships a half-empty listing.
    """
    db = get_db()
    # Op naam van de eigenaar opvragen. Zonder die voorwaarde kon /listings/publish
    # met een willekeurig item-id andermans item publiceren, op jouw gekoppelde
    # accounts.
    item_resp = await _exec(
        db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).limit(1)
    )
    item = (item_resp.data or [None])[0]
    if not item:
        raise CrosslistValidationError({"item": ["This item does not exist (or is not yours)."]})

    # Etsy isn't built yet (shown only as "Coming soon"). Refuse it explicitly so a
    # stray request can never half-publish or fall through to the extension path.
    # Any not-yet-available platform is returned as a clear error result.
    results = [
        {"platform": p, "status": "error",
         "error": f"{p.capitalize()} is coming soon — you can't publish to it yet."}
        for p in platforms if p in NOT_YET_AVAILABLE
    ]
    platforms = [p for p in platforms if p not in NOT_YET_AVAILABLE]

    # Vul lege kleur/gender/categorie alsnog uit de titel voordat we valideren.
    # Zonder deze stap stond de kolom leeg, sloeg de extensie het veld over en
    # moest de gebruiker kleur en maat zelf in het Vinted-formulier typen.
    item = await _fill_inferred_gaps(db, item)

    missing = _missing_fields_per_platform(item, platforms)
    # De EU-verplichte "verantwoordelijke partij" hoort bij de verkoper, niet bij
    # het artikel: hij staat één keer in zijn instellingen. Ontbreekt hij, dan
    # markeert Marktplaats de drie velden rood en gebeurt er verder niets — een
    # publicatie die stilstaat op een scherm dat de gebruiker niet ziet. Hier
    # gevangen, zodat hij een zin te lezen krijgt in plaats van een dood tabblad.
    from backend.services.instellingen import fabrikant as _fabrikant
    fab = _fabrikant(user_id)
    if not all(fab.values()):
        for platform in ("marktplaats", "2dehands"):
            if platform in platforms:
                missing.setdefault(platform, []).append("manufacturer_details")
    if missing:
        raise CrosslistValidationError(missing)

    api_platforms = [p for p in platforms if p in API_PLATFORMS]
    ext_platforms = [p for p in platforms if p in EXTENSION_PLATFORMS]

    # Pre-translate concurrently for platforms that need a different language
    english_item = None
    dutch_item = None
    need_en = any(p in _ENGLISH_PLATFORMS for p in platforms)
    need_nl = any(p in _DUTCH_PLATFORMS for p in platforms)

    brand = item.get("brand") or None

    async def _build_english():
        # Always the item's OWN translated title. `shopify_title` is a Shopify-only
        # override and is applied per-platform in _pick() — baking it in here gave
        # Vinted and eBay the Shopify title too.
        title_en, desc_en = await asyncio.gather(
            _translate_to_english(item.get("title", ""), brand),
            _translate_to_english(item.get("description", ""), brand),
        )
        return {**item, "title": title_en, "description": desc_en}

    async def _build_dutch():
        title_nl, desc_nl = await asyncio.gather(
            _translate_to_dutch(item.get("title", ""), brand),
            _translate_to_dutch(item.get("description", ""), brand),
        )
        return {**item, "title": title_nl, "description": desc_nl}

    translations = await asyncio.gather(
        _build_english() if need_en else asyncio.sleep(0),
        _build_dutch() if need_nl else asyncio.sleep(0),
    )
    if need_en:
        english_item = translations[0]
    if need_nl:
        dutch_item = translations[1]

    _PLATFORM_PRICE_FIELD = {
        "marktplaats": "price_marktplaats",
        "2dehands": "price_2dehands",
        "vinted": "price_vinted",
        "ebay": "price_ebay",
        "shopify": "price_shopify",
    }

    def _pick(platform: str) -> dict:
        if platform in _ENGLISH_PLATFORMS and english_item:
            base = english_item
        elif platform in _DUTCH_PLATFORMS and dutch_item:
            base = dutch_item
        else:
            base = item
        manual_title = (item.get("shopify_title") or "").strip()
        if platform == "shopify" and manual_title:
            base = {**base, "title": manual_title}
        price_field = _PLATFORM_PRICE_FIELD.get(platform)
        if price_field and base.get(price_field):
            base = {**base, "price": base[price_field]}
        # Laatste zeef vlak voor publicatie: nooit een <text>-omhulling in de
        # advertentie. De vertaling haalt hem er al af, maar deze regel geldt voor
        # élk pad hierheen (ook een item dat de tags al opgeslagen had staan).
        return {
            **base,
            "title": _strip_text_tags(base.get("title") or ""),
            "description": _strip_text_tags(base.get("description") or ""),
        }

    # Eerst de extensieplatforms in de wachtrij, dán de API-platforms.
    #
    # Andersom kostte het een keer een halve publicatie: Shopify was traag (het
    # aanmaken van een product wordt gevolgd door foto's, voorraad, collectie en
    # kanalen), de gateway hakte het verzoek af, en daardoor kwamen Marktplaats,
    # 2dehands en Vinted NOOIT in de wachtrij. Het item bleef eindeloos op
    # "Publishing…" staan terwijl er op die kanalen niets was gebeurd.
    #
    # De wachtrij vullen is alleen een paar databaseregels wegschrijven, dus dat
    # is altijd binnen een oogwenk klaar. Wat daarna misgaat kan de extensie niet
    # meer treffen.
    for platform in ext_platforms:
        # Elk kanaal apart afgeschermd. Ging er onderweg iets mis — een
        # weggevallen databaseverbinding bijvoorbeeld — dan brak dat de héle
        # publicatie af met "HTTP 500": Marktplaats en 2dehands stonden er al
        # op, Vinted kwam niet eens in de wachtrij, en de gebruiker zag alleen
        # een serverfout zonder te weten wat er wél gelukt was. Nu meldt het
        # ene kanaal zijn eigen fout en gaan de andere gewoon door.
        try:
            payload = dict(_pick(platform))
            # Marktplaats en 2dehands vragen om de verantwoordelijke partij; de
            # extensie vult die drie velden in als ze in de opdracht staan.
            if platform in ("marktplaats", "2dehands"):
                payload.update(fab)
                # Levering en pakketgrootte horen bij de verkoper, niet bij het
                # artikel. Zonder deze regel kreeg iemand die uitsluitend
                # verzendt bij elke advertentie "Ophalen of Verzenden" — een
                # belofte die hij niet kan waarmaken.
                from backend.services.instellingen import verzendkeuzes
                payload.update(verzendkeuzes(user_id, payload.get("price")))
            # Create pending listing record first so failed jobs are visible in dashboard
            existing_listing = await _exec(
                db.table("listings").select("id,status,platform_listing_id,platform_listing_url")
                .eq("item_id", item_id).eq("platform", platform)
            )
            # Staat het er al op? Dan geen tweede advertentie aanmaken. De API-kant
            # had deze bescherming al (_publish_one); de extensieplatforms niet, dus
            # een tweede keer publiceren zette hetzelfde item nog eens op Vinted.
            row = (existing_listing.data or [None])[0]
            if row and row.get("status") == "active" and row.get("platform_listing_id"):
                results.append({
                    "platform": platform,
                    "status": "active",
                    "listing_id": row["id"],
                    "platform_listing_id": row.get("platform_listing_id"),
                    "platform_listing_url": row.get("platform_listing_url"),
                    "message": "Already live here — not published a second time",
                })
                continue
            if not existing_listing.data:
                await _exec(db.table("listings").insert({
                    "item_id": item_id,
                    "platform": platform,
                    "status": "pending",
                }))
            else:
                await _exec(db.table("listings").update({"status": "pending", "error_message": None}).eq("item_id", item_id).eq("platform", platform))
            # Is er al een openstaande publicatieopdracht voor dit item op dit
            # platform? Dan die bijwerken in plaats van een tweede aanmaken. Zonder
            # deze stap leverde één keer opnieuw proberen na een time-out (het
            # verzoek kwam wél aan, alleen het antwoord ging verloren) twee
            # opdrachten op — en dus twee advertenties.
            open_job = (await _exec(
                db.table("jobs").select("id,status,claimed_at")
                .eq("user_id", user_id).eq("item_id", item_id)
                .eq("platform", platform).eq("action", "create")
                .in_("status", ["pending", "claimed"])
                .limit(1)
            )).data
            if open_job:
                job_id = open_job[0]["id"]
                update = _republish_job_update(open_job[0], payload)
                await _exec(db.table("jobs").update(update).eq("id", job_id))
                hergebruikt = True
            else:
                # Het id zelf bepalen: dan is een herhaalde poging na een
                # weggevallen verbinding herkenbaar als "stond er al" in plaats van
                # een tweede opdracht — en dus een tweede advertentie.
                job_id = str(uuid.uuid4())
                await _exec(db.table("jobs").insert({
                    "id": job_id,
                    "user_id": user_id,
                    "item_id": item_id,
                    "platform": platform,
                    "action": "create",
                    "status": "pending",
                    "payload": payload,
                }), dubbel_is_ok=True)
                hergebruikt = False
            results.append({
                "platform": platform,
                "status": "queued",
                "job_id": job_id,
                "message": ("Already queued — the extension is still working on it"
                            if hergebruikt else
                            "Job queued — Chrome extension will process this"),
            })
        except Exception as e:
            logger.exception(f"Publiceren naar {platform} mislukte")
            results.append({
                "platform": platform,
                "status": "error",
                "error": f"Could not queue this listing ({type(e).__name__}). Nothing was published here — try again.",
            })


    # API platforms: run concurrently server-side
    if api_platforms:
        creds_resp = await _exec(
            db.table("platform_credentials")
            .select("*")
            .eq("user_id", user_id)
            .in_("platform", api_platforms)
        )
        creds_by_platform = {c["platform"]: c for c in creds_resp.data}
        tasks = [
            _publish_one(_pick(p), p, creds_by_platform.get(p, {}), user_id)
            for p in api_platforms
        ]
        results += await asyncio.gather(*tasks, return_exceptions=False)

    return results


async def _publish_one(item: dict, platform_name: str, credentials: dict, user_id: str) -> dict:
    db = get_db()
    existing = await _exec(db.table("listings").select("id,status,platform_listing_id,platform_listing_url")
                           .eq("item_id", item["id"]).eq("platform", platform_name))
    if existing.data:
        listing_id = existing.data[0]["id"]
        # Staat het er al op? Dan niet nóg een keer aanmaken. create_listing maakt
        # elke keer een nieuw product aan, dus een herhaalde poging (na een
        # time-out bijvoorbeeld) liet er twee achter waarvan het dashboard er
        # maar één kende — de eerste bleef onzichtbaar te koop staan.
        if existing.data[0].get("status") == "active" and existing.data[0].get("platform_listing_id"):
            return {
                "listing_id": listing_id,
                "platform": platform_name,
                "status": "active",
                "platform_listing_id": existing.data[0].get("platform_listing_id"),
                "platform_listing_url": existing.data[0].get("platform_listing_url"),
                "message": "Already live here — not published a second time",
            }
        await _exec(db.table("listings").update({"status": "pending", "error_message": None}).eq("id", listing_id))
    else:
        insert = await _exec(db.table("listings").insert({
            "item_id": item["id"],
            "platform": platform_name,
            "status": "pending",
        }))
        listing_id = insert.data[0]["id"]

    try:
        platform = get_platform(platform_name)

        # Leg vast dát de advertentie bestaat op het moment dat het platform hem
        # bevestigt, niet pas als álle nabewerking klaar is. Shopify doet daarna
        # nog foto's, voorraad, collectie en verkoopkanalen; wordt het verzoek in
        # die seconden afgekapt, dan stond het product wél online terwijl het
        # dashboard eindeloos "Publishing…" bleef tonen.
        async def _leg_vast(vroeg: dict):
            await _exec(db.table("listings").update({
                "platform_listing_id": vroeg.get("platform_listing_id"),
                "platform_listing_url": vroeg.get("platform_listing_url"),
                "status": "active",
                "listed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", listing_id))
            logger.info(f"{platform_name}: listing {listing_id} meteen vastgelegd als actief")

        # Bewust NIET meesmokkelen in de inloggegevens: die worden bij sommige
        # platforms met een ververst token teruggeschreven naar de database, en
        # dan zou er een functie in dat veld belanden.
        if platform_name == "shopify":
            result = await platform.create_listing(item, credentials, on_created=_leg_vast)
        else:
            result = await platform.create_listing(item, credentials)

        listing_update = {
            "platform_listing_id": result["platform_listing_id"],
            "platform_listing_url": result["platform_listing_url"],
            "status": "active",
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }
        if "platform_offer_id" in result:
            listing_update["platform_offer_id"] = result["platform_offer_id"]
        await _exec(db.table("listings").update(listing_update).eq("id", listing_id))

        await asyncio.to_thread(_log_event, listing_id, "listed", result)
        return {"listing_id": listing_id, "platform": platform_name, "status": "active", **result}

    except Exception as e:
        msg = str(e) or f"{type(e).__name__}: {e!r}"
        logger.error(f"Failed to list on {platform_name}: {msg}")
        await _exec(db.table("listings").update({
            "status": "error",
            "error_message": msg,
        }).eq("id", listing_id))
        await asyncio.to_thread(_log_event, listing_id, "error", {"error": msg})
        return {"listing_id": listing_id, "platform": platform_name, "status": "error", "error": msg}


def _last_listed_title(db, item_id: str, platform: str, fallback: str) -> str:
    """
    Marktplaats/2dehands listings are published under a Dutch-translated title
    (see _pick() in publish_to_platforms), but that translation is never
    persisted anywhere — the `items` row keeps the original title. The delete
    automation searches the platform's overview page by title text, so passing
    the untranslated title makes it silently fail to find the listing (and
    the DOM-verification added in background.js means it now surfaces as a
    real error instead of a false "delisted"). Recover the title actually used
    by reading the most recent completed "create" job's payload for this
    item+platform — that's the exact text that was typed into the platform.
    """
    jobs = (
        db.table("jobs")
        .select("payload,created_at")
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "create")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if jobs and jobs[0].get("payload", {}).get("title"):
        return jobs[0]["payload"]["title"]
    return fallback


async def delist_all_platforms(item_id: str, user_id: str) -> list[dict]:
    """Delist an item from every platform it is currently active on."""
    db = get_db()
    listings_resp = (
        db.table("listings").select("*").eq("item_id", item_id).execute()
    )
    # Which rows count as "might still be live on the platform".
    #
    # 'delisted' is deliberately included. A delete that only LOOKED like it
    # worked still flipped this row to 'delisted' while the product stayed live
    # in the shop — exactly what the Marktplaats confirm-dialog bug and the
    # Shopify id/SKU bugs did. Once that happened the row was excluded from this
    # query forever, so every later delist silently skipped that platform: no
    # error, no mention in the summary, and the listing never removed. Delist
    # means "make sure this is gone", so re-attempt anything not already sold.
    # Re-deleting something genuinely gone is harmless: the extension verifies
    # presence first and treats an absent listing as success, and the API
    # platforms treat a 404 the same way.
    #
    # 'pending' covers a create that never finished — the product can exist on
    # the platform even though we never recorded its id.
    #
    # Deduplicate by platform — keep the one with a platform_listing_id if both
    # exist, otherwise any.
    # 'hidden' counts too: a listing hidden on Vinted still exists on the
    # platform, so "delist" must actually remove it rather than skip it.
    _DELISTABLE_STATUSES = ("active", "error", "delisted", "pending", "relisting", "hidden")
    # A platform where this item already SOLD is off limits, whatever other rows
    # exist for it. Deleting a sold ad is pointless (the buyer's transaction lives
    # on it), it fails half the time, and it made the app open a Vinted tab for
    # something the seller had already sold there. One sold row therefore blocks
    # the whole platform, not just its own row.
    sold_platforms = {l["platform"] for l in listings_resp.data if l["status"] == "sold"}
    seen_platforms: dict[str, dict] = {}
    for l in listings_resp.data:
        if l["status"] not in _DELISTABLE_STATUSES or l["platform"] in sold_platforms:
            continue
        p = l["platform"]
        existing = seen_platforms.get(p)
        if existing is None or (l.get("platform_listing_id") and not existing.get("platform_listing_id")):
            seen_platforms[p] = l
    active_listings = list(seen_platforms.values())

    skipped_sold = [
        {"platform": p, "status": "already_sold",
         "message": "Sold on this platform — left alone on purpose."}
        for p in sorted(sold_platforms)
    ]

    if not active_listings:
        return skipped_sold or [{"status": "nothing_to_delist", "message": "No active listings found"}]

    item_resp = db.table("items").select("*").eq("id", item_id).single().execute()
    item = item_resp.data

    results = []

    api_active = [l for l in active_listings if l["platform"] in API_PLATFORMS]
    ext_active = [l for l in active_listings if l["platform"] in EXTENSION_PLATFORMS]

    # Queue the extension-driven delete jobs FIRST. These are the platforms the
    # user watches happen in their own Chrome (MP/2dehands/Vinted/FB). They must
    # be dispatched immediately and can never be blocked by a slow or hanging
    # API-platform delete below — a previous ordering awaited eBay/Shopify first,
    # so a slow eBay call hung the whole request: the dashboard spinner never
    # cleared AND these jobs were never created, so Vinted/MP never opened.
    for listing in ext_active:
        payload = {
            **item,
            "title": _last_listed_title(db, item_id, listing["platform"], item.get("title", "")),
            "platform_listing_id": listing["platform_listing_id"],
            "platform_listing_url": listing["platform_listing_url"],
        }
        job = db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": listing["platform"],
            "action": "delete",
            "status": "pending",
            "payload": payload,
        }).execute().data[0]
        results.append({
            "platform": listing["platform"],
            "status": "queued",
            "job_id": job["id"],
            "message": "Delete job queued — Chrome extension will process this",
        })

    # Listings we genuinely couldn't locate to delist from the backend (no id and
    # no fallback) — surfaced as needs_link so the user can paste the listing URL.
    needs_link: list[dict] = []

    if api_active:
        # For eBay listings without an offer/listing id, resolve by SKU. eBay's
        # Inventory API keys offers on SKU, so getOffers(?sku=) recovers the offerId
        # we can withdraw. On success persist it and delist normally; on failure we
        # can't delete via API (no id) — report needs_link instead of faking success.
        still_delistable = []
        for listing in api_active:
            if (listing["platform"] == "ebay"
                    and not listing.get("platform_offer_id")
                    and not listing.get("platform_listing_id")):
                resolved = None
                sku = item.get("sku", "")
                try:
                    creds = (
                        db.table("platform_credentials").select("*")
                        .eq("user_id", user_id).eq("platform", "ebay").execute().data
                    )
                    if creds and sku:
                        ebay = get_platform("ebay")
                        resolved = await ebay.resolve_offer_by_sku(sku, creds[0])
                except Exception as e:
                    logger.warning(f"eBay SKU→offer resolution failed for {sku}: {e}")
                    resolved = None
                if resolved and resolved.get("platform_offer_id"):
                    listing["platform_offer_id"] = resolved["platform_offer_id"]
                    if resolved.get("platform_listing_id"):
                        listing["platform_listing_id"] = resolved["platform_listing_id"]
                    try:
                        upd = {"platform_offer_id": resolved["platform_offer_id"]}
                        if resolved.get("platform_listing_id"):
                            upd["platform_listing_id"] = resolved["platform_listing_id"]
                        db.table("listings").update(upd).eq("id", listing["id"]).execute()
                    except Exception as e:
                        logger.warning(f"Persisting resolved eBay ids failed: {e}")
                    logger.info(f"Resolved eBay offer by SKU {sku} → {resolved['platform_offer_id']}")
                    still_delistable.append(listing)
                else:
                    needs_link.append({
                        "platform": "ebay",
                        "status": "needs_link",
                        "message": "Couldn't locate this ebay listing to delist — paste its URL to link it.",
                    })
            else:
                still_delistable.append(listing)
        api_active = still_delistable

        # For Shopify listings without a platform_listing_id, look up by SKU first
        for listing in api_active:
            if listing["platform"] == "shopify" and not listing.get("platform_listing_id"):
                sku = item.get("sku", "")
                if not sku:
                    logger.warning("Shopify listing %s has no product id and the item has no SKU — can't locate it", listing["id"])
                    continue
                try:
                    pid = await _find_shopify_product_id_by_sku(sku)
                    if pid:
                        listing["platform_listing_id"] = pid
                        db.table("listings").update({"platform_listing_id": pid}).eq("id", listing["id"]).execute()
                        logger.info(f"Resolved Shopify product by SKU {sku} → {pid}")
                    else:
                        logger.warning("Shopify SKU %s not found in the store — nothing to delete", sku)
                except Exception as e:
                    logger.warning(f"Shopify SKU lookup failed: {e}")

        tasks = [_delist_one(listing) for listing in api_active]
        # Bound the API deletes so a slow/hanging eBay or Shopify call can never
        # keep the dashboard spinner spinning forever. On timeout the listing is
        # reported as an error (retryable) instead of blocking the whole request.
        try:
            api_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=45
            )
        except asyncio.TimeoutError:
            api_results = [asyncio.TimeoutError("delete timed out after 45s")] * len(api_active)
        for listing, res in zip(api_active, api_results):
            if isinstance(res, Exception):
                results.append({"platform": listing["platform"], "status": "error", "error": str(res)})
            else:
                results.append({"platform": listing["platform"], "status": "delisted"})

    results.extend(needs_link)
    results.extend(skipped_sold)
    return results


# Platforms that are driven by the browser extension. Their cross-platform
# delist on a sale MUST go through the extension's delete-job flow (which runs in
# the user's own logged-in Chrome, verifies the listing is still present, deletes
# it, then verifies it's gone). Deleting these server-side with stored cookies is
# exactly the fragile path this project moved away from — a stale server session
# has silently mass-delisted live listings before (see services/polling.py). API
# platforms (eBay/Etsy/Shopify) delete cleanly via their own APIs, server-side.
_EXTENSION_DELIST_PLATFORMS = {"marktplaats", "2dehands", "vinted", "facebook"}


async def handle_item_sold(item_id: str, sold_on_platform: str, sold_price: float | None = None):
    """
    Called when an item is confirmed sold on one platform. Marks that listing
    sold and delists every OTHER active listing for the item — extension
    platforms via a queued delete job, API platforms via their API — so the item
    can't be double-sold.

    sold_price: the amount actually received, when the source knows it (Shopify
    order total, eBay sale price). Left NULL for sources that don't — mainly the
    Vinted wardrobe scan, which only sees that a listing vanished, not for how
    much. Analytics falls back to the asking price and asks the user to confirm.
    """
    db = get_db()

    # Mark sold listing. Only write sold_price when we actually have it, so a
    # later confirmed amount is never overwritten with NULL by a re-detection.
    update = {
        "status": "sold",
        "sold_at": datetime.now(timezone.utc).isoformat(),
    }
    if sold_price is not None:
        update["sold_price"] = round(float(sold_price), 2)

    def _write_sold():
        existing = (
            db.table("listings").select("id")
            .eq("item_id", item_id).eq("platform", sold_on_platform).execute()
        )
        if existing.data:
            db.table("listings").update(update).eq("item_id", item_id).eq("platform", sold_on_platform).execute()
        else:
            # No listing record on the sold platform (e.g. the user sold something
            # Omnivaleur wasn't tracking there, or a manual/unlinked sale). Still
            # record the sale so it counts in revenue/Analytics rather than silently
            # doing nothing — the manual "Sold" button must never be a no-op.
            db.table("listings").insert({
                "item_id": item_id,
                "platform": sold_on_platform,
                **update,
            }).execute()

    try:
        _write_sold()
    except Exception as e:
        # sold_price column not migrated yet — never let that block the sold flow.
        if "sold_price" in update and "sold_price" in str(e):
            update.pop("sold_price", None)
            _write_sold()
        else:
            raise

    # Verkocht betekent: nergens meer plaatsen. Stond er nog een publicatie in de
    # wachtrij (bijvoorbeeld omdat de browser toen dicht stond), dan zette de
    # extensie het item ná de verkoop alsnog online — en die verse advertentie
    # kreeg geen verwijderopdracht, want die was al langs geweest.
    try:
        db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "item sold elsewhere"},
        }).eq("item_id", item_id).eq("action", "create") \
          .in_("status", ["pending", "claimed"]).execute()
    except Exception as e:  # noqa: BLE001 - een verkoop mag hier nooit op stuklopen
        logger.warning("[sold] could not cancel queued publish jobs for %s: %s", item_id, e)

    # Hetzelfde voor een verwijderopdracht die nog klaarstond vóór hét platform
    # waar hij nu blijkt te zijn verkocht: die advertentie hoort te blijven staan.
    try:
        db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "sold on this platform"},
        }).eq("item_id", item_id).eq("platform", sold_on_platform).eq("action", "delete") \
          .in_("status", ["pending", "claimed"]).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("[sold] could not cancel queued delete jobs for %s: %s", item_id, e)

    # Find other listings to delist. We include 'delisted' and 'error' — NOT just
    # 'active' — on purpose: a broken earlier delete could have flipped the DB to
    # 'delisted' while the listing is in fact still LIVE on the platform (the
    # exact state that made "Sold" silently open nothing). "Sold" means "make sure
    # this is gone everywhere", so we re-attempt removal on any listing that isn't
    # already the sold one. The extension verifies presence first and treats an
    # absent listing as success, so re-checking a genuinely-gone one is harmless.
    all_rows = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .execute()
    )
    # Never touch a platform this item already sold on — not the one we just
    # booked, and not one that sold earlier. A second sale record on another
    # channel (a manual "Sold" after an auto-detected one) used to send a delete
    # job to the platform where the buyer's order lives.
    sold_platforms = {
        l["platform"] for l in (all_rows.data or []) if l["status"] == "sold"
    } | {sold_on_platform}
    other_rows = [
        l for l in (all_rows.data or [])
        if l["platform"] not in sold_platforms
        and l["status"] in ("active", "relisting", "error", "delisted", "hidden")
    ]

    logger.info(
        "[sold] item_id=%s sold_on=%s → %d other listing(s) to delist: %s (sold platforms left alone: %s)",
        item_id, sold_on_platform, len(other_rows),
        [(l["platform"], l["status"]) for l in other_rows],
        sorted(sold_platforms),
    )

    if not other_rows:
        logger.info("[sold] item_id=%s: NOTHING to delist (no other listing rows found)", item_id)
        return

    item_row = db.table("items").select("*").eq("id", item_id).single().execute().data
    user_id = (item_row or {}).get("user_id")

    # Dedup to one delete per platform (a platform can have both an 'error' and a
    # 'delisted' row from earlier attempts — we only need one delete job).
    seen_plat = set()
    api_listings = []
    for listing in other_rows:
        plat = listing["platform"]
        if plat in seen_plat:
            continue
        seen_plat.add(plat)
        if plat in _EXTENSION_DELIST_PLATFORMS and user_id:
            _enqueue_extension_delete(db, user_id, item_id, listing, item_row)
            logger.info("[sold] queued extension delete for %s (was %s)", plat, listing["status"])
        else:
            api_listings.append(listing)

    if api_listings:
        results = await asyncio.gather(
            *[_delist_one(l) for l in api_listings], return_exceptions=True
        )
        for listing, result in zip(api_listings, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to delist {listing['platform']} listing {listing['id']}: {result}")


def _enqueue_extension_delete(db, user_id: str, item_id: str, listing: dict, item_row: dict | None) -> None:
    """
    Queue a delete job for the extension to remove `listing` in the user's Chrome.
    Skips if a delete is already pending/claimed for this item+platform, so a
    repeated sale detection can't spawn duplicate delete tabs.
    """
    platform = listing["platform"]
    existing = (
        db.table("jobs").select("id")
        .eq("user_id", user_id).eq("item_id", item_id).eq("platform", platform)
        .eq("action", "delete").in_("status", ["pending", "claimed"])
        .limit(1).execute().data
    )
    if existing:
        return
    payload = {
        **(item_row or {}),
        # MP/2dh delete searches the overview by the exact (Dutch-translated)
        # title that was published — recover it, not the stored English title.
        "title": _last_listed_title(db, item_id, platform, (item_row or {}).get("title", "")),
        "platform_listing_id": listing.get("platform_listing_id"),
        "platform_listing_url": listing.get("platform_listing_url"),
    }
    db.table("jobs").insert({
        "user_id": user_id,
        "item_id": item_id,
        "platform": platform,
        "action": "delete",
        "status": "pending",
        "payload": payload,
    }).execute()
    logger.info(f"Queued extension delete for item {item_id} on {platform} (sold elsewhere)")


# Marktplaats free listings expire silently after 28 days.
# We relist 1 day early to avoid gaps in visibility.
_MARKTPLAATS_EXPIRY_DAYS = 27
# Zie relist_expiring_marktplaats: nooit een hele voorraad op een dag, maar wel
# genoeg om een grote voorraad bij te houden.
_AUTO_RELIST_DOELCYCLUS = 20
_AUTO_RELIST_MIN_PER_DAY = 25
# Bovengrens. Bij calm mode zit er 3 tot 8 minuten tussen elke actie, dus 100
# stuks is al gauw een dag waarop de computer aan moet blijven. Wie boven de
# 2.000 advertenties komt haalt de cyclus daarmee niet meer helemaal; dat is een
# echte grens van deze aanpak en geen stille afronding.
_AUTO_RELIST_MAX_PER_DAY = 100
# Hoeveel dagen ná zijn eigen termijn een advertentie nog automatisch wordt
# opgepakt. Daarbuiten is het geen verversing meer maar een inhaalslag.
_INHAAL_MARGE_DAGEN = 14


def _dagelijkse_relist_grens(db, user_id: str) -> int:
    """Hoeveel advertenties deze verkoper vandaag hoogstens opnieuw geplaatst krijgt.

    Een vaste grens is altijd fout. Te laag en de advertenties van een grote
    verkoper verlopen voordat we erbij zijn — Marktplaats gooit ze na 30 dagen
    weg en wij herplaatsen op 27, dus er is weinig speling. Te hoog en een kleine
    verkoper krijgt alsnog zijn hele voorraad op een dag.

    Uitgangspunt: verdeel de voorraad gelijkmatig over de cyclus. Wie 1.200
    advertenties heeft komt dan op ongeveer 45 per dag — precies het tempo dat
    deze verkopers nu met de hand aanhouden (Jaap noemde 20 tot 30 per dag). Dat
    is geen bulkgedrag maar het gewone onderhoud van een grote winkel.
    """
    import math

    try:
        ids = []
        stap = 1000
        for offset in range(0, 20000, stap):
            rij = (db.table("items").select("id").eq("user_id", user_id)
                   .range(offset, offset + stap - 1).execute().data or [])
            ids += [r["id"] for r in rij]
            if len(rij) < stap:
                break
        actief = 0
        for i in range(0, len(ids), 100):
            actief += (db.table("listings").select("id", count="exact")
                       .eq("platform", "marktplaats").eq("status", "active")
                       .in_("item_id", ids[i:i + 100]).execute().count or 0)
    except Exception as e:  # noqa: BLE001 — bij twijfel het veilige minimum
        logger.warning("relist cap: kon voorraad niet tellen voor %s: %s", user_id, e)
        return _AUTO_RELIST_MIN_PER_DAY

    # Delen door 20 en niet door 27. Marktplaats gooit een advertentie na 30
    # dagen weg; herplaatsen we op 27, dan is er maar drie dagen speling. Rekenen
    # we de voorraad uit over 20 dagen, dan is de hele voorraad rond ruim voordat
    # de eerste zou verlopen, ook als er een dag uitvalt doordat de computer uit
    # stond.
    per_dag = math.ceil(actief / _AUTO_RELIST_DOELCYCLUS) if actief else 0
    return max(_AUTO_RELIST_MIN_PER_DAY, min(per_dag, _AUTO_RELIST_MAX_PER_DAY))


async def _echte_datums_ophalen(db) -> None:
    """Geïmporteerde advertenties op hun echte Marktplaats-datum zetten.

    Bij het importeren zetten we listed_at op vandaag, want de datum stond er niet
    bij. Voor het herplaatsen is dat de verkeerde klok: Marktplaats rekent vanaf de
    dag dat de advertentie er echt op kwam en gooit hem na dertig dagen weg. Wie
    zijn voorraad importeert ziet er bij ons dus splinternieuw uit terwijl de helft
    bijna verloopt — en die advertenties zijn weg voordat wij ze oppakken.

    Draait elke ronde opnieuw en overschrijft steeds met dezelfde waarde: het is
    een correctie, geen eenmalige migratie, dus er valt niets stuk als hij een keer
    niet lukt. Marktplaats weet het beter dan wij, altijd.
    """
    try:
        from backend.services.mp_datums import corrigeer_listed_at
    except Exception as e:  # noqa: BLE001 — nooit de hele ronde laten vallen
        logger.warning("echte datums overgeslagen: %s", e)
        return
    try:
        rijen = (db.table("listings")
                 .select("id,item_id,platform_listing_id")
                 .eq("platform", "marktplaats").eq("status", "active")
                 .limit(4000).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("echte datums: advertenties niet gelezen: %s", e)
        return
    if not rijen:
        return
    per_verkoper: dict[str, list[dict]] = {}
    for r in rijen:
        try:
            item = (db.table("items").select("user_id,title")
                    .eq("id", r["item_id"]).single().execute().data or {})
        except Exception:  # noqa: BLE001
            continue
        if item.get("user_id"):
            per_verkoper.setdefault(item["user_id"], []).append(
                {**r, "titel": item.get("title") or ""})
    for user_id, lijst in per_verkoper.items():
        titels = [x["titel"] for x in lijst if x["titel"]][:8]
        nummers = {str(x.get("platform_listing_id") or "").strip()
                   for x in lijst if x.get("platform_listing_id")}
        try:
            await corrigeer_listed_at(db, user_id, titels, nummers)
        except Exception as e:  # noqa: BLE001
            logger.warning("echte datums voor %s mislukt: %s", user_id, e)


async def relist_expiring_marktplaats():
    """
    Queue a new 'create' job for every Marktplaats listing that has been
    active for >= MARKTPLAATS_EXPIRY_DAYS days and hasn't been re-queued yet.
    Marks the old listing 'relisting' so this function won't double-trigger.
    """
    from datetime import datetime, timezone, timedelta
    db = get_db()

    # Elke verkoper stelt zelf in na hoeveel dagen een advertentie opnieuw
    # geplaatst wordt. Hier wordt met de RUIMSTE instelling opgehaald — anders
    # zou wie op 7 dagen staat pas na 27 dagen aan de beurt komen — en verderop
    # per advertentie tegen de eigen instelling van de eigenaar gelegd.
    from backend.services.instellingen import (RELIST_DAGEN_MIN,
                                               RELIST_DAGEN_STANDAARD,
                                               alle_relist_dagen)
    dagen_per_verkoper = alle_relist_dagen()
    await _echte_datums_ophalen(db)
    from backend.services.instellingen import lees as _lees_instellingen
    _auto_aan: dict[str, bool] = {}

    def auto_relist_aan(uid: str) -> bool:
        if uid not in _auto_aan:
            _auto_aan[uid] = bool(_lees_instellingen(uid).get("auto_relist", True))
        return _auto_aan[uid]

    ruimste = min([RELIST_DAGEN_STANDAARD, *dagen_per_verkoper.values()] or
                  [RELIST_DAGEN_STANDAARD])
    ruimste = max(RELIST_DAGEN_MIN, ruimste)
    nu = datetime.now(timezone.utc)
    cutoff = (nu - timedelta(days=ruimste)).isoformat()
    listings_resp = (
        db.table("listings")
        .select("*")
        .eq("platform", "marktplaats")
        .eq("status", "active")
        .lt("listed_at", cutoff)
        # Oudste eerst. Wie het langst wacht is het dichtst bij de 30 dagen
        # waarop Marktplaats de advertentie zelf weggooit, dus die heeft voorrang.
        .order("listed_at")
        .execute()
    )

    if not listings_resp.data:
        return

    # NOOIT ALLES OP EEN DAG.
    #
    # Dit zette een baan klaar voor elke advertentie die ouder was dan 27 dagen,
    # zonder limiet en zonder spreiding. Gemeten geval 18-08-2026: een verkoper
    # importeerde 619 advertenties op twee dagen, dus op 13 en 14 september zouden
    # er 125 en 494 tegelijk verwijderd en opnieuw geplaatst worden. Op een
    # account waar hij drie jaar aan gebouwd heeft.
    #
    # Dat is precies het patroon waar Marktplaats op let, en het is ook nog eens
    # in tegenspraak met de handmatige verversknop, die bewust op 3 per dag staat.
    # Hier hoort dezelfde terughoudendheid.
    #
    # De grens ligt hoger dan bij handmatig verversen, en met opzet: dit is geen
    # extra oppepper maar het redden van een advertentie die anders vanzelf
    # verdwijnt. Zie _dagelijkse_relist_grens voor hoe hij meeschaalt.
    vandaag = datetime.now(timezone.utc).date().isoformat()
    per_verkoper: dict[str, int] = {}
    for row in (db.table("jobs")
                .select("user_id")
                .eq("platform", "marktplaats")
                .eq("action", "create")
                .gte("created_at", vandaag)
                .execute().data or []):
        per_verkoper[row["user_id"]] = per_verkoper.get(row["user_id"], 0) + 1
    grens_per_verkoper: dict[str, int] = {}

    logger.info("Auto-relist: %s expiring Marktplaats listings, spread per seller",
                len(listings_resp.data))

    for listing in listings_resp.data:
        try:
            item_resp = db.table("items").select("*").eq("id", listing["item_id"]).single().execute()
            if not item_resp.data:
                continue
            item = item_resp.data

            eigenaar = item["user_id"]

            # Advertenties uit Admarkt (zakelijk Marktplaats) hebben geen eigen
            # advertentie-adres: het enige adres dat Admarkt teruggeeft is de
            # webwinkel van de verkoper. Zonder dat adres kunnen we de oude niet
            # weghalen — en een Admarkt-campagne verloopt ook niet vanzelf na 30
            # dagen. Een "herplaatsing" zou daar dus geen verversing zijn maar een
            # tweede, gelijke advertentie naast de eerste. Precies waar
            # Marktplaats accounts voor blokkeert. Overslaan dus.
            if not (listing.get("platform_listing_url") or "").strip():
                logger.info("Auto-relist overgeslagen voor listing %s: geen advertentie-adres "
                            "(Admarkt-import verloopt niet en kan niet worden vervangen)",
                            listing["id"])
                continue

            # Uitgezet door de verkoper zelf: dan gebeurt er niets, ook niet
            # stilletjes. De advertentie blijft gewoon op 'active' staan.
            if not auto_relist_aan(eigenaar):
                continue

            # Is deze advertentie voor DEZE verkoper al oud genoeg? De query
            # hierboven haalde ruim op; dit is de eigen instelling.
            eigen_dagen = dagen_per_verkoper.get(eigenaar, _MARKTPLAATS_EXPIRY_DAYS)
            geplaatst = listing.get("listed_at")
            if geplaatst:
                try:
                    toen = datetime.fromisoformat(str(geplaatst).replace("Z", "+00:00"))
                    if toen.tzinfo is None:
                        toen = toen.replace(tzinfo=timezone.utc)
                    if (nu - toen).days < eigen_dagen:
                        continue
                except ValueError:
                    pass          # onleesbare datum: laat de ruime query beslissen

            # NIET ALSNOG EEN HALF JAAR INHALEN.
            #
            # Zodra de echte Marktplaats-datum bekend is, blijkt een geïmporteerde
            # voorraad vaak in één klap "te oud". Gemeten 20-08-2026 bij Jaap:
            # 959 van zijn 1.222 advertenties zijn 25 dagen of ouder, waarvan er
            # 236 al 45 tot 60 dagen online staan — en die staan er dus gewoon
            # nog, ze verlopen kennelijk niet op het schema dat wij aannemen.
            # Zonder deze rem zou Omnivaleur er vanaf morgen 62 per dag gaan
            # verwijderen en opnieuw plaatsen, vijftien dagen lang, met alle
            # reacties en vragen die eraan hangen. Dat is geen redding meer maar
            # een ingreep waar de verkoper zelf over hoort te beslissen.
            #
            # Automatisch herplaatsen pakt de oudste eerst, en niet meer dan de
            # dagelijkse grens per verkoper. Zo wordt een geïmporteerde voorraad
            # in de loop van weken bijgewerkt in plaats van in één dag — zonder
            # dat de oudste, die het eerst verdwijnt, wordt overgeslagen.
            if geplaatst:
                try:
                    toen = datetime.fromisoformat(str(geplaatst).replace("Z", "+00:00"))
                    if toen.tzinfo is None:
                        toen = toen.replace(tzinfo=timezone.utc)
                    # HIER STOND EEN REM DIE PRECIES DE VERKEERDE OVERSLOEG.
                    #
                    # Alles ouder dan de eigen termijn plus veertien dagen werd
                    # overgeslagen, om te voorkomen dat een pas geïmporteerde
                    # voorraad in één klap "te oud" zou zijn. Het gevolg was het
                    # tegenovergestelde van de bedoeling: juist de advertenties
                    # die het dichtst bij verwijdering staan bleven liggen.
                    # Gemeten bij Jaap (21-08-2026): de ronde verversde
                    # advertenties van 17 juli, terwijl die van 14 mei — de
                    # oudste, en dus de eerste die Marktplaats weggooit — er nooit
                    # doorheen kwamen.
                    #
                    # De rem is niet nodig: de dagelijkse grens per verkoper
                    # (_dagelijkse_relist_grens) spreidt het al, en de rij staat
                    # op oudste eerst. Zonder deze uitzondering komt de oudste dus
                    # gewoon als eerste aan de beurt — precies wat een verkoper
                    # verwacht en wat zijn advertenties redt.
                    pass
                except ValueError:
                    pass

            if eigenaar not in grens_per_verkoper:
                grens_per_verkoper[eigenaar] = _dagelijkse_relist_grens(db, eigenaar)
            if per_verkoper.get(eigenaar, 0) >= grens_per_verkoper[eigenaar]:
                # Morgen weer. De advertentie blijft op 'active' staan, dus hij
                # komt de volgende ronde vanzelf opnieuw langs — en omdat we op
                # listed_at sorteren staat hij dan vooraan.
                continue
            per_verkoper[eigenaar] = per_verkoper.get(eigenaar, 0) + 1

            # EERST WEG, DAN OPNIEUW. Hier stond alleen de "create" — op de
            # aanname dat Marktplaats de oude advertentie na 30 dagen zelf al
            # had weggegooid. Die aanname is aantoonbaar onjuist: bij Jaap
            # stonden advertenties van 45 tot 60 dagen oud gewoon nog online.
            # Gevolg: elke automatische herplaatsing zette er een tweede naast.
            # Gemeten op 21-08-2026: 61 nieuwe advertenties, nul verwijderingen,
            # en zijn account groeide van 1.220 naar ongeveer 1.300 — precies het
            # dubbel-plaatsen waar Marktplaats accounts voor blokkeert.
            #
            # refresh_listing doet het wél goed: het zet een verwijderopdracht
            # klaar en plant de nieuwe plaatsing erachteraan, en /jobs/pending
            # laat die tweede stap alleen door als de eerste écht gelukt is.
            from backend.services.relist import refresh_listing, RefreshError
            try:
                await refresh_listing(listing["item_id"], "marktplaats",
                                      item["user_id"], "relist",
                                      eigen_quotum=True)
            except RefreshError as e:
                # Dagquotum vol of nog in afkoeling: morgen weer. De advertentie
                # blijft op 'active' staan en komt vanzelf opnieuw langs.
                logger.info("Auto-relist overgeslagen voor listing %s: %s",
                            listing["id"], e)
                per_verkoper[eigenaar] = max(0, per_verkoper.get(eigenaar, 1) - 1)
                continue

            logger.info(f"Queued relist job for item {listing['item_id']} (listing {listing['id']})")
        except Exception as e:
            logger.error(f"Failed to queue relist for listing {listing['id']}: {e}")


async def _find_shopify_product_id_by_sku(sku: str) -> str | None:
    """
    Locate a Shopify product by variant SKU, walking every page of the catalog.

    The previous version read products.json with limit=50 and gave up — on any
    store with more than 50 products a listing whose product id we'd lost was
    simply never found, so the delist reported "couldn't delete" (or nothing at
    all) while the product stayed live in the shop. Shopify caps a page at 250
    and hands out the next page via a cursor in the Link header.
    """
    import httpx
    import re as _re
    from backend.config import settings
    from backend.platforms.shopify_importer import _get_token

    token = await _get_token()
    url = f"https://{settings.shopify_store}/admin/api/2024-10/products.json"
    params: dict = {"limit": 250, "fields": "id,variants"}
    headers = {"X-Shopify-Access-Token": token}

    async with httpx.AsyncClient(timeout=20) as c:
        for _ in range(40):  # 40 x 250 = 10k products — far beyond any real shop
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            for p in r.json().get("products", []):
                if any(v.get("sku") == sku for v in p.get("variants", [])):
                    return str(p["id"])
            # Cursor pagination: Link: <https://…page_info=xyz>; rel="next"
            link = r.headers.get("link") or r.headers.get("Link") or ""
            nxt = _re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not nxt:
                return None
            url, params = nxt.group(1), {}
    return None


async def _delist_one(listing: dict):
    db = get_db()
    item_resp = db.table("items").select("user_id").eq("id", listing["item_id"]).single().execute()
    item_user_id = item_resp.data["user_id"] if item_resp.data else None
    creds_resp = (
        db.table("platform_credentials")
        .select("*")
        .eq("user_id", item_user_id)
        .eq("platform", listing["platform"])
        .execute()
    )
    credentials = creds_resp.data[0] if creds_resp.data else {}

    try:
        platform = get_platform(listing["platform"])
        # platform_offer_id is an eBay-only concept (Inventory API offers). Using it
        # as a fallback for every platform meant a stray value on a Shopify row would
        # be sent to Shopify as a product id, which 404s and reads as "delete failed".
        delete_id = (
            listing.get("platform_offer_id") if listing["platform"] == "ebay" else None
        ) or listing.get("platform_listing_id")
        deleted = await platform.delete_listing(delete_id, credentials)
        if deleted is False:
            raise RuntimeError(f"delete_listing returned False for {listing['platform']} listing {listing['platform_listing_id']}")
        db.table("listings").update({
            "status": "delisted",
        }).eq("id", listing["id"]).execute()
        _log_event(listing["id"], "delisted", {})
    except Exception as e:
        logger.error(f"Delist failed for {listing['id']}: {e}")
        _log_event(listing["id"], "error", {"error": str(e)})
        raise


# ── Price propagation ──────────────────────────────────────────────────────
# Changing a price used to write nothing but the items row, so every "Apply"
# in Stale stock and every bulk reprice was invisible to buyers: the dashboard
# said €19.99 while all six channels kept showing the old price. Anything that
# writes a price now goes through here.

# Platforms whose price we can actually change today.
#   ebay/shopify — direct API call.
#   vinted       — queued as an extension edit job.
# Marktplaats, 2dehands and Facebook have no edit automation at all yet, so
# they are reported as "unsupported" rather than silently skipped.
_PRICE_SYNC_API = {"ebay", "shopify"}
_PRICE_SYNC_EXTENSION = {"vinted"}


async def sync_price_to_platforms(item_id: str, user_id: str) -> list[dict]:
    """Push the item's current price to every platform it is live on.

    Returns one result per live listing: status is 'updated', 'queued',
    'unsupported' or 'error'. Never raises — a failing channel must not undo
    the price change or block the others.
    """
    db = get_db()
    item = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).single().execute().data
    if not item:
        return []

    listings = (
        db.table("listings").select("*")
        .eq("item_id", item_id)
        .in_("status", ["active", "hidden"])
        .execute().data or []
    )
    if not listings:
        return []

    def _price_for(platform: str) -> float | None:
        # Mirror _pick() in publish_to_platforms: a per-platform price override
        # wins over the base price, so syncing never overwrites a price the user
        # deliberately set for one channel.
        field = _PLATFORM_PRICE_FIELD_GLOBAL.get(platform)
        raw = item.get(field) if field else None
        if raw in (None, ""):
            raw = item.get("price")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    results: list[dict] = []
    api_listings = [l for l in listings if l["platform"] in _PRICE_SYNC_API]
    creds_by_platform: dict[str, dict] = {}
    if api_listings:
        creds_resp = (
            db.table("platform_credentials").select("*")
            .eq("user_id", user_id)
            .in_("platform", sorted({l["platform"] for l in api_listings}))
            .execute()
        )
        creds_by_platform = {c["platform"]: c for c in (creds_resp.data or [])}

    for listing in listings:
        platform = listing["platform"]
        price = _price_for(platform)
        if price is None:
            results.append({"platform": platform, "status": "error", "error": "No usable price on this item"})
            continue

        if platform in _PRICE_SYNC_EXTENSION:
            # The extension owns Vinted's edit page. _price_update tells the
            # content script this refresh is specifically about the price —
            # a plain content_refresh deliberately leaves the price alone.
            db.table("jobs").insert({
                "user_id": user_id,
                "item_id": item_id,
                "platform": platform,
                "action": "content_refresh",
                "status": "pending",
                "payload": {
                    **item,
                    "price": price,
                    "platform_listing_id": listing.get("platform_listing_id"),
                    "platform_listing_url": listing.get("platform_listing_url"),
                    "_price_update": True,
                },
            }).execute()
            results.append({"platform": platform, "status": "queued",
                            "message": "Price edit queued — Chrome extension will apply it"})
            continue

        if platform not in _PRICE_SYNC_API:
            results.append({
                "platform": platform, "status": "unsupported",
                "message": f"{platform} has no price-edit automation yet — change it there by hand",
            })
            continue

        try:
            plat = get_platform(platform)
            if platform == "ebay":
                await plat.update_listing_price(
                    listing.get("platform_offer_id") or "", price,
                    creds_by_platform.get(platform, {}), sku=item.get("sku") or item["id"],
                )
            else:
                await plat.update_listing_price(
                    listing.get("platform_listing_id") or "", price,
                    creds_by_platform.get(platform, {}),
                )
            _log_event(listing["id"], "price_updated", {"price": price})
            results.append({"platform": platform, "status": "updated", "price": price})
        except Exception as e:
            msg = str(e) or f"{type(e).__name__}: {e!r}"
            logger.error("Price sync failed on %s for item %s: %s", platform, item_id, msg)
            _log_event(listing["id"], "error", {"error": f"price sync: {msg}"})
            results.append({"platform": platform, "status": "error", "error": msg})

    return results


# Same mapping publish_to_platforms uses; module-level so the price sync can't
# drift away from what publishing actually sends.
_PLATFORM_PRICE_FIELD_GLOBAL = {
    "marktplaats": "price_marktplaats",
    "2dehands": "price_2dehands",
    "vinted": "price_vinted",
    "ebay": "price_ebay",
    "shopify": "price_shopify",
}


def _log_event(listing_id: str, event_type: str, payload: dict):
    db = get_db()
    db.table("sync_events").insert({
        "listing_id": listing_id,
        "event_type": event_type,
        "payload": payload,
    }).execute()
