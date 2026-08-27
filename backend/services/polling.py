"""
Polling service for platforms without webhooks (Marktplaats, 2dehands).
Runs on a configurable interval via APScheduler.
"""
import asyncio
import logging
from backend.database import get_db, IN_BROK
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
POLL_PLATFORMS = {"marktplaats", "2dehands"}


async def poll_platform_statuses():
    """
    Check all active listings on polled platforms for status changes.
    Triggers auto-delist if a sold item is detected.

    Draait elke `polling_interval` seconden, dus alles wat hier per listing aan
    database-verkeer gebeurt, gebeurt honderden keren per dag. Daarom in drie
    gebundelde queries in plaats van twee losse queries pér listing:

      1. de actieve listings (alleen de kolommen die we echt gebruiken),
      2. in één keer welk item bij welke gebruiker hoort,
      3. in één keer alle platformkoppelingen.

    Listings van gebruikers zonder koppeling voor dat platform worden
    overgeslagen. `get_listing_status` vraagt bij Marktplaats/2dehands een
    verkoper-pagina op die alleen mét de cookies van die verkoper klopt — zonder
    koppeling levert die call dus geen bruikbare uitkomst op, alleen verkeer.
    Dat scheelt ook de honderden nep-listings van het demo-account.
    """
    db = get_db()

    listings = await _exec(
        db.table("listings")
        .select("id,item_id,platform,platform_listing_id,not_found_count")
        .eq("status", "active")
        .in_("platform", list(POLL_PLATFORMS))
    )

    if not listings.data:
        return

    item_ids = list({row["item_id"] for row in listings.data})
    # In brokken: dit draait over ÁLLE actieve advertenties van alle verkopers
    # samen (gemeten 27-08-2026: 4.751). Eén `.in_()` met zoveel id's maakt een
    # URL die httpx weigert te versturen, en dan viel de hele verkoopcontrole
    # stil — voor iedereen tegelijk, zonder zichtbare foutmelding.
    owners = {}
    for i in range(0, len(item_ids), IN_BROK):
        stuk = item_ids[i:i + IN_BROK]
        for row in ((await _exec(db.table("items").select("id,user_id").in_("id", stuk))).data or []):
            owners[row["id"]] = row["user_id"]

    credentials_by_key: dict[tuple[str, str], dict] = {}
    for row in (
        (await _exec(
            db.table("platform_credentials")
            .select("*")
            .in_("platform", list(POLL_PLATFORMS))
        )).data
        or []
    ):
        credentials_by_key[(row["user_id"], row["platform"])] = row

    pollable = [
        (row, credentials_by_key[(owners[row["item_id"]], row["platform"])])
        for row in listings.data
        if owners.get(row["item_id"])
        and (owners[row["item_id"]], row["platform"]) in credentials_by_key
    ]

    skipped = len(listings.data) - len(pollable)
    logger.info(
        f"Polling {len(pollable)} active listings"
        + (f" ({skipped} skipped — no platform connection for the owner)" if skipped else "")
    )

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
