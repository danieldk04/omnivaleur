from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from backend.models import ListingCreate
from backend.database import get_db, fetch_all, naast_de_lus, execute_with_retry, IN_BROK
from backend.services.crosslist import publish_to_platforms, handle_item_sold, CrosslistValidationError
from backend.services.relist import (
    refresh_listing, refresh_stale_listings, renew_etsy_listing, relist_ended_ebay_listing,
    RefreshError, REFRESH_CAPABLE_PLATFORMS,
)
from backend.api.deps import get_current_user, require_active_subscription
from backend.services.verkoopdatum import als_datum, lees_verkoopdatum
from datetime import datetime, timezone
import re
import unicodedata
import logging

logger = logging.getLogger("omnivaleur.sold")

router = APIRouter(prefix="/listings", tags=["listings"])


def _parse_listing_id(platform: str, url: str) -> str | None:
    """
    Extract a platform's listing id from a listing URL the user pastes.
    Mirrors the regexes the extension already uses (background.js onUpdated
    auto-detect) so a hand-pasted URL yields the same id the extension would.
    Best-effort — returns None when nothing matches.
    """
    if not url:
        return None
    u = url.strip()
    p = (platform or "").lower()
    try:
        if p == "vinted":
            # /items/{id}-slug or bare /items/{id}
            m = re.search(r"/items/(\d+)", u)
            return m.group(1) if m else None
        if p in ("marktplaats", "2dehands"):
            # /v/listing/{digits}, m-prefixed id in path or query
            m = (re.search(r"/v/listing/(\d+)", u)
                 or re.search(r"/seller/view/(m\d+)", u)
                 or re.search(r"[?&](m\d{6,})", u)
                 or re.search(r"(m\d{6,})", u))
            return m.group(1) if m else None
        if p == "ebay":
            m = re.search(r"/itm/(\d+)", u)
            return m.group(1) if m else None
        if p == "shopify":
            # /products/{numeric-id} or /products/{handle}
            m = re.search(r"/products/(\d+)", u)
            if m:
                return m.group(1)
            m = re.search(r"/products/([a-z0-9][a-z0-9\-]*)", u, re.I)
            return m.group(1) if m else None
    except Exception:
        return None
    return None


def _user_item_ids(db, user_id: str) -> list[str]:
    """Return all item IDs belonging to this user. Paged: a plain select is
    silently cut off at the database's row limit, and every id that fell off the
    end took its listings with it."""
    return [r["id"] for r in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", user_id))]


def _listings_via_items(db, user_id: str, platform: str | None,
                        status: str | None) -> list[dict]:
    """Alle advertenties van deze verkoper in één vraag, titel en SKU inbegrepen.

    WAAROM DIT ER IS (01-09-2026, Egbert). De oude weg vroeg eerst alle item-id's
    op, hakte die in brokken van 200 en stelde per brok een aparte vraag, en deed
    dat daarna nóg een keer om bij elke advertentie de titel te zoeken. Bij zijn
    5.533 artikelen zijn dat ruim zeventig vragen achter elkaar binnen één
    verzoek. Gemeten op zijn echte gegevens: 17,9 seconden. Op de server, waar
    het langzamer gaat dan hier, is dat precies de aanroep die de gateway opgaf —
    het lege scherm en de tijdverloop-fout waar hij over belde.

    Postgres kent de band tussen een advertentie en zijn artikel al (de sleutel
    `listings_item_id_fkey`), dus die vraag kan in één keer: geef de advertenties
    wáár het artikel van deze verkoper is, en lever titel en SKU meteen mee.
    Zelfde uitkomst, zelfde velden: 1,5 seconde in plaats van 17,9.
    """
    def bouw():
        q = (db.table("listings")
             .select("*,items!inner(title,sku,user_id)")
             .eq("items.user_id", user_id))
        if platform:
            q = q.eq("platform", platform)
        if status:
            q = q.eq("status", status)
        return q

    rijen = fetch_all(bouw, page_size=1000)
    # De titel en SKU staan in een apart blokje omdat ze uit de andere tabel
    # komen; het dashboard en de extensie verwachten ze los op de advertentie.
    for l in rijen:
        it = l.pop("items", None) or {}
        l["title"] = it.get("title")
        l["sku"] = it.get("sku")
    return rijen


def _listings_per_brok(db, user_id: str, platform: str | None,
                       status: str | None) -> list[dict]:
    """De oude weg: per brok van 200 item-id's. Alleen nog als vangnet.

    Fetch every listing, in chunks and pages. The old single call asked for
    2000 rows in one go: PostgREST caps a response at its own max-rows limit
    and says nothing about it, so past that point the dashboard simply never
    saw those listings — items that were live on a platform showed up under
    "To list". A stable order is required, otherwise paging can repeat or skip
    rows.
    """
    item_ids = _user_item_ids(db, user_id)
    if not item_ids:
        return []

    def bouw(chunk):
        q = db.table("listings").select("*").in_("item_id", chunk)
        if platform:
            q = q.eq("platform", platform)
        if status:
            q = q.eq("status", status)
        return q

    listings: list[dict] = []
    for chunk_start in range(0, len(item_ids), 200):
        chunk = item_ids[chunk_start:chunk_start + 200]
        listings.extend(fetch_all(lambda c=chunk: bouw(c)))
    # Attach each listing's item title AND sku so the extension can match sold ads
    # for listings that have no platform_listing_id (hand-marked / unconfirmed).
    # De SKU is de betrouwbaarste sleutel: elke door ons geplaatste advertentie
    # begint met "(SKU)", terwijl de titel op het platform vertaald en afgekapt is.
    ids = list({l["item_id"] for l in listings if l.get("item_id")})
    if ids:
        items = []
        for i in range(0, len(ids), 200):
            brok = ids[i:i + 200]
            items.extend(fetch_all(lambda b=brok: db.table("items").select("id,title,sku").in_("id", b)))
        by_id = {it["id"]: it for it in items}
        for l in listings:
            it = by_id.get(l.get("item_id")) or {}
            l["title"] = it.get("title")
            l["sku"] = it.get("sku")
    return listings


def _mislukte_advertenties(db, user_id: str, platform: str,
                           item_id: str | None = None) -> list[dict]:
    """De mislukte advertenties van deze verkoper op dit kanaal, in ÉÉN vraag.

    WAAROM DIT ER IS (04-09-2026, Egbert). Het opruimen deed het nog op de oude
    manier: eerst alle item-id's ophalen, die in brokken van 200 hakken en per
    brok een aparte vraag stellen. Bij zijn 5.533 artikelen zijn dat 29 vragen
    achter elkaar binnen één verzoek, en geen van die 29 werd herkanst. Gemeten
    op zijn echte gegevens: 7,8 seconden en 29 vragen, tegen 0,2 seconde en één
    vraag langs dezelfde weg als `_listings_via_items` — met exact dezelfde 304
    rijen als uitkomst. Elke losse vraag is een kans dat Supabase de hergebruikte
    verbinding wegtrekt, en dát werd op zijn scherm een kale foutcode.
    """
    def bouw():
        q = (db.table("listings")
             .select("id,item_id,platform_listing_id,items!inner(user_id)")
             .eq("items.user_id", user_id)
             .eq("platform", platform).eq("status", "error"))
        if item_id:
            q = q.eq("item_id", item_id)
        return q

    rijen = fetch_all(bouw, page_size=1000)
    for r in rijen:
        r.pop("items", None)
    return rijen


@router.get("/")
def list_all_listings(
    limit: int = 200,
    platform: str = None,
    status: str = None,
    user_id: str = Depends(get_current_user),
):
    db = get_db()
    try:
        return _listings_via_items(db, user_id, platform, status)
    except Exception as e:  # noqa: BLE001
        # De snelle weg leunt op de sleutel tussen listings en items. Valt die
        # ooit weg, dan is een traag antwoord nog altijd oneindig veel beter dan
        # een verkoper die zijn advertenties kwijt is.
        logger.warning("advertentielijst via items mislukt (%s) — terug naar de oude weg", e)
        return _listings_per_brok(db, user_id, platform, status)


@router.post("/publish")
async def publish_listing(
    body: ListingCreate,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_active_subscription),
):
    try:
        results = await publish_to_platforms(body.item_id, body.platforms, user_id)
    except CrosslistValidationError as e:
        raise HTTPException(status_code=422, detail={"missing_fields": e.missing})
    return {"results": results}


@router.get("/item/{item_id}")
def get_listings_for_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    result = db.table("listings").select("*").eq("item_id", item_id).execute()
    return result.data


@router.post("/mark-active")
def mark_listing_active(body: dict, user_id: str = Depends(get_current_user)):
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform required")
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Optional link-establishment: the user can paste the live listing's URL (and/or
    # id) so auto-delist can locate it later. Parse the id from the URL when only a
    # URL is given. Both stay optional so the plain "mark active" call is unchanged.
    listing_url = (body.get("platform_listing_url") or "").strip() or None
    listing_id = (body.get("platform_listing_id") or "").strip() or None
    if listing_url and not listing_id:
        listing_id = _parse_listing_id(platform, listing_url)

    now = datetime.now(timezone.utc).isoformat()
    link_fields: dict = {}
    if listing_url:
        link_fields["platform_listing_url"] = listing_url
    if listing_id:
        link_fields["platform_listing_id"] = listing_id

    existing = db.table("listings").select("id").eq("item_id", item_id).eq("platform", platform).execute()
    if existing.data:
        db.table("listings").update({
            "status": "active",
            "error_message": None,
            "listed_at": now,
            **link_fields,
        }).eq("item_id", item_id).eq("platform", platform).execute()
    else:
        db.table("listings").insert({
            "item_id": item_id,
            "platform": platform,
            "status": "active",
            "listed_at": now,
            **link_fields,
        }).execute()

    # The user marked this listed by hand — so any still-open publish job for this
    # item+platform is done (the extension likely published it but couldn't confirm).
    # Settle it to "done" so the "extension is working" banner clears immediately and
    # the stale-claim sweep won't reset it to pending and re-open a tab.
    try:
        db.table("jobs").update({
            "status": "done",
            "done_at": now,
            "result": {"manual": "marked active by user"},
        }).eq("user_id", user_id).eq("item_id", item_id).eq("platform", platform) \
          .eq("action", "create").in_("status", ["pending", "claimed"]).execute()
    except Exception:
        pass

    # Return the updated listing row so the frontend can refresh (and confirm the
    # link was captured).
    row = (
        db.table("listings").select("*")
        .eq("item_id", item_id).eq("platform", platform)
        .limit(1).execute().data
    )
    listing = row[0] if row else None

    # Handmatig op "listed" zetten zonder link is precies waar het later misgaat:
    # zonder advertentie-id weet het dashboard niet wélke advertentie van dit item
    # is, dus kan hij hem bij verkoop niet automatisch van de andere platforms
    # halen. Daarom zetten we meteen een scan klaar: de extensie loopt de eigen
    # advertenties op dat platform langs en koppelt het juiste id/URL alsnog aan
    # dit item (op titel, of op de titel die wij zelf in het formulier zetten).
    linked = bool((listing or {}).get("platform_listing_id"))
    scan_queued = False
    if not linked:
        try:
            from backend.api.jobs import _queue_scan
            from backend.api.imports import SCANNABLE_PLATFORMS
            if platform in SCANNABLE_PLATFORMS:
                _queue_scan(db, user_id, platform)
                scan_queued = True
        except Exception as e:  # nooit fataal — de markering zelf is al gelukt
            logger.warning(f"mark-active: could not queue linking scan for {platform}: {e}")

    return {"ok": True, "listing": listing, "linked": linked, "scan_queued": scan_queued}


@router.post("/clear-error")
def clear_listing_errors(body: dict, user_id: str = Depends(get_current_user)):
    """Haal een mislukte publicatie van het scherm af.

    WAAROM DIT BESTAAT (03-09-2026, Egbert Brouwer / papas-plectrums)

    Zijn wachtrij voor 2dehands werd teruggenomen. Dat was terecht: 279
    opdrachten van elk drie en een halve minuut zijn zestien uur waarin hij
    verder niets kan. Maar elke teruggenomen opdracht liet een rode balk achter
    op de artikelrij, en die balken gaan alleen weg als er alsnog met succes
    wordt gepubliceerd. Hij keek dus tegen zes bladzijden rood aan, zonder een
    enkele knop om er iets mee te doen, en concludeerde: "Ik kom niet verder."

    Een advertentie die nooit is aangemaakt hoort geen mislukte advertentie te
    zijn maar een niet-geplaatste. Daarom verdwijnt de rij hier echt als er
    nooit een advertentienummer aan hing; hing dat er wel, dan blijft de rij
    staan en gaat alleen de foutmelding eraf.

    body: {platform, item_id?}  zonder item_id: alles wat op dit kanaal faalde.

    04-09-2026: het opzoeken gaat nu in één gekoppelde vraag in plaats van in
    29 losse (zie `_mislukte_advertenties`), elke schrijfactie wordt herkanst,
    en gaat er tóch iets stuk dan staat er in het antwoord wát er stukging.
    """
    platform = (body.get("platform") or "").strip()
    if not platform:
        raise HTTPException(status_code=400, detail="platform required")
    item_id = (body.get("item_id") or "").strip() or None

    db = get_db()
    if item_id:
        eigen = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
        if not eigen.data:
            raise HTTPException(status_code=404, detail="Item not found")

    try:
        rijen = _mislukte_advertenties(db, user_id, platform, item_id)

        # Nooit een advertentienummer gehad? Dan is er niets geplaatst en is de
        # rij zelf onzin. Weg ermee, dan staat het artikel weer op "nog plaatsen".
        weg = [r["id"] for r in rijen if not r.get("platform_listing_id")]
        # Wel een advertentienummer: dat wordt alleen weggeschreven als het
        # platform de advertentie heeft aangemaakt en het nummer heeft
        # teruggegeven. Zo'n rij weggooien zou de link kwijtmaken die
        # auto-delist later nodig heeft, dus die blijft staan als gewone
        # actieve advertentie zonder foutmelding.
        houden = [r["id"] for r in rijen if r.get("platform_listing_id")]

        # execute_with_retry: Supabase trekt af en toe een hergebruikte
        # verbinding weg. Zonder herkansing is dat hier geen hik maar een
        # mislukte knop, en de klant ziet alleen een foutcode.
        for i in range(0, len(weg), IN_BROK):
            execute_with_retry(db.table("listings").delete().in_("id", weg[i:i + IN_BROK]))
        for i in range(0, len(houden), IN_BROK):
            execute_with_retry(db.table("listings").update({
                "status": "active", "error_message": None,
            }).in_("id", houden[i:i + IN_BROK]))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        # Geen naamloze 500 meer. Die kwam bij Egbert als "code F1F7E7" op zijn
        # scherm, en het logboek waar die code bij hoort was op dat moment al
        # volgelopen met een andere storing. Wat er misging hoort in het
        # antwoord zelf te staan.
        logger.exception("clear-error mislukte voor %s op %s", user_id, platform)
        raise HTTPException(status_code=502, detail=(
            f"Could not clear the failed {platform} publishes "
            f"({type(e).__name__}: {str(e)[:200]}). Nothing was removed from "
            f"{platform} itself. Reload the page and try again."))

    return {"ok": True, "cleared": len(rijen), "removed": len(weg)}


@router.post("/refresh")
async def refresh_one_listing(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Refresh a single listing. body: {item_id, platform, strategy: "content"|"relist", new_price?: number}
    "content" = safe in-place edit (price/photo-order nudge).
    "relist"  = legitimate delete + recreate, rate-limited and delayed to avoid a spam pattern.
    new_price is only applied for "relist" — e.g. accepting the 10-15% price-drop
    suggestion shown in the dashboard to improve the odds of a sale.
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    strategy = body.get("strategy", "content")
    new_price = body.get("new_price")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform required")
    if new_price is not None:
        try:
            new_price = float(new_price)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="new_price must be a number")
    try:
        result = await refresh_listing(item_id, platform, user_id, strategy, new_price=new_price)
        return result
    except RefreshError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        # Anything unexpected here (e.g. a schema mismatch) would otherwise bubble up
        # as a raw, non-JSON 500 page — the frontend's r.json() call then throws its
        # own confusing "Unexpected token" error instead of showing the real problem.
        #
        # Maar een weggevallen verbinding is geen storing om de verkoper mee lastig
        # te vallen met Python-taal. Jaap Kroon kreeg op 28-08-2026 letterlijk
        # "Refresh failed unexpectedly: EOF occurred in violation of protocol
        # (_ssl.c:2417)" op zijn scherm en kon daar niets mee — hij wist niet eens
        # of zijn advertentie nog online stond.
        from backend.database import _is_herstelbaar
        if _is_herstelbaar(e):
            logger.warning("Verversen viel weg op een verbindingsfout: %s", e)
            raise HTTPException(
                status_code=503,
                detail="The connection dropped, so nothing was changed and your "
                       "listing is still live. Please try again in a moment.",
            )
        raise HTTPException(status_code=500, detail=f"Refresh failed unexpectedly: {e}")


@router.post("/refresh-stale")
async def refresh_stale(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Bulk-refresh the oldest eligible listings on one platform.
    body: {platform, older_than_days?: 30, limit?: 5}
    Capped by the same per-user daily quota as single refreshes.
    """
    platform = body.get("platform")
    if not platform:
        raise HTTPException(status_code=400, detail="platform required")
    if platform not in REFRESH_CAPABLE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Refresh isn't available for {platform} yet")
    results = await refresh_stale_listings(
        user_id, platform,
        older_than_days=body.get("older_than_days", 30),
        limit=min(body.get("limit", 5), 20),
    )
    return {"results": results}


@router.post("/renew-etsy")
async def renew_etsy(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Etsy's official renewal action — charges the normal Etsy listing fee.
    Not part of the shared refresh quota (real money, user-initiated per click).
    body: {item_id}
    """
    item_id = body.get("item_id")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    try:
        return await renew_etsy_listing(item_id, user_id)
    except RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/relist-ended-ebay")
async def relist_ended_ebay(body: dict, user_id: str = Depends(require_active_subscription)):
    """
    Republish an ENDED eBay listing via eBay's own relist mechanism.
    Refuses to run on a still-active listing (eBay duplicate-listing policy).
    body: {item_id}
    """
    item_id = body.get("item_id")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    try:
        return await relist_ended_ebay_listing(item_id, user_id)
    except RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Waarom een advertentie als "mogelijk verkocht" is aangemerkt. De verkoper krijgt
# deze zin letterlijk te zien, want het verschil bepaalt hoe zeker het is:
# een label op de pagina is bewijs, een verdwenen advertentie is een aanwijzing.
#
# LET OP: deze teksten mogen de woorden "relist", "delist" of "still live" niet
# bevatten. Het herplaats-overzicht in het dashboard herkent een mislukte
# herplaatsing aan die woorden in dit veld, en zou deze advertenties dan als
# mislukte herplaatsing tonen.
VERDENKING_REDENEN = {
    "label": "Mogelijk verkocht: de advertentiepagina toont zelf 'verkocht' of 'gereserveerd'.",
    "weg": "Mogelijk verkocht: de advertentie is niet meer op het platform te vinden. "
           "Let op — op Marktplaats verdwijnt een gratis advertentie ook vanzelf na 30 dagen.",
    "verdwenen_te_jong":
        "Mogelijk verkocht: de advertentie was al van het platform af toen we hem "
        "voor het herplaatsen wilden weghalen, en hij was nog te jong om vanzelf te "
        "verlopen. Er is dus niets opnieuw geplaatst. Verkocht? Bevestig het hier — "
        "dan gaat hij ook van de andere kanalen af. Niet verkocht? Dan gaat deze "
        "advertentie naar het archief en kun je hem met één klik opnieuw plaatsen.",
}
VERDENKING_STANDAARD = VERDENKING_REDENEN["weg"]


@router.post("/possibly-sold")
def possibly_sold(body: dict, user_id: str = Depends(get_current_user)):
    """Advertenties die verkocht LIJKEN, ter bevestiging door de verkoper.

    Waarom niet meteen afmelden: op Marktplaats is een verkoop meestal onzichtbaar
    voor Marktplaats zelf — verkoop je met de hand, dan komt er nooit een
    "verkocht" op je advertentie. Wat overblijft is dat de advertentie verdwenen
    is, en dát betekent daar óók "verlopen na 30 dagen". Zouden we daarop
    afgaan, dan haalden we een nog levend artikel van Vinted, eBay en de webshop
    af, en dat is onherstelbaar werk voor de verkoper. Daarom wordt het gemeld en
    beslist hij.

    De extensie levert alleen regels aan die haar eigen drempel hebben gehaald:
    een label op de advertentiepagina (bewijs, meteen), of twee aparte rondes
    minstens een half uur uit elkaar waarin de advertentie niet te vinden was.

    Body: {listings: [{item_id, platform, platform_listing_id?, title?, reden?}]}
    """
    db = get_db()
    regels = (body or {}).get("listings") or []
    gemarkeerd = 0
    nu = datetime.now(timezone.utc).isoformat()
    for r in regels[:200]:
        item_id = r.get("item_id")
        platform = r.get("platform")
        if not item_id or not platform:
            continue
        # Alleen eigen items, en alleen advertenties die nu nog als levend gelden.
        # 'sold' staat er bewust niet bij: een al bevestigde verkoop mag nooit
        # terugvallen naar een vraag.
        eigen = (db.table("items").select("id").eq("id", item_id)
                 .eq("user_id", user_id).limit(1).execute().data or [])
        if not eigen:
            continue
        reden = VERDENKING_REDENEN.get(str(r.get("reden") or ""), VERDENKING_STANDAARD)
        velden = {"status": "sold_unconfirmed", "error_message": reden, "last_checked": nu}

        def _markeer(f):
            return (db.table("listings").update(f)
                    .eq("item_id", item_id).eq("platform", platform)
                    .in_("status", ["active", "hidden", "relisting"]).execute())
        try:
            _markeer(velden)
        except Exception as e:  # noqa: BLE001 — de melding mag nooit op een veld stuklopen
            logger.warning("[sold] kon reden niet meeschrijven voor %s/%s: %s", item_id, platform, e)
            _markeer({"status": "sold_unconfirmed"})
        gemarkeerd += 1
    logger.info("[sold] %s advertentie(s) als mogelijk verkocht gemarkeerd voor %s",
                gemarkeerd, user_id)
    return {"marked": gemarkeerd}


# Statussen waarin een artikel nog "in de verkoop" is. Alleen dán boeken we een
# verkoop uit de berichtenlijst: een gesprek houdt zijn verkocht-badge voor
# altijd, dus zonder deze grens zou elke ronde dezelfde verkopen van maanden
# geleden opnieuw melden — en een artikel dat de verkoper bewust heeft
# gearchiveerd alsnog als omzet van vandaag in de boeken zetten.
IN_DE_VERKOOP = ("active", "relisting", "hidden", "pending", "sold_unconfirmed")


def _sku_uit_titel(titel: str) -> str | None:
    """Het nummer waarmee elke door deze app geplaatste titel begint: "(1308) ..."."""
    m = re.match(r"\s*\((\d{1,6})\)", titel or "")
    return m.group(1) if m else None


@router.post("/sold-from-messages")
def sold_from_messages(body: dict, background_tasks: BackgroundTasks,
                       user_id: str = Depends(get_current_user)):
    """Verkopen die Marktplaats alleen in de BERICHTENLIJST prijsgeeft.

    WAAROM DIT ER IS (01-09-2026, Daniel). Op de advertentie zelf komt nooit een
    "verkocht" te staan als je met de hand verkoopt — jij haalt de advertentie
    weg en meer ziet Marktplaats niet. Maar op het GESPREK met de koper zet
    Marktplaats wél een groene "Verkocht!"-badge. Dat is het enige plek waar het
    platform een handmatige verkoop hardop bevestigt, en het is ook precies hoe
    Daniel het zelf nakijkt. De extensie opent die pagina toch al elk kwartier
    voor het tellen van berichten, dus dit kost geen extra bezoek.

    Dit is bewijs, geen aanwijzing: hier wordt dus wél geboekt en niet gevraagd.
    Drie grenzen houden dat veilig:

    1. De extensie meldt alleen een LOS labeltje dat exact "verkocht" is, nooit
       het woord uit een berichtvoorbeeld.
    2. De sleutel is het nummer voor de titel — "(1308)" — en dat moet bij precies
       één artikel van deze verkoper horen. Twee treffers betekent overslaan:
       liever niets boeken dan de verkeerde verkoop.
    3. Alleen artikelen die nog ergens te koop staan. Een badge blijft eeuwig op
       een oud gesprek staan; zonder deze grens zou elke ronde de hele
       verkoopgeschiedenis opnieuw als omzet van vandaag boeken.

    Body: {platform, sold: [{sku, title}]}
    """
    platform = (body or {}).get("platform")
    regels = (body or {}).get("sold") or []
    if platform not in ("marktplaats", "2dehands"):
        raise HTTPException(status_code=400, detail="platform must be marktplaats or 2dehands")

    db = get_db()
    eigen = fetch_all(lambda: db.table("items").select("id,title").eq("user_id", user_id))
    per_sku: dict[str, list[str]] = {}
    for it in eigen or []:
        sku = _sku_uit_titel(it.get("title"))
        if sku:
            per_sku.setdefault(sku, []).append(it["id"])

    geboekt, overgeslagen = 0, 0
    for regel in regels[:200]:
        sku = str((regel or {}).get("sku") or "").strip()
        kandidaten = per_sku.get(sku) or []
        if len(kandidaten) != 1:
            # Nul: een advertentie die niet uit deze app komt (of van een ander
            # account). Twee of meer: dubbel nummer, dus niet te herleiden.
            if kandidaten:
                logger.info("[sold] berichten: nummer %s hoort bij %d artikelen — overgeslagen",
                            sku, len(kandidaten))
            overgeslagen += 1
            continue
        item_id = kandidaten[0]

        rijen = (db.table("listings").select("status,platform")
                 .eq("item_id", item_id).execute().data or [])
        if any(r.get("status") == "sold" for r in rijen):
            overgeslagen += 1            # al geboekt, badge blijft eeuwig staan
            continue
        if not any(r.get("status") in IN_DE_VERKOOP for r in rijen):
            overgeslagen += 1            # staat nergens meer te koop
            continue

        logger.info("[sold] berichten: verkocht-badge op %s (%s) → boeken op %s",
                    sku, item_id, platform)
        background_tasks.add_task(handle_item_sold, item_id, platform, None)
        geboekt += 1

    logger.info("[sold] berichten (%s): %d geboekt, %d overgeslagen van %d melding(en)",
                platform, geboekt, overgeslagen, len(regels))
    return {"booked": geboekt, "skipped": overgeslagen}


@router.post("/possibly-sold/answer")
def answer_possibly_sold(body: dict, background_tasks: BackgroundTasks,
                         user_id: str = Depends(get_current_user)):
    """Het antwoord van de verkoper op "is dit verkocht?".

    Twee uitkomsten, allebei definitief voor deze advertentie:

    - verkocht=true  → de normale verkoopafhandeling: geboekt in Analytics en van
      alle ANDERE kanalen afgehaald. Precies wat de Sold-knop doet.
    - verkocht=false → de advertentie staat niet meer op het platform maar is niet
      verkocht (verlopen, of zelf weggehaald). Dan hoort hij in het archief, niet
      op "live". Zo blijft de vraag ook niet terugkomen: de verkoopcontrole kijkt
      alleen naar actieve advertenties.

    Body: {item_id, platform, verkocht: bool, sold_price?}
    """
    item_id = (body or {}).get("item_id")
    platform = (body or {}).get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()
    owned = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Item not found")

    rij = (db.table("listings").select("id,status")
           .eq("item_id", item_id).eq("platform", platform)
           .eq("status", "sold_unconfirmed").limit(1).execute().data or [])
    if not rij:
        raise HTTPException(status_code=404, detail="No listing awaiting confirmation for this item on that platform")

    if body.get("verkocht"):
        prijs = body.get("sold_price")
        try:
            prijs = None if prijs in (None, "") else round(float(str(prijs).replace(",", ".")), 2)
        except (TypeError, ValueError):
            prijs = None
        # De datum is die van vandaag: wanneer het precies verkocht is weet
        # niemand hier. In Analytics is de datum aan te klikken en te corrigeren.
        logger.info("[sold] bevestigd door de verkoper: item=%s platform=%s prijs=%s", item_id, platform, prijs)
        background_tasks.add_task(handle_item_sold, item_id, platform, prijs)
        return {"ok": True, "status": "sold"}

    db.table("listings").update({"status": "delisted", "error_message": None})         .eq("id", rij[0]["id"]).execute()
    logger.info("[sold] niet verkocht volgens de verkoper: item=%s platform=%s → archief", item_id, platform)
    return {"ok": True, "status": "delisted"}


@router.post("/sold")
def mark_sold(item_id: str, platform: str, background_tasks: BackgroundTasks, sold_price: float | None = None, dry_run: bool = False, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")

    # dry_run = a zero-side-effect preview: touches NOTHING (no sold flag, no delist
    # jobs), just reports which other platforms a real run WOULD delist. Lets the
    # user rehearse the Sold button safely — nothing gets removed anywhere.
    if dry_run:
        others = (
            db.table("listings")
            .select("platform,status")
            .eq("item_id", item_id)
            .in_("status", ["active", "relisting"])
            .neq("platform", platform)
            .execute()
        )
        would_delist = sorted({l["platform"] for l in (others.data or [])})
        logger.info("[sold] DRY-RUN item_id=%s platform=%s would_delist=%s", item_id, platform, would_delist)
        return {"status": "dry_run", "would_mark_sold": platform, "would_delist": would_delist}

    logger.info("[sold] POST /sold item_id=%s platform=%s sold_price=%s -> delist triggered", item_id, platform, sold_price)
    background_tasks.add_task(handle_item_sold, item_id, platform, sold_price)
    return {"status": "delist_triggered"}


@router.post("/sold-price")
def set_sold_price(body: dict, user_id: str = Depends(get_current_user)):
    """
    Set/correct the amount an already-sold listing actually went for. Used from
    the Analytics "Sales breakdown" so revenue/profit reflect the real sale
    price instead of the asking price (items rarely sell at asking on
    Vinted/Marktplaats). Pass sold_price = null to clear it back to "estimate".
    Body: {item_id, platform, sold_price}.
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    raw = body.get("sold_price")
    if raw in (None, ""):
        sold_price = None
    else:
        try:
            sold_price = round(float(raw), 2)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="sold_price must be a number")
        if sold_price < 0:
            raise HTTPException(status_code=400, detail="sold_price can't be negative")

    db = get_db()
    # Scope to the caller's own item (listings has no user_id column).
    owned = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Item not found")

    res = (
        db.table("listings")
        .update({"sold_price": sold_price})
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("status", "sold")
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="No sold listing found for this item on that platform")
    return {"ok": True, "sold_price": sold_price}


@router.post("/sold-date")
def set_sold_date(body: dict, user_id: str = Depends(get_current_user)):
    """
    De verkoopdatum van een al verkochte advertentie bijstellen.

    Nodig omdat wij een verkoop soms pas later opmerken. Herkennen we de datum
    op de bestellingenpagina van het platform niet, dan staat er de dag waarop
    wij hem zagen — en die kan er weken naast zitten. Zonder deze knop kan de
    verkoper dat nooit rechtzetten en blijft zijn omzetgrafiek scheef staan.

    Body: {item_id, platform, sold_at}  (ISO-datum, "2026-08-17")
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    datum = lees_verkoopdatum(body.get("sold_at"))
    if datum is None:
        raise HTTPException(status_code=400,
                            detail="sold_at must be a real date, no later than today")

    db = get_db()
    owned = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Item not found")

    res = (
        db.table("listings")
        .update({"sold_at": datum.isoformat()})
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("status", "sold")
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="No sold listing found for this item on that platform")
    return {"ok": True, "sold_at": datum.isoformat()}


@router.post("/not-sold")
def mark_not_sold(body: dict, user_id: str = Depends(get_current_user)):
    """
    Undo a false "sold" — the Vinted wardrobe scan infers a sale when a listing
    disappears, which occasionally misfires (a temporary scrape gap, the item
    briefly hidden). This flips that listing back to 'active' and clears the
    sold_at/sold_price bookkeeping so it drops out of Analytics again.

    Scope is deliberately narrow: only the flagged listing is restored. We do NOT
    try to recreate listings on OTHER platforms that a genuine-looking sale may
    have delisted — those runs already happened and re-publishing is the user's
    explicit action (Crosslist), not something to silently auto-fire here.
    Body: {item_id, platform}.
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()
    owned = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not owned.data:
        raise HTTPException(status_code=404, detail="Item not found")

    def _restore(fields):
        return (
            db.table("listings")
            .update(fields)
            .eq("item_id", item_id)
            .eq("platform", platform)
            .eq("status", "sold")
            .execute()
        )

    fields = {"status": "active", "sold_at": None, "sold_price": None}
    try:
        res = _restore(fields)
    except Exception as e:
        # sold_price column not migrated yet — restore the rest so the fix still works.
        if "sold_price" in str(e):
            fields.pop("sold_price", None)
            res = _restore(fields)
        else:
            raise
    if not res.data:
        raise HTTPException(status_code=404, detail="No sold listing found for this item on that platform")
    return {"ok": True, "status": "active"}


def _parse_sku_price(raw_price):
    if raw_price in (None, ""):
        return None
    try:
        # Accept "€29,99", "29.99", 29.99 …
        s = str(raw_price).replace("€", "").replace(",", ".").strip()
        v = round(float(s), 2)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


@router.post("/reconcile-vinted-orders")
async def reconcile_vinted_orders(body: dict, user_id: str = Depends(get_current_user)):
    """
    Authoritative Vinted sale reconciliation from the seller's own
    "My orders → Sold" page (scraped by the extension). This is stronger than
    inferring a sale from a listing disappearing off the wardrobe: Vinted itself
    says the order sold, and the row carries the amount actually received.

    Each order carries the price paid, whether it's a genuine sale (`sold: true`)
    or a cancelled/refunded order (`sold: false`, ignored), and one of two keys:
    the item's SKU (the "(1234)" prefix some sellers put in their titles), or the
    order row's visible text.

    Safety: we only act on an EXACT, UNIQUE match scoped to the caller's own items
    — either the SKU, or the item's full title appearing verbatim in the order row.
    Anything ambiguous or unknown is skipped, never guessed, so a bad scrape can't
    mark the wrong item sold (and trigger its cross-platform delist).
    Already-sold items are only touched to backfill a missing sold_price or to
    correct a sale date that was stamped too late, so this endpoint can run every
    few minutes without re-queuing delist jobs.

    DE DATUM (30-08-2026). Deze pagina is een GESCHIEDENIS, geen melding: er
    staan ook bestellingen van weken terug op. Boekten we die met de klok van het
    moment van ontdekken, dan kreeg elke bestelling die we voor het eerst konden
    koppelen de datum van vandaag — en na een stille periode landde de omzet van
    weken op één dag. De extensie stuurt daarom de datum mee die Vinted zelf bij
    de bestelling toont; herkennen we die niet, dan verandert er niets aan een
    al geboekte datum en valt een nieuwe verkoop terug op nu.

    Body: {orders: [{sku?, text?, price, sold, date?}]}
    """
    orders = body.get("orders")
    if not isinstance(orders, list):
        raise HTTPException(status_code=400, detail="orders must be a list")

    db = get_db()
    # Titelsleutel voor verkopers zonder nummer in de titel: de volledige,
    # genormaliseerde itemtitel moet lettterlijk in de orderregel voorkomen, en
    # maar bij één item passen. Korte titels (< 12 tekens) tellen niet mee — die
    # zouden te makkelijk toevallig ergens in staan.
    def _norm(t: str) -> str:
        t = unicodedata.normalize("NFKD", t or "")
        t = "".join(c for c in t if not unicodedata.combining(c)).lower()
        t = re.sub(r"^\s*\([^)]{1,24}\)\s*", "", t)
        return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())

    own_items = fetch_all(
        lambda: db.table("items").select("id,title").eq("user_id", user_id))
    title_keys: list[tuple[str, str]] = []
    counts: dict[str, int] = {}
    for it in own_items:
        key = _norm(it.get("title"))
        if len(key) >= 12:
            title_keys.append((key, it["id"]))
            counts[key] = counts.get(key, 0) + 1
    title_keys = [(k, i) for k, i in title_keys if counts[k] == 1]

    def _match_by_text(text: str) -> str | None:
        hay = _norm(text)
        if not hay:
            return None
        hits = {item_id for key, item_id in title_keys if key in hay}
        return hits.pop() if len(hits) == 1 else None

    marked_sold = 0
    price_backfilled = 0
    date_fixed = 0
    zonder_datum = 0
    matched = 0
    unmatched_skus = []
    sold_orders = [o for o in orders if isinstance(o, dict) and o.get("sold")]
    logger.info("[sold] reconcile-vinted-orders: received %d orders (%d marked sold) for user=%s",
                len(orders), len(sold_orders), user_id)

    for o in orders:
        if not isinstance(o, dict) or not o.get("sold"):
            continue
        sku = str(o.get("sku") or "").strip()
        price = _parse_sku_price(o.get("price"))
        # De datum die Vinted bij de bestelling toont. De extensie levert de
        # kandidaten op volgorde van betrouwbaarheid aan (het datetime-attribuut
        # van de pagina eerst, de zichtbare regeltekst als laatste); de eerste die
        # met zekerheid te lezen is wint. Lukt geen enkele, dan blijft het None en
        # raken we een bestaande datum niet aan.
        datum = None
        for kandidaat in ([o.get("date")] if not isinstance(o.get("date"), list) else o.get("date")) + [o.get("text")]:
            datum = lees_verkoopdatum(kandidaat)
            if datum:
                break
        if datum is None:
            zonder_datum += 1

        item_id = None
        if sku:
            # Exact + UNIQUE match only. len != 1 → ambiguous/unknown → skip.
            items = (await naast_de_lus(lambda: db.table("items").select("id").eq("user_id", user_id).eq("sku", sku).execute())).data or []
            if len(items) == 1:
                item_id = items[0]["id"]
        if not item_id:
            item_id = _match_by_text(o.get("text") or "")
        if not item_id:
            unmatched_skus.append(sku or (str(o.get("text") or "")[:60]))
            continue
        matched += 1

        vinted_rows = (
            (await naast_de_lus(lambda: db.table("listings").select("id,status,sold_price")
            .eq("item_id", item_id).eq("platform", "vinted").execute())).data or []
        )
        sold_row = next((l for l in vinted_rows if l["status"] == "sold"), None)

        if sold_row:
            # Already recorded — just fill in the real price if we didn't have it.
            if price is not None and sold_row.get("sold_price") in (None, 0):
                try:
                    (await naast_de_lus(lambda: db.table("listings").update({"sold_price": price}).eq("id", sold_row["id"]).execute()))
                    price_backfilled += 1
                except Exception:
                    pass
            # En de datum terugzetten als die te laat is gestempeld. Alleen naar
            # VOREN in de tijd: ontdekken kan nooit eerder dan verkopen, dus een
            # eerdere datum is per definitie de betere. Hiermee repareren zich ook
            # de verkopen die eerder allemaal op de ontdekdag zijn beland.
            if datum is not None:
                staand = sold_row.get("sold_at")
                if not staand or datum < als_datum(staand):
                    try:
                        (await naast_de_lus(lambda: db.table("listings")
                         .update({"sold_at": datum.isoformat()}).eq("id", sold_row["id"]).execute()))
                        date_fixed += 1
                    except Exception:
                        pass
            continue

        # New sale. Ensure a Vinted listing row exists so it shows in analytics,
        # then run the canonical sold flow (records price + delists other platforms).
        if not vinted_rows:
            (await naast_de_lus(lambda: db.table("listings").insert({
                "item_id": item_id, "platform": "vinted", "status": "active",
            }).execute()))
        try:
            await handle_item_sold(item_id, "vinted", price, sold_at=datum)
            marked_sold += 1
        except Exception:
            pass

    # Alarm voor precies de storing die dit alles veroorzaakte: een ronde die in
    # één keer een stapel verkopen boekt ZONDER dat er ook maar één datum te
    # lezen was. Dan is de opmaak van Vinteds bestellingenpagina veranderd en
    # krijgen die verkopen allemaal de datum van vandaag. Zichtbaar in de logs,
    # zodat het niet weer weken onopgemerkt blijft.
    if marked_sold > 3 and zonder_datum >= marked_sold:
        logger.warning(
            "[sold] reconcile-vinted-orders: %d verkopen tegelijk geboekt zonder ENKELE leesbare "
            "datum (user=%s). Ze krijgen nu allemaal de datum van vandaag. Controleer de "
            "datumvelden op de Vinted-bestellingenpagina in de extensie.",
            marked_sold, user_id,
        )
    logger.info("[sold] reconcile-vinted-orders: matched=%d newly_sold=%d price_backfilled=%d "
                "date_fixed=%d zonder_datum=%d unmatched=%d unmatched_skus=%s",
                matched, marked_sold, price_backfilled, date_fixed, zonder_datum,
                len(unmatched_skus), unmatched_skus)
    return {"ok": True, "marked_sold": marked_sold, "price_backfilled": price_backfilled,
            "date_fixed": date_fixed, "zonder_datum": zonder_datum}
