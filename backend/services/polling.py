"""
Polling service for platforms without webhooks (Marktplaats, 2dehands).
Runs on a configurable interval via APScheduler.
"""
import asyncio
import logging
from backend.database import get_db, fetch_all, IN_BROK
from backend.platforms import get_platform
from backend.services.crosslist import handle_item_sold

logger = logging.getLogger(__name__)


# De Supabase-client is synchroon: elke .execute() blokkeert de héle server tot
# het antwoord binnen is. Deze taak draait elke vijf minuten en doet één tot twee
# van die aanroepen per actieve advertentie, dus bij honderden advertenties stond
# alles minutenlang stil — en kreeg wie op dat moment iets opsloeg een 502 van de
# gateway. Alleen .execute() doet netwerkwerk; de rest van de keten bouwt enkel de
# query op. Daarom draait uitsluitend die stap in een aparte thread.
async def _exec(query):
    return await asyncio.to_thread(query.execute)

# Vinted excluded: polling relies on a separate backend-bootstrapped session (distinct
# from the browser-extension session used for scan/publish) that requires storing the
# user's Vinted password, and when it goes stale it silently mass-delists live listings
# via false "not found" reads. Not worth that risk for a status check.
# eBay en Etsy staan er sinds 30-08-2026 bij. Die twee zijn via hun eigen API te
# bevragen met de sleutel die de verkoper al heeft gekoppeld — geen cookies, geen
# browser. Tot dan kwam een eBay-verkoop alleen binnen via de webhook (die alleen
# werkt als eBay-meldingen goed staan) en een Etsy-verkoop helemaal niet, waardoor
# het artikel overal elders gewoon te koop bleef staan.
POLL_PLATFORMS = {"marktplaats", "2dehands", "ebay", "etsy"}

# Hoe lang een advertentie met rust gelaten wordt nadat hij is nagekeken, en
# hoeveel er hooguit in één ronde langskomen.
#
# WAAROM DIT ER IS (31-08-2026) — de duurste lus die dit project had.
# Deze taak haalde élke ronde ALLE actieve advertenties opnieuw op (gemeten
# 27-08: 4.751) en liep ze daarna één voor één langs met een netwerkaanroep per
# stuk. Twee dingen gingen daar mis, en allebei bleven ze onzichtbaar:
#
#   * De ronde kón niet af. 4.751 aanroepen achter elkaar duren tientallen
#     minuten, terwijl de taak elke vijf minuten opnieuw wil starten. Wat
#     achteraan de lijst stond werd dus in de praktijk NOOIT gecontroleerd —
#     precies de advertenties die het langst te koop stonden.
#   * Elke ronde trok dezelfde 4.751 rijen opnieuw uit de database. Bij 288
#     rondes per dag is dat vele gigabytes verkeer per maand aan gegevens die
#     niemand had opgevraagd. Op 31-08-2026 zette Supabase het hele project op
#     slot wegens overschreden verkeer (402), waarmee de site voor iedereen
#     plat lag.
#
# Nu komt alleen langs wat écht aan de beurt is, oudste eerst. Iedere
# advertentie komt daardoor gegarandeerd een keer aan de beurt in plaats van
# alleen de eerste paar honderd, en het verkeer per ronde is een fractie.
HERCONTROLE_NA = 3600          # seconden: hooguit één keer per uur per advertentie
PER_RONDE = 500                # hooguit zoveel advertenties in één ronde


async def poll_platform_statuses():
    """
    Check active listings on polled platforms for status changes.
    Triggers auto-delist if a sold item is detected.

    Alleen de advertenties die aan de beurt zijn: nog nooit gecontroleerd, of
    langer dan HERCONTROLE_NA geleden. Oudste eerst, met een dak erop, zodat
    één ronde altijd afloopt en niemand achteraan de rij blijft staan.

    Listings van gebruikers zonder koppeling voor dat platform worden
    overgeslagen. `get_listing_status` vraagt bij Marktplaats/2dehands een
    verkoper-pagina op die alleen mét de cookies van die verkoper klopt — zonder
    koppeling levert die call dus geen bruikbare uitkomst op, alleen verkeer.
    Dat scheelt ook de honderden nep-listings van het demo-account.
    """
    db = get_db()

    grens = (datetime.now(timezone.utc)
             - timedelta(seconds=HERCONTROLE_NA)).isoformat()
    # `nullsfirst`: een advertentie die nog nooit is nagekeken gaat voor. Zonder
    # dat zou een nieuwe advertentie achter de hele bestaande voorraad aansluiten.
    rijen = ((await _exec(db.table("listings")
              .select("id,item_id,platform,platform_listing_id,not_found_count,last_checked")
              .eq("status", "active")
              .in_("platform", list(POLL_PLATFORMS))
              .or_(f"last_checked.is.null,last_checked.lt.{grens}")
              .order("last_checked", desc=False, nullsfirst=True)
              .limit(PER_RONDE))).data or [])

    if not rijen:
        return

    item_ids = list({row["item_id"] for row in rijen})
    # In brokken: één `.in_()` met te veel id's maakt een URL die httpx weigert
    # te versturen, en dan viel de hele verkoopcontrole stil — voor iedereen
    # tegelijk, zonder zichtbare foutmelding. Zie IN_BROK in database.py.
    owners = {}
    for i in range(0, len(item_ids), IN_BROK):
        stuk = item_ids[i:i + IN_BROK]
        for row in ((await _exec(db.table("items").select("id,user_id").in_("id", stuk))).data or []):
            owners[row["id"]] = row["user_id"]

    # Alleen de koppelingen van de eigenaren die in DEZE ronde meedoen. Die
    # rijen bevatten tokens en cookies en zijn daarmee de dikste rijen die we
    # hebben; ze allemaal ophalen terwijl er een handvol nodig is, is precies
    # het soort verkeer dat het project op slot heeft gezet.
    credentials_by_key: dict[tuple[str, str], dict] = {}
    eigenaren = sorted({u for u in owners.values() if u})
    for i in range(0, len(eigenaren), IN_BROK):
        stuk = eigenaren[i:i + IN_BROK]
        for row in (
            (await _exec(
                db.table("platform_credentials")
                .select("*")
                .in_("platform", list(POLL_PLATFORMS))
                .in_("user_id", stuk)
            )).data
            or []
        ):
            credentials_by_key[(row["user_id"], row["platform"])] = row

    pollable = [
        (row, credentials_by_key[(owners[row["item_id"]], row["platform"])])
        for row in rijen
        if owners.get(row["item_id"])
        and (owners[row["item_id"]], row["platform"]) in credentials_by_key
    ]

    skipped = len(rijen) - len(pollable)
    logger.info(
        f"Polling {len(pollable)} active listings (aan de beurt: {len(rijen)})"
        + (f" ({skipped} skipped — no platform connection for the owner)" if skipped else "")
    )

    # Een overgeslagen advertentie (eigenaar zonder koppeling) moet óók een
    # stempel krijgen. Zonder dat blijft hij eeuwig "aan de beurt" en verdringt
    # hij elke ronde opnieuw de advertenties die wél gecontroleerd kunnen worden.
    nu = datetime.now(timezone.utc).isoformat()
    overgeslagen = [r["id"] for r in rijen
                    if (r, credentials_by_key.get((owners.get(r["item_id"]), r["platform"])))
                    and not (owners.get(r["item_id"])
                             and (owners[r["item_id"]], r["platform"]) in credentials_by_key)]
    for i in range(0, len(overgeslagen), IN_BROK):
        try:
            await _exec(db.table("listings").update({"last_checked": nu})
                        .in_("id", overgeslagen[i:i + IN_BROK]))
        except Exception as e:  # noqa: BLE001 — een stempel is geen reden om te stoppen
            logger.warning("Kon overgeslagen listings niet stempelen: %s", e)

    for listing, credentials in pollable:
        await _check_one(listing, credentials)


async def _check_one(listing: dict, credentials: dict):
    db = get_db()
    platform_name = listing["platform"]

    try:
        platform = get_platform(platform_name)
        status = await platform.get_listing_status(
            listing["platform_listing_id"], credentials
        )

        from datetime import datetime, timezone
        await _exec(db.table("listings").update({
            "last_checked": datetime.now(timezone.utc).isoformat()
        }).eq("id", listing["id"]))

        if status == "sold":
            logger.info(f"Item {listing['item_id']} sold on {platform_name} — triggering delist")
            await handle_item_sold(listing["item_id"], platform_name)

        elif status == "not_found":
            # A single 404 is often caused by a stale/expired polling session rather than
            # a genuinely removed listing (confirmed: this previously mass-delisted live
            # Vinted listings during a session outage). Require 2 consecutive not-found
            # polls before trusting it enough to actually delist.
            not_found_count = (listing.get("not_found_count") or 0) + 1
            if not_found_count >= 2:
                logger.warning(f"Listing {listing['id']} not found on {platform_name} for {not_found_count} consecutive polls — marking delisted")
                await _exec(db.table("listings").update({"status": "delisted", "not_found_count": not_found_count}).eq("id", listing["id"]))
            else:
                logger.warning(f"Listing {listing['id']} not found on {platform_name} (1st time) — waiting for confirmation before delisting")
                await _exec(db.table("listings").update({"not_found_count": not_found_count}).eq("id", listing["id"]))

        elif status in ("active", "sold"):
            if listing.get("not_found_count"):
                await _exec(db.table("listings").update({"not_found_count": 0}).eq("id", listing["id"]))

    except Exception as e:
        logger.error(f"Poll failed for listing {listing['id']}: {e}")
