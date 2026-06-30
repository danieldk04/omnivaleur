"""
Polling service for platforms without webhooks (primarily Vinted).
Runs on a configurable interval via APScheduler.
"""
import logging
from backend.database import get_db
from backend.platforms import get_platform
from backend.services.crosslist import handle_item_sold

logger = logging.getLogger(__name__)

POLL_PLATFORMS = {"vinted", "marktplaats", "2dehands"}


async def poll_platform_statuses():
    """
    Check all active listings on polled platforms for status changes.
    Triggers auto-delist if a sold item is detected.
    """
    db = get_db()

    listings = (
        db.table("listings")
        .select("*")
        .eq("status", "active")
        .in_("platform", list(POLL_PLATFORMS))
        .execute()
    )

    if not listings.data:
        return

    logger.info(f"Polling {len(listings.data)} active listings")

    for listing in listings.data:
        await _check_one(listing)


async def _check_one(listing: dict):
    db = get_db()
    platform_name = listing["platform"]

    creds_resp = (
        db.table("platform_credentials")
        .select("*")
        .eq("platform", platform_name)
        .execute()
    )
    credentials = creds_resp.data[0] if creds_resp.data else {}

    try:
        platform = get_platform(platform_name)
        status = await platform.get_listing_status(
            listing["platform_listing_id"], credentials
        )

        from datetime import datetime, timezone
        db.table("listings").update({
            "last_checked": datetime.now(timezone.utc).isoformat()
        }).eq("id", listing["id"]).execute()

        if status == "sold":
            logger.info(f"Item {listing['item_id']} sold on {platform_name} — triggering delist")
            await handle_item_sold(listing["item_id"], platform_name)

        elif status == "not_found":
            logger.warning(f"Listing {listing['id']} not found on {platform_name} — marking delisted")
            db.table("listings").update({"status": "delisted"}).eq("id", listing["id"]).execute()

    except Exception as e:
        logger.error(f"Poll failed for listing {listing['id']}: {e}")
