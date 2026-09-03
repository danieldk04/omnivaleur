"""
Listing refresh ("bump old listings back up").

Every strategy here operates only within each platform's own rules — nothing
fakes engagement, spoofs bot traffic, or evades a platform's abuse detection.
Nothing is "guaranteed" to change ranking; it's rate-limited on purpose so it
can't look like scripted spam.

Per-platform, what's actually available differs a lot:

- "content" (Vinted only): light edit of an existing listing — shuffles the
  photos EXCEPT the first/main one (needs 3+ photos), price/title/description
  left untouched. Lowest impact, zero account risk. Not offered for
  Marktplaats/2dehands because there's no verified edit-page automation for
  them yet (see extension/content/marktplaats.js — it only implements the
  create/delete flow) and shipping an unverified DOM script here would be a
  reliability risk, not a safety one — it would just silently fail.

- "relist" (Vinted, Marktplaats, 2dehands): legitimate delete + re-create,
  the only way to get a new listing timestamp on platforms that sort
  "Newest" by creation date. Reuses the extension's existing, already-proven
  create/delete job flow — no new browser automation. Rate-limited per
  listing and per user/day, re-create step delayed with jitter.

- "renew" (Etsy only): Etsy's own official renewal mechanism — PATCH the
  listing's state to 'active', which Etsy's API documents as re-charging the
  listing fee and refreshing the listing. This is an intended platform
  feature, not a workaround, and is the only strategy here that's an actual
  first-party "refresh" action rather than an inferred side-effect of
  delete+recreate.

- "relist_ended" (eBay only): republish an offer that has ALREADY ended,
  via eBay's own offer/publish endpoint (their "relist" flow). This never
  touches a live listing — eBay's duplicate-listing policy prohibits two
  active listings for the same item, so bumping an active eBay listing is
  explicitly NOT implemented here.
"""
from __future__ import annotations
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta
from backend.database import get_db, fetch_all, naast_de_lus, IN_BROK
from backend.platforms import get_platform
from backend.services.crosslist import _exec

logger = logging.getLogger(__name__)

def _met_fabrikant(payload: dict, platform: str, user_id: str) -> dict:
    """Marktplaats en 2dehands eisen de EU-verantwoordelijke partij. Die hoort bij
    de verkoper, niet bij het artikel, dus hij wordt er hier bij gezet."""
    if platform not in ("marktplaats", "2dehands"):
        return payload
    try:
        from backend.services.instellingen import fabrikant, verzendkeuzes
        return {**payload, **fabrikant(user_id),
                **verzendkeuzes(user_id, payload.get("price"))}
    except Exception:  # noqa: BLE001 — liever plaatsen zonder dan niet plaatsen
        return payload


# Extension-driven platforms: relist reuses their existing, already-working
# create/delete job flow. No new browser automation is introduced here.
EXTENSION_RELIST_PLATFORMS = {"vinted", "marktplaats", "2dehands"}

# Per-platform: which refresh strategies are actually offered.
PLATFORM_STRATEGIES = {
    "vinted": {"content", "relist"},
    "marktplaats": {"relist"},
    "2dehands": {"relist"},
}

REFRESH_CAPABLE_PLATFORMS = set(PLATFORM_STRATEGIES.keys())

# Safety limits — deliberately conservative. These exist to keep the
# behavior indistinguishable from a normal seller tidying up their shop.
MIN_COOLDOWN_DAYS = 14          # can't refresh the same listing more than 1x/14d
MAX_REFRESHES_PER_USER_PER_DAY = 8

# Marktplaats is strenger dan Vinted, en het verschil is principieel: op Vinted
# is "bump" een functie van het platform zelf, op Marktplaats kost bovenaan komen
# geld. Weghalen en opnieuw plaatsen is daar dus niet gewoon opruimen maar het
# omzeilen van een betaalde dienst — precies waar Marktplaats op let. Daarom een
# eigen, ruimere afkoeltijd per kanaal in plaats van één getal voor alles.
#
# Bijkomend: Marktplaats-advertenties worden na 27 dagen sowieso al automatisch
# opnieuw geplaatst (relist_expiring_marktplaats). Een handmatige verversing komt
# daar bovenop, dus 21 dagen zorgt dat die twee elkaar niet opstapelen.
COOLDOWN_DAYS_PER_PLATFORM = {
    "marktplaats": 21,
    "2dehands": 21,
}
MAX_MP_REFRESHES_PER_USER_PER_DAY = 3


def _cooldown_days(platform: str) -> int:
    return COOLDOWN_DAYS_PER_PLATFORM.get(platform, MIN_COOLDOWN_DAYS)
RELIST_DELAY_MIN_MINUTES = 45   # recreate happens 45min-4h after delete
RELIST_DELAY_MAX_MINUTES = 240
CONTENT_PRICE_JITTER_PCT = 0.02  # +/-2% nudge, rounded to a sane price


# Hoe lang werk mag blijven hangen voordat we ingrijpen. Een baan wacht normaal
# hooguit uren: hij loopt zodra de computer met de extensie aan staat. Drie dagen
# is dus geen drukte meer maar een storing.
VASTGELOPEN_NA_DAGEN = 3


async def herstel_vastgelopen_werk() -> dict:
    """Advertenties die halverwege een herplaatsing bleven steken weer vlot trekken.

    Waarom dit nodig is. Een herplaatsing bestaat uit twee stappen: eerst weg bij
    het platform, daarna opnieuw plaatsen. Tussen die twee stappen staat de
    advertentie op 'relisting'. Blijft de tweede stap liggen — de computer stond
    uit, de baan liep vast, de verkoper sloot de browser — dan blijft hij daar
    staan. Voor de verkoper betekent dat: zijn advertentie is weg bij Marktplaats
    en komt niet terug, en niets in het scherm vertelt hem dat.

    Gemeten op 18-08-2026: 53 advertenties stonden op 'relisting', waarvan 17
    zonder enige openstaande opdracht om ze terug te zetten. Die waren dus
    definitief verdwenen zonder dat iemand het wist.

    Deze opruimer doet twee dingen, en geen van beide raadt iets:
      1. Staat een advertentie op 'relisting' zonder openstaande plaatsingsbaan,
         dan zetten we die baan alsnog klaar.
      2. Staat een baan langer dan drie dagen te wachten, dan zetten we hem op
         fout met een leesbare uitleg, zodat hij in het dashboard zichtbaar wordt
         in plaats van eeuwig stil te blijven staan.
    """
    db = get_db()
    grens = (datetime.now(timezone.utc) - timedelta(days=VASTGELOPEN_NA_DAGEN)).isoformat()
    hersteld, gemeld, teruggenomen = 0, 0, 0

    try:
        vast = ((await naast_de_lus(lambda: db.table("listings").select("id,item_id,platform")
                .eq("status", "relisting").limit(1000).execute())).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("herstel: kon vastgelopen advertenties niet lezen: %s", e)
        return {"hersteld": 0, "gemeld": 0}

    for rij in vast:
        try:
            lopend = ((await naast_de_lus(lambda: db.table("jobs").select("id,scheduled_for,created_at")
                      .eq("item_id", rij["item_id"]).eq("platform", rij["platform"])
                      .eq("action", "create").in_("status", ["pending", "claimed", "running"])
                      .limit(5).execute())).data or [])
            # IS DE OUDE ADVERTENTIE WEL ECHT WEG? (03-09-2026, Toon)
            #
            # Een kale plaatsing hoort alleen bij een verwijdering die is
            # afgerond. Is die verlopen, afgebroken of door de verkoper zelf
            # geannuleerd, dan staat de oude advertentie gewoon nog online en
            # zet een nieuwe plaatsing er een tweede naast. Toon annuleerde om
            # 02:34 drie herplaatsingen; om 17:44 stonden hier drie kale
            # plaatsingen voor klaar. Bij twee andere verkopers gebeurde
            # hetzelfde via de driedagenveger, met de oude advertentie nog
            # aantoonbaar live (HTTP 200).
            laatste = ((await naast_de_lus(lambda: db.table("jobs")
                        .select("id,user_id,item_id,platform,status,created_at,payload")
                        .eq("item_id", rij["item_id"]).eq("platform", rij["platform"])
                        .eq("action", "delete").order("created_at", desc=True)
                        .limit(1).execute())).data or [None])[0]
            if laatste and laatste.get("status") in ("pending", "claimed", "running"):
                continue          # het weghalen komt nog; de plaatsing volgt daarna
            if not laatste or laatste.get("status") != "done":
                teruggenomen += await _herplaatsing_terugnemen(db, rij, laatste, lopend)
                continue
            if lopend:
                continue          # er komt nog werk aan, afblijven
            item = ((await naast_de_lus(lambda: db.table("items").select("*").eq("id", rij["item_id"])
                    .single().execute())).data)
            if not item:
                continue
            (await naast_de_lus(lambda: db.table("jobs").insert({
                "user_id": item["user_id"],
                "item_id": rij["item_id"],
                "platform": rij["platform"],
                "action": "create",
                "status": "pending",
                "payload": _met_fabrikant(item, rij["platform"], item["user_id"]),
            }).execute()))
            hersteld += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("herstel: kon %s niet vlot trekken: %s", rij["id"], e)

    # Werk dat al dagen stilstaat hoort zichtbaar te worden.
    try:
        oud = ((await naast_de_lus(lambda: db.table("jobs")
               .select("id,user_id,item_id,platform,action,created_at,payload")
               .in_("status", ["pending", "claimed"])
               .lt("created_at", grens).limit(500).execute())).data or [])
        # De banen die we hierboven zojuist zelf hebben ingepland zijn van
        # vandaag en vallen dus per definitie buiten deze grens.
        #
        # Een verlopen VERWIJDERING van een herplaatsing is meer dan een baan
        # die stilstond: de oude advertentie is nooit weggehaald en staat dus
        # nog online. Die herplaatsing nemen we in zijn geheel terug (advertentie
        # terug op 'active', gepaarde plaatsing mee geannuleerd, verversbeurt
        # teruggegeven), anders bleef de rij op 'relisting' hangen en zette de
        # reddingsronde hierboven er later een kale plaatsing naast.
        oud.sort(key=lambda b: 0 if b.get("action") == "delete" else 1)
        teruggenomen_paren: set = set()
        for baan in oud:
            sleutel = (baan.get("item_id"), baan.get("platform"))
            if (baan.get("action") == "delete"
                    and (baan.get("payload") or {}).get("_refresh_rollback")):
                from backend.api.jobs import _neem_herplaatsing_terug
                await naast_de_lus(lambda b=baan: _neem_herplaatsing_terug(
                    db, b, datetime.now(timezone.utc).isoformat(), VERLOPEN_HERPLAATSING))
                teruggenomen_paren.add(sleutel)
                gemeld += 1
                continue
            if baan.get("action") == "create" and sleutel in teruggenomen_paren:
                continue          # al meegenomen met zijn verwijdering
            # De reden hoort in 'result'. De tabel heeft geen 'error'-kolom, en
            # daarop schrijven laat deze hele opruimronde stilletjes mislukken.
            (await naast_de_lus(lambda: db.table("jobs").update({
                "status": "error",
                "done_at": datetime.now(timezone.utc).isoformat(),
                "result": {"error": (
                    f"Deze opdracht stond meer dan {VASTGELOPEN_NA_DAGEN} dagen te "
                    "wachten en is niet uitgevoerd. Zet je computer met de "
                    "Omnivaleur-extensie aan en probeer het opnieuw.")},
            }).eq("id", baan["id"]).execute()))
            gemeld += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("herstel: kon oude banen niet melden: %s", e)

    if hersteld or gemeld or teruggenomen:
        logger.info("herstel: %d advertentie(s) opnieuw ingepland, %d vastgelopen baan/banen gemeld, "
                    "%d herplaatsing(en) teruggenomen", hersteld, gemeld, teruggenomen)
    return {"hersteld": hersteld, "gemeld": gemeld, "teruggenomen": teruggenomen}


HERPLAATSING_TERUGGENOMEN = (
    "Relist taken back: the old listing was never removed, so it is still live here. "
    "Nothing was reposted, so there is no duplicate. It will be picked up again in a "
    "later relist round."
)
VERLOPEN_HERPLAATSING = (
    f"Deze herplaatsing stond meer dan {VASTGELOPEN_NA_DAGEN} dagen te wachten en is "
    "niet uitgevoerd: de oude advertentie is nooit weggehaald en staat dus nog gewoon "
    "online. Er is niets opnieuw geplaatst. Zet je computer met de Omnivaleur-extensie "
    "aan; de volgende herplaatsronde pakt hem opnieuw op."
)


async def _herplaatsing_terugnemen(db, rij: dict, verwijderopdracht: dict | None,
                                   lopend: list[dict]) -> int:
    """Een herplaatsing waarvan het weghalen nooit is afgerond ongedaan maken.

    De advertentie staat nog online, dus 'active' is de waarheid. Elke
    klaarstaande plaatsing wordt ingetrokken: die zou er een tweede naast zetten.
    """
    now = datetime.now(timezone.utc).isoformat()
    for baan in lopend:
        await naast_de_lus(lambda b=baan: db.table("jobs").update({
            "status": "cancelled", "result": {"cancelled": HERPLAATSING_TERUGGENOMEN},
            "done_at": now,
        }).eq("id", b["id"]).execute())
    if verwijderopdracht:
        from backend.api.jobs import _neem_herplaatsing_terug
        await naast_de_lus(lambda: _neem_herplaatsing_terug(
            db, verwijderopdracht, now, HERPLAATSING_TERUGGENOMEN))
    # De rij zelf, mocht de verwijderopdracht een andere rij hebben aangewezen.
    await naast_de_lus(lambda: db.table("listings").update({
        "status": "active", "error_message": HERPLAATSING_TERUGGENOMEN,
    }).eq("id", rij["id"]).eq("status", "relisting").execute())
    logger.info("herstel: herplaatsing van item %s op %s teruggenomen (%d plaatsing(en) ingetrokken)",
                rij.get("item_id"), rij.get("platform"), len(lopend))
    return 1


class RefreshError(Exception):
    pass


# Wat een advertentie MOET hebben voordat we hem durven weg te halen.
#
# WAAROM DIT ER IS (28-08-2026, Jaap). Herplaatsen is twee stappen: eerst weg
# bij Marktplaats, daarna opnieuw plaatsen. Die tweede stap struikelde op items
# zonder omschrijving — het plaatsformulier van Marktplaats eist een tekst, dus
# de extensie brak af nog voor de foto's. Gevolg op één dag: 60 advertenties
# verwijderd, 0 teruggeplaatst, en omdat Marktplaats een verwijderde advertentie
# meteen op 410 zet was ook de tekst zelf onherstelbaar weg.
#
# Deze controle staat vóór het verwijderen. Ontbreekt er iets, dan gebeurt er
# niets: de advertentie blijft gewoon online staan. Een gemiste verversing kost
# een plek in de zoekresultaten; een mislukte herplaatsing kost de advertentie.
def ontbreekt_voor_herplaatsen(item: dict) -> str | None:
    """Geeft terug wat er mist, of None als deze advertentie veilig terug kan."""
    if not str(item.get("description") or "").strip():
        return ("this item has no description — Marktplaats refuses a listing "
                "without one, so removing the current listing would lose it. "
                "Fill the description (or use 'Fill from Marktplaats') first.")
    if not (item.get("photo_urls") or []):
        return ("this item has no photos — Marktplaats refuses a listing "
                "without one, so removing the current listing would lose it.")
    return None


def _check_and_increment_quota(db, user_id: str, platform: str | None = None) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    row = db.table("refresh_quota").select("count").eq("user_id", user_id).eq("day", today).execute()
    count = row.data[0]["count"] if row.data else 0
    if count >= MAX_REFRESHES_PER_USER_PER_DAY:
        raise RefreshError(
            f"Daily refresh limit reached ({MAX_REFRESHES_PER_USER_PER_DAY}/day). "
            "This cap is intentional — it keeps refresh activity looking like normal "
            "shop upkeep instead of a bulk/bot pattern."
        )

    # Bovenop de dagteller een strengere sublimiet voor Marktplaats/2dehands.
    # Acht keer opnieuw plaatsen op één dag is op Vinted onopvallend en op
    # Marktplaats een patroon. Geteld uit de banen zelf, zodat hier geen tweede
    # teller bijgehouden hoeft te worden die uit de pas kan gaan lopen.
    if platform in COOLDOWN_DAYS_PER_PLATFORM:
        vandaag = datetime.now(timezone.utc).date().isoformat()
        # ALLEEN DE HANDMATIGE KNOP TELT HIER MEE, EN ALLEEN ALS HIJ LUKTE.
        #
        # Hier werd elke verwijderopdracht van vandaag geteld. Dat zijn er bij
        # een grote verkoper tientallen die niets met deze knop te maken hebben:
        # het nachtelijke automatisch herplaatsen (dat zijn eigen, veel ruimere
        # grens heeft), een advertentie die elders verkocht was, en een
        # verwijdering die zelf mislukte. Gemeten bij Jaap op 28-08-2026: 61
        # verwijderopdrachten uit de nachtronde, dus de verversknop meldde de
        # hele dag "3 per dag bereikt" terwijl hij hem nog geen enkele keer had
        # gebruikt. Een mislukte poging hoort al helemaal niet mee te tellen —
        # er is dan niets verwijderd en niets herplaatst.
        mp_vandaag = (
            db.table("jobs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("action", "delete")
            .eq("payload->>_handmatige_verversing", "true")
            .neq("status", "error")
            .gte("created_at", vandaag)
            .execute()
        )
        if (mp_vandaag.count or 0) >= MAX_MP_REFRESHES_PER_USER_PER_DAY:
            raise RefreshError(
                f"Daily {platform} refresh limit reached "
                f"({MAX_MP_REFRESHES_PER_USER_PER_DAY}/day). Marktplaats charges for "
                "bumping a listing, so removing and reposting is exactly the pattern "
                "it watches for. Keeping this low is what keeps your account safe."
            )
    if row.data:
        db.table("refresh_quota").update({"count": count + 1}).eq("user_id", user_id).eq("day", today).execute()
    else:
        db.table("refresh_quota").insert({"user_id": user_id, "day": today, "count": 1}).execute()


def rollback_refresh(rollback: dict, user_id: str) -> None:
    """
    Undo the optimistic bookkeeping a refresh does at enqueue time when the
    extension job later fails. Without this, a failed content-refresh or a
    failed relist-delete leaves the listing on its 14-day cooldown and a quota
    slot spent — punishing the user for a refresh that never actually ran.
    """
    if not rollback:
        return
    db = get_db()
    listing_id = rollback.get("listing_id")
    if listing_id:
        db.table("listings").update({
            "last_refreshed_at": rollback.get("prior_last_refreshed_at"),
            "refresh_count": rollback.get("prior_refresh_count") or 0,
        }).eq("id", listing_id).execute()
    day = rollback.get("day")
    if day:
        row = db.table("refresh_quota").select("count").eq("user_id", user_id).eq("day", day).execute()
        if row.data:
            new_count = max(0, (row.data[0].get("count") or 0) - 1)
            db.table("refresh_quota").update({"count": new_count}).eq("user_id", user_id).eq("day", day).execute()


def _check_cooldown(listing: dict, platform: str | None = None) -> None:
    last = listing.get("last_refreshed_at")
    if not last:
        return
    dagen = _cooldown_days(platform or listing.get("platform") or "")
    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    elapsed = datetime.now(timezone.utc) - last_dt
    if elapsed < timedelta(days=dagen):
        remaining = timedelta(days=dagen) - elapsed
        raise RefreshError(
            f"This listing was refreshed {elapsed.days}d ago. "
            f"Wait {remaining.days}d more — refreshing too often is what gets accounts flagged."
        )


def _jittered_price(price: float) -> float:
    """Small, realistic-looking price nudge (a seller tweaking price is normal)."""
    delta = price * random.uniform(-CONTENT_PRICE_JITTER_PCT, CONTENT_PRICE_JITTER_PCT)
    new_price = max(1.0, round(price + delta, 2))
    # Avoid landing on the exact same price by chance.
    if new_price == price:
        new_price = round(price + 0.5, 2)
    return new_price


def _update_listing_refresh_state(db, listing_id: str, fields: dict) -> None:
    """
    Update cooldown/quota bookkeeping on the listing. If `last_refresh_strategy`
    hasn't been migrated onto the listings table yet (schema.sql ADD COLUMN not
    run), PostgREST fails the WHOLE update — silently breaking the cooldown/count
    fields too, not just the mode badge. Retry without it so the core refresh
    flow never depends on that optional column existing.
    """
    try:
        db.table("listings").update(fields).eq("id", listing_id).execute()
    except Exception as e:
        if "last_refresh_strategy" in fields and "last_refresh_strategy" in str(e):
            fallback = {k: v for k, v in fields.items() if k != "last_refresh_strategy"}
            db.table("listings").update(fallback).eq("id", listing_id).execute()
        else:
            raise


async def refresh_listing(item_id: str, platform: str, user_id: str, strategy: str,
                          new_price: float | None = None,
                          eigen_quotum: bool = False) -> dict:
    """
    Queue a refresh for one listing.
    strategy: "content" (safe edit-in-place, Vinted only) or
              "relist" (delete + scheduled recreate, Vinted/Marktplaats/2dehands).
    new_price: optional explicit price for a "relist" — e.g. the user accepting the
               10-15% price-drop suggestion. Ignored for "content" (that strategy is
               documented as never touching price). When given, it also becomes the
               item's new base price, so it sticks instead of reverting on the next refresh.
    """
    allowed = PLATFORM_STRATEGIES.get(platform, set())
    if strategy not in allowed:
        raise RefreshError(
            f"'{strategy}' isn't available for {platform}. "
            f"Available here: {', '.join(sorted(allowed)) or 'none'}."
        )

    db = get_db()

    item_resp = (await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute(), herkans=True))
    if not item_resp.data:
        raise RefreshError("Item not found")
    item = item_resp.data[0]

    listing_resp = (
        (await naast_de_lus(lambda: db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("status", "active")
        .execute(), herkans=True))
    )
    if not listing_resp.data:
        raise RefreshError("No active listing on this platform")
    listing = listing_resp.data[0]

    if platform not in REFRESH_CAPABLE_PLATFORMS:
        raise RefreshError(f"Refresh isn't available for {platform} yet")

    # Eerst: kunnen we deze advertentie straks überhaupt terugzetten? Zo niet,
    # dan halen we hem ook niet weg. Zie ontbreekt_voor_herplaatsen.
    # NU OOGSTEN, WANT STRAKS IS DE PAGINA WEG.
    #
    # Herplaatsen is: eerst weghalen, dan opnieuw plaatsen. Zodra dat weghalen
    # gebeurd is, geeft Marktplaats op de advertentiepagina HTTP 410 en is alles
    # wat daar stond onherroepelijk weg — de foto's voorop.
    #
    # Deze stap stond er al, maar alleen als het item helemaal LEEG was (geen
    # tekst of geen enkele foto). Een geïmporteerde advertentie heeft precies
    # één foto en een ingekorte tekst, en kwam daar dus zonder aanvulling
    # doorheen. Gemeten bij Jaap (Zilverwebsite, 28-08-2026): 14 advertenties
    # halverwege een herplaatsing, alle 14 met één foto, alle 14 pagina's
    # inmiddels 410 — die foto's zijn niet meer terug te halen. Nog eens 51
    # stonden op het punt hetzelfde te overkomen.
    #
    # Daarom oogsten we nu ALTIJD als er iets te winnen valt, en niet pas als
    # er niets meer over is.
    if (strategy == "relist" and platform in ("marktplaats", "2dehands")
            and listing.get("platform_listing_url")
            and (ontbreekt_voor_herplaatsen(item) or len(item.get("photo_urls") or []) <= 1)):
        from backend.services.mp_enrich import vul_item_aan_uit_advertentie
        item = await vul_item_aan_uit_advertentie(
            db, item, listing["platform_listing_url"])
    if strategy == "relist":
        mist = ontbreekt_voor_herplaatsen(item)
        if mist:
            raise RefreshError(f"Relist skipped — {mist}")

    _check_cooldown(listing, platform)
    # `eigen_quotum` betekent: de aanroeper bewaakt zelf hoeveel er per dag mag.
    # Dat is het automatisch herplaatsen, dat zijn eigen, veel ruimere grens per
    # verkoper hanteert (~voorraad gedeeld door de cyclus). Het dagquotum
    # hieronder is de rem op de HANDMATIGE verversknop en staat op 3 per dag voor
    # Marktplaats; zou het automatische pad daar ook doorheen moeten, dan zou dat
    # stilzwijgend terugvallen van tientallen naar drie advertenties per dag.
    if not eigen_quotum:
        _check_and_increment_quota(db, user_id, platform)

    now = datetime.now(timezone.utc)
    # Captured before we mutate the listing, so a failed job can be rolled back
    # to exactly the prior cooldown/quota state (see rollback_refresh).
    rollback = {
        "listing_id": listing["id"],
        "day": now.date().isoformat(),
        "prior_last_refreshed_at": listing.get("last_refreshed_at"),
        "prior_refresh_count": listing.get("refresh_count") or 0,
    }

    if strategy == "content":
        # Content refresh keeps the seller's OWN price — no jitter. It re-saves
        # the listing (with a photo re-order) so Vinted registers a fresh edit
        # without silently changing what the item is listed for.
        # Re-saving the listing rewrites its title/description, so they must be
        # localized here too — otherwise a content refresh quietly turns a Dutch
        # marktplaats listing back into English.
        from backend.services.crosslist import localize_item_for_platform
        localized = await localize_item_for_platform(item, platform)
        payload = {
            **localized,
            "platform_listing_id": listing["platform_listing_id"],
            "platform_listing_url": listing["platform_listing_url"],
            "price": float(item["price"]) if item.get("price") not in (None, "") else None,
            "photo_urls": _shuffled_photos(item.get("photo_urls") or []),
            "_refresh_rollback": rollback,
        }
        job = (await naast_de_lus(lambda: db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": platform,
            "action": "content_refresh",
            "status": "pending",
            "payload": payload,
        }).execute())).data[0]

        _update_listing_refresh_state(db, listing["id"], {
            "last_refreshed_at": now.isoformat(),
            "refresh_count": (listing.get("refresh_count") or 0) + 1,
            "last_refresh_strategy": "content",
        })

        return {"strategy": "content", "job_id": job["id"], "status": "queued"}

    # strategy == "relist": delete now, recreate after a randomized delay.
    #
    # DE VOLGORDE HIERONDER IS DE HELE VEILIGHEID — niet zomaar herschikken.
    #
    # Wat hier misging (Jaap Kroon, 28-08-2026): de verwijderopdracht werd als
    # eerste weggeschreven en pas dáárna werd de nieuwe advertentie opgebouwd —
    # met een vertaling, een prijsberekening en een paar databaseaanroepen
    # ertussen. Viel de verbinding op één van die stappen weg, dan stond de
    # verwijderopdracht er al en de herplaatsing niet. De extensie haalde de
    # advertentie dus netjes weg en er kwam nooit iets voor terug. Erger nog:
    # de status ging pas onderaan op "relisting", dus de reddingsronde
    # (herstel_vastgelopen_werk) zag hem niet eens staan. De advertentie was
    # stil en definitief weg.
    #
    # Daarom: ALLES wat kan mislukken gebeurt nu vóór de eerste opdracht wordt
    # weggeschreven. Daarna staan de twee inserts direct achter elkaar, en lukt
    # de tweede alsnog niet, dan halen we de eerste weer weg. Uitkomst: er staan
    # altijd twee opdrachten, of geen enkele. Nooit alleen een verwijdering.

    # ---- 1. Alles voorbereiden. Hier mag het misgaan; er is nog niets weg. ----
    delay_minutes = random.randint(RELIST_DELAY_MIN_MINUTES, RELIST_DELAY_MAX_MINUTES)
    scheduled_for = (now + timedelta(minutes=delay_minutes)).isoformat()

    if new_price is not None:
        if new_price <= 0:
            raise RefreshError("Price must be greater than 0")
        relist_price = round(new_price, 2)
        (await naast_de_lus(lambda: db.table("items").update({"price": relist_price}).eq("id", item_id).execute(), herkans=True))
    else:
        # Slight variation so the new listing isn't byte-identical to the old one —
        # legitimate reasons (price update, reordered photos), not spoofing.
        relist_price = _jittered_price(float(item.get("price") or 0)) or item.get("price")

    # Publish in the platform's own language, exactly like the original publish
    # did. Without this the recreate posts the raw English DB row to
    # marktplaats/2dehands, so a relisted item silently loses its Dutch title.
    from backend.services.crosslist import localize_item_for_platform
    localized = await localize_item_for_platform(item, platform)

    create_payload = {
        **localized,
        "price": relist_price,
        # Keep the EXACT original photo order — photo 1 must stay photo 1 (it's the
        # cover image the seller chose). The recreate already gets genuinely new
        # images because each photo is re-encoded on upload, so there's no need to
        # shuffle the order for uniqueness, and shuffling silently changed which
        # photo showed as the cover.
        "photo_urls": item.get("photo_urls") or [],
    }
    # A Vinted account lives on ONE country domain (e.g. vinted.nl). The create
    # form must be opened on that same domain, otherwise the recreate lands on
    # the wrong catalog — the same domain trap that broke delete. Carry the real
    # origin (recovered from the old listing URL) so the extension opens
    # {origin}/items/new instead of a hardcoded vinted.com.
    # Ook bij automatisch herplaatsen vraagt Marktplaats om de verantwoordelijke
    # partij. Zonder deze regel staat de nachtelijke ronde stil op drie rode
    # velden in een tabblad dat niemand ziet.
    if platform in ("marktplaats", "2dehands"):
        from backend.services.instellingen import fabrikant as _fabrikant, verzendkeuzes
        create_payload.update(_fabrikant(user_id))
        create_payload.update(verzendkeuzes(user_id, create_payload.get("price")))
        # DE ADVERTENTIE KOMT TERUG IN ZIJN EIGEN CATEGORIE.
        #
        # Amanda, 30-08-2026: "als je een advertentie van marktplaats laat
        # refreshen gaat dat goed, tot het punt dat de advertentie is geplaatst:
        # hij zet deze dan in de verkeerde categorie. Dit kun je bij MP niet
        # aanpassen, dus moet je de advertentie weer in zijn geheel handmatig
        # plaatsen."
        #
        # Bij het importeren wordt de categorie geráden uit titel en tekst, uit
        # een lijst die veel kleiner is dan de boom van Marktplaats. Voor
        # brocante, munten, boeken en postzegels bestaat er in die lijst
        # helemaal geen goede doos, dus werd het altijd de verkeerde. Terwijl de
        # oude advertentie — die op dit moment nog gewoon online staat — zijn
        # échte categorie zelf op de pagina zet.
        #
        # Dit gebeurt in stap 1, dus VÓÓR het verwijderen. Lukt het niet, dan
        # blijft alles bij het oude: een gemiste categorie mag nooit een
        # advertentie kosten.
        #
        # EN IN ZIJN EIGEN ADVERTENTIEVORM (03-09-2026, Amanda Haas).
        #
        # Dezelfde pagina zegt ook of het een vraagprijs is of "Bieden". Bij
        # het importeren nemen we alleen een échte vraagprijs over, dus een
        # bied-advertentie staat bij ons op 0 — en een vraagprijs van 0 is voor
        # Marktplaats een leeg prijsveld: "Geen prijs ingevuld". Het tabblad
        # bleef dan open staan wachten op de verkoper, terwijl de oude
        # advertentie al weg was. Elf van haar advertenties stonden daardoor
        # nergens meer. Eén ophaalronde levert nu allebei op.
        if listing.get("platform_listing_url"):
            from backend.services.mp_enrich import advertentie_kenmerken
            kenmerken = await advertentie_kenmerken(listing["platform_listing_url"])
            mp_cat = kenmerken.get("mp_category") or {}
            if mp_cat:
                create_payload["mp_category"] = mp_cat
                logger.info("[relist] item %s komt terug in zijn eigen categorie: %s",
                            item_id, mp_cat.get("l2_naam") or mp_cat)
            mp_vorm = kenmerken.get("mp_prijstype") or {}
            if mp_vorm:
                create_payload["mp_prijstype"] = mp_vorm
                logger.info("[relist] item %s komt terug als %s", item_id, mp_vorm.get("soort"))
    if platform == "vinted" and listing.get("platform_listing_url"):
        try:
            from urllib.parse import urlparse
            p = urlparse(listing["platform_listing_url"])
            if p.scheme and p.netloc:
                create_payload["_create_origin"] = f"{p.scheme}://{p.netloc}"
        except Exception:
            pass

    # Marktplaats/2dehands publish under a Dutch-translated title (never
    # persisted anywhere), so the delete automation must search for that
    # exact title, not item["title"] — otherwise it can't find the listing
    # on the overview page. Recover it from the last "create" job's payload.
    from backend.services.crosslist import _last_listed_title
    delete_payload = {
        **item,
        "title": _last_listed_title(db, item_id, platform, item.get("title", "")),
        "platform_listing_id": listing["platform_listing_id"],
        "platform_listing_url": listing["platform_listing_url"],
        # If the delist fails the whole relist aborts (the paired create is
        # skipped in /jobs/pending), so undo the cooldown/quota here too.
        "_refresh_rollback": rollback,
        # Alleen de handmatige verversknop valt onder de 3-per-dag-grens; het
        # nachtelijke herplaatsen heeft zijn eigen, ruimere grens. Zonder dit
        # merkteken telde de dagteller ze allebei. Zie _check_and_increment_quota.
        "_handmatige_verversing": not eigen_quotum,
    }

    # ---- 2. Nu pas wegschrijven. Vanaf hier is er geen voorbereiding meer. ----
    # De verwijdering moet als eerste in de database staan: het dispatch-filter in
    # jobs.py zoekt de bijbehorende verwijdering op created_at <= die van de
    # herplaatsing. Draai je dit om, dan vindt hij hem niet en vuurt de
    # herplaatsing terwijl de oude advertentie nog online staat (dubbele
    # advertentie).
    # Het id zelf bepalen. Valt de verbinding weg terwijl het ANTWOORD onderweg
    # is, dan staat de opdracht er misschien al; een herhaalde poging loopt dan
    # op een dubbele sleutel en dat betekent "stond er al" — geen tweede
    # opdracht, en dus geen tweede advertentie. Zonder dit zou herkansen op een
    # insert het probleem alleen maar verplaatsen.
    verwijder_id = str(uuid.uuid4())
    await _exec(db.table("jobs").insert({
        "id": verwijder_id,
        "user_id": user_id,
        "item_id": item_id,
        "platform": platform,
        "action": "delete",
        "status": "pending",
        "payload": delete_payload,
    }), dubbel_is_ok=True)

    try:
        await _exec(db.table("jobs").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "item_id": item_id,
            "platform": platform,
            "action": "create",
            "status": "pending",
            "payload": create_payload,
            "scheduled_for": scheduled_for,
        }), dubbel_is_ok=True)
    except Exception as e:  # noqa: BLE001
        # De herplaatsing kon niet worden vastgelegd. Dan mag de verwijdering
        # ook niet blijven staan — anders haalt de extensie straks een
        # advertentie weg die nooit meer terugkomt. Liever een mislukte
        # verversing dan een verdwenen advertentie.
        if verwijder_id:
            try:
                (await naast_de_lus(lambda: db.table("jobs").delete().eq("id", verwijder_id).execute(), herkans=True))
            except Exception:  # noqa: BLE001
                # Lukt zelfs dat niet, dan zetten we hem op geannuleerd; de
                # extensie pakt alleen "pending" op.
                try:
                    (await naast_de_lus(lambda: db.table("jobs").update({
                        "status": "cancelled",
                        "result": {"error": "Relist aborted before the recreate was queued."},
                    }).eq("id", verwijder_id).execute(), herkans=True))
                except Exception:  # noqa: BLE001
                    logger.error(
                        "KRITIEK: verwijderopdracht %s kon niet worden teruggedraaid voor item %s op %s",
                        verwijder_id, item_id, platform)
        logger.error("Herplaatsen afgebroken voor item %s op %s: %s", item_id, platform, e)
        raise RefreshError(
            "The connection dropped while setting up the relist, so nothing was "
            "changed and your listing is still live. Please try again."
        ) from e

    _update_listing_refresh_state(db, listing["id"], {
        "status": "relisting",
        "last_refreshed_at": now.isoformat(),
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
        "last_refresh_strategy": "relist",
    })

    logger.info(f"Queued relist for item {item_id} on {platform}, recreate scheduled in {delay_minutes}min")
    return {
        "strategy": "relist",
        "status": "queued",
        "recreate_scheduled_for": scheduled_for,
        "new_price": relist_price,
        "message": f"Old listing removed now; new listing will be created in ~{delay_minutes} min to avoid a scripted-looking pattern.",
    }


def _shuffled_photos(photo_urls: list[str]) -> list[str]:
    if len(photo_urls) < 2:
        return photo_urls
    shuffled = photo_urls[:]
    random.shuffle(shuffled)
    return shuffled


async def refresh_stale_listings(user_id: str, platform: str, older_than_days: int = 30, limit: int = 5) -> list[dict]:
    """
    Bulk entry point: refresh the user's oldest eligible listings on one platform,
    capped by the same daily quota (so this can't be used to blast every item at once).
    """
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    cooldown_cutoff = (datetime.now(timezone.utc)
                       - timedelta(days=_cooldown_days(platform))).isoformat()

    item_ids = [r["id"] for r in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", user_id))]
    if not item_ids:
        return []

    # In brokken: boven ~639 item-id's wordt de URL van dit filter te lang en
    # gooit httpx een uitzondering (zie database.IN_BROK). Bij een grote winkel
    # liep het opnieuw-plaatsen daar dus stil op stuk.
    def _brok(stuk):
        return (db.table("listings").select("*").in_("item_id", stuk)
                .eq("platform", platform).eq("status", "active")
                .lt("listed_at", cutoff).order("listed_at").limit(limit)
                .execute().data or [])

    def _alles():
        rijen = []
        for i in range(0, len(item_ids), IN_BROK):
            rijen.extend(_brok(item_ids[i:i + IN_BROK]))
        rijen.sort(key=lambda l: l.get("listed_at") or "")
        return rijen[:limit]

    candidates = [
        l for l in (await naast_de_lus(_alles))
        if not l.get("last_refreshed_at") or l["last_refreshed_at"] < cooldown_cutoff
    ]

    results = []
    for listing in candidates:
        try:
            res = await refresh_listing(listing["item_id"], platform, user_id, "relist")
            results.append({"item_id": listing["item_id"], **res})
        except RefreshError as e:
            results.append({"item_id": listing["item_id"], "status": "skipped", "reason": str(e)})
            break  # quota hit — stop trying the rest
    return results


async def renew_etsy_listing(item_id: str, user_id: str) -> dict:
    """
    Etsy's own official renewal action (PATCH state=active). Real money changes
    hands here — Etsy charges the normal listing fee — so this is deliberately
    NOT bundled into the daily refresh quota used by the other platforms; it's
    a one-click "pay to renew" action the user explicitly triggers, same as
    clicking Renew on etsy.com.
    """
    db = get_db()
    item_resp = (await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute(), herkans=True))
    if not item_resp.data:
        raise RefreshError("Item not found")

    listing_resp = (
        (await naast_de_lus(lambda: db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", "etsy")
        .in_("status", ["active", "sold", "error"])
        .execute()))
    )
    if not listing_resp.data:
        raise RefreshError("No Etsy listing found for this item")
    listing = listing_resp.data[0]
    if not listing.get("platform_listing_id"):
        raise RefreshError("This Etsy listing has no known listing ID")

    creds_resp = (
        (await naast_de_lus(lambda: db.table("platform_credentials")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "etsy")
        .execute()))
    )
    if not creds_resp.data:
        raise RefreshError("Etsy isn't connected")
    credentials = creds_resp.data[0]

    platform = get_platform("etsy")
    result = await platform.renew_listing(listing["platform_listing_id"], credentials)

    now = datetime.now(timezone.utc).isoformat()
    (await naast_de_lus(lambda: db.table("listings").update({
        "status": "active",
        "last_refreshed_at": now,
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
    }).eq("id", listing["id"]).execute()))

    return {"strategy": "renew", "status": "renewed", "etsy_state": result.get("state")}


async def relist_ended_ebay_listing(item_id: str, user_id: str) -> dict:
    """
    Republish an ENDED eBay offer via eBay's own relist mechanism. Refuses to run
    if the listing is still active — eBay's duplicate-listing policy prohibits two
    live listings for the same item, so this only ever touches offers that have
    already ended (sold, withdrawn, or expired).
    """
    db = get_db()
    item_resp = (await naast_de_lus(lambda: db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute(), herkans=True))
    if not item_resp.data:
        raise RefreshError("Item not found")

    listing_resp = (
        (await naast_de_lus(lambda: db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", "ebay")
        .execute()))
    )
    if not listing_resp.data:
        raise RefreshError("No eBay listing found for this item")
    listing = listing_resp.data[0]
    offer_id = listing.get("platform_offer_id") or listing.get("platform_listing_id")
    if not offer_id:
        raise RefreshError("This eBay listing has no known offer ID")

    creds_resp = (
        (await naast_de_lus(lambda: db.table("platform_credentials")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "ebay")
        .execute()))
    )
    if not creds_resp.data:
        raise RefreshError("eBay isn't connected")
    credentials = creds_resp.data[0]

    platform = get_platform("ebay")
    try:
        result = await platform.relist_ended(offer_id, credentials)
    except RuntimeError as e:
        raise RefreshError(str(e))

    now = datetime.now(timezone.utc).isoformat()
    (await naast_de_lus(lambda: db.table("listings").update({
        "status": "active",
        "platform_listing_id": result["platform_listing_id"],
        "platform_listing_url": result["platform_listing_url"],
        "listed_at": now,
        "last_refreshed_at": now,
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
    }).eq("id", listing["id"]).execute()))

    return {"strategy": "relist_ended", "status": "relisted", **result}
