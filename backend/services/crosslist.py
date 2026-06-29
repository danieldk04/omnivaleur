"""
Core crosslisting orchestration.
Handles: publish to multiple platforms, auto-delist on sale.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from backend.database import get_db
from backend.platforms import get_platform

_ENGLISH_PLATFORMS = {"vinted", "shopify", "ebay", "etsy"}
# marktplaats/2dehands require Dutch — user now enters English, so translate EN→NL.
_DUTCH_PLATFORMS: set[str] = {"marktplaats", "2dehands"}

logger = logging.getLogger(__name__)


async def _translate(text: str, langpair: str) -> str:
    """Translate text via MyMemory free API. langpair e.g. 'nl|en' or 'en|nl'."""
    if not text or not text.strip():
        return text
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:500], "langpair": langpair},
            )
            data = r.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            return translated if translated else text
    except Exception as e:
        logger.warning(f"Translation ({langpair}) failed, using original: {e}")
        return text


async def _translate_to_english(text: str) -> str:
    return await _translate(text, "nl|en")


async def _translate_to_dutch(text: str) -> str:
    return await _translate(text, "en|nl")


# Platforms handled by the Chrome extension (form automation in real browser)
EXTENSION_PLATFORMS = {"marktplaats", "2dehands", "vinted"}
# Platforms handled server-side via official API
API_PLATFORMS = {"ebay", "etsy", "shopify"}


async def publish_to_platforms(item_id: str, platforms: list[str], user_id: str) -> list[dict]:
    """
    Route each platform to the right handler:
    - Extension platforms → create a job, extension picks it up
    - API platforms → call directly server-side
    """
    db = get_db()
    item_resp = db.table("items").select("*").eq("id", item_id).single().execute()
    item = item_resp.data

    results = []
    api_platforms = [p for p in platforms if p in API_PLATFORMS]
    ext_platforms = [p for p in platforms if p in EXTENSION_PLATFORMS]

    # Pre-translate concurrently for platforms that need a different language
    english_item = None
    dutch_item = None
    need_en = any(p in _ENGLISH_PLATFORMS for p in platforms)
    need_nl = any(p in _DUTCH_PLATFORMS for p in platforms)

    async def _build_english():
        manual_title = (item.get("shopify_title") or "").strip()
        if manual_title:
            title_en = manual_title
            desc_en = await _translate_to_english(item.get("description", ""))
        else:
            title_en, desc_en = await asyncio.gather(
                _translate_to_english(item.get("title", "")),
                _translate_to_english(item.get("description", "")),
            )
        return {**item, "title": title_en, "description": desc_en}

    async def _build_dutch():
        title_nl, desc_nl = await asyncio.gather(
            _translate_to_dutch(item.get("title", "")),
            _translate_to_dutch(item.get("description", "")),
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

    def _pick(platform: str) -> dict:
        if platform in _ENGLISH_PLATFORMS and english_item:
            return english_item
        if platform in _DUTCH_PLATFORMS and dutch_item:
            return dutch_item
        return item

    # API platforms: run concurrently server-side
    if api_platforms:
        creds_resp = (
            db.table("platform_credentials")
            .select("*")
            .eq("user_id", user_id)
            .in_("platform", api_platforms)
            .execute()
        )
        creds_by_platform = {c["platform"]: c for c in creds_resp.data}
        tasks = [
            _publish_one(_pick(p), p, creds_by_platform.get(p, {}), user_id)
            for p in api_platforms
        ]
        results += await asyncio.gather(*tasks, return_exceptions=False)

    # Extension platforms: enqueue jobs
    for platform in ext_platforms:
        payload = dict(_pick(platform))
        # Create pending listing record first so failed jobs are visible in dashboard
        existing_listing = db.table("listings").select("id").eq("item_id", item_id).eq("platform", platform).execute()
        if not existing_listing.data:
            db.table("listings").insert({
                "item_id": item_id,
                "platform": platform,
                "status": "pending",
            }).execute()
        else:
            db.table("listings").update({"status": "pending", "error_message": None}).eq("item_id", item_id).eq("platform", platform).execute()
        job = db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": platform,
            "action": "create",
            "status": "pending",
            "payload": payload,
        }).execute().data[0]
        results.append({
            "platform": platform,
            "status": "queued",
            "job_id": job["id"],
            "message": "Job queued — Chrome extension will process this",
        })

    return results


async def _publish_one(item: dict, platform_name: str, credentials: dict, user_id: str) -> dict:
    db = get_db()
    listing_row = {
        "item_id": item["id"],
        "platform": platform_name,
        "status": "pending",
    }
    insert = db.table("listings").insert(listing_row).execute()
    listing_id = insert.data[0]["id"]

    try:
        platform = get_platform(platform_name)
        result = await platform.create_listing(item, credentials)

        db.table("listings").update({
            "platform_listing_id": result["platform_listing_id"],
            "platform_listing_url": result["platform_listing_url"],
            "status": "active",
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", listing_id).execute()

        _log_event(listing_id, "listed", result)
        return {"listing_id": listing_id, "platform": platform_name, "status": "active", **result}

    except Exception as e:
        logger.error(f"Failed to list on {platform_name}: {e}")
        db.table("listings").update({
            "status": "error",
            "error_message": str(e),
        }).eq("id", listing_id).execute()
        _log_event(listing_id, "error", {"error": str(e)})
        return {"listing_id": listing_id, "platform": platform_name, "status": "error", "error": str(e)}


async def delist_all_platforms(item_id: str, user_id: str) -> list[dict]:
    """Delist an item from every platform it is currently active on."""
    db = get_db()
    listings_resp = (
        db.table("listings").select("*").eq("item_id", item_id).execute()
    )
    # Include 'active' listings and ANY 'error' listings (product may exist on platform
    # even if our status tracking failed). Deduplicate by platform — keep the one with
    # a platform_listing_id if both exist, otherwise any.
    seen_platforms: dict[str, dict] = {}
    for l in listings_resp.data:
        if l["status"] not in ("active", "error"):
            continue
        p = l["platform"]
        existing = seen_platforms.get(p)
        if existing is None or (l.get("platform_listing_id") and not existing.get("platform_listing_id")):
            seen_platforms[p] = l
    active_listings = list(seen_platforms.values())

    if not active_listings:
        return [{"status": "nothing_to_delist", "message": "No active listings found"}]

    item_resp = db.table("items").select("*").eq("id", item_id).single().execute()
    item = item_resp.data

    results = []

    api_active = [l for l in active_listings if l["platform"] in API_PLATFORMS]
    ext_active = [l for l in active_listings if l["platform"] in EXTENSION_PLATFORMS]

    if api_active:
        # For Shopify listings without a platform_listing_id, look up by SKU first
        for listing in api_active:
            if listing["platform"] == "shopify" and not listing.get("platform_listing_id"):
                try:
                    from backend.platforms.shopify_importer import _get_token
                    import httpx
                    from backend.config import settings
                    token = await _get_token()
                    sku = item.get("sku", "")
                    async with httpx.AsyncClient() as c:
                        r = await c.get(
                            f"https://{settings.shopify_store}/admin/api/2024-10/products.json",
                            params={"limit": 50},
                            headers={"X-Shopify-Access-Token": token},
                        )
                        products = r.json().get("products", [])
                    match = next(
                        (p for p in products
                         if any(v.get("sku") == sku for v in p.get("variants", []))),
                        None,
                    )
                    if match:
                        pid = str(match["id"])
                        listing["platform_listing_id"] = pid
                        db.table("listings").update({"platform_listing_id": pid}).eq("id", listing["id"]).execute()
                        logger.info(f"Resolved Shopify product by SKU {sku} → {pid}")
                except Exception as e:
                    logger.warning(f"Shopify SKU lookup failed: {e}")

        tasks = [_delist_one(listing) for listing in api_active]
        api_results = await asyncio.gather(*tasks, return_exceptions=True)
        for listing, res in zip(api_active, api_results):
            if isinstance(res, Exception):
                results.append({"platform": listing["platform"], "status": "error", "error": str(res)})
            else:
                results.append({"platform": listing["platform"], "status": "delisted"})

    for listing in ext_active:
        payload = {
            **item,
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

    return results


async def handle_item_sold(item_id: str, sold_on_platform: str):
    """
    Called when an item is confirmed sold on one platform.
    Delists from all other active platforms concurrently.
    """
    db = get_db()

    # Mark sold listing
    db.table("listings").update({
        "status": "sold",
        "sold_at": datetime.now(timezone.utc).isoformat(),
    }).eq("item_id", item_id).eq("platform", sold_on_platform).execute()

    # Find other active listings
    other = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("status", "active")
        .neq("platform", sold_on_platform)
        .execute()
    )

    if not other.data:
        return

    tasks = [_delist_one(listing) for listing in other.data]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for listing, result in zip(other.data, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to delist {listing['platform']} listing {listing['id']}: {result}")


_MVP_USER_ID = "00000000-0000-0000-0000-000000000001"

# Marktplaats free listings expire silently after 28 days.
# We relist 1 day early to avoid gaps in visibility.
_MARKTPLAATS_EXPIRY_DAYS = 27


async def relist_expiring_marktplaats():
    """
    Queue a new 'create' job for every Marktplaats listing that has been
    active for >= MARKTPLAATS_EXPIRY_DAYS days and hasn't been re-queued yet.
    Marks the old listing 'relisting' so this function won't double-trigger.
    """
    from datetime import datetime, timezone, timedelta
    db = get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=_MARKTPLAATS_EXPIRY_DAYS)).isoformat()
    listings_resp = (
        db.table("listings")
        .select("*")
        .eq("platform", "marktplaats")
        .eq("status", "active")
        .lt("listed_at", cutoff)
        .execute()
    )

    if not listings_resp.data:
        return

    logger.info(f"Auto-relisting {len(listings_resp.data)} expiring Marktplaats listings")

    for listing in listings_resp.data:
        try:
            item_resp = db.table("items").select("*").eq("id", listing["item_id"]).single().execute()
            if not item_resp.data:
                continue
            item = item_resp.data

            db.table("listings").update({"status": "relisting"}).eq("id", listing["id"]).execute()

            db.table("jobs").insert({
                "user_id": _MVP_USER_ID,
                "item_id": listing["item_id"],
                "platform": "marktplaats",
                "action": "create",
                "status": "pending",
                "payload": item,
            }).execute()

            logger.info(f"Queued relist job for item {listing['item_id']} (listing {listing['id']})")
        except Exception as e:
            logger.error(f"Failed to queue relist for listing {listing['id']}: {e}")


async def _delist_one(listing: dict):
    db = get_db()
    creds_resp = (
        db.table("platform_credentials")
        .select("*")
        .eq("user_id", _MVP_USER_ID)
        .eq("platform", listing["platform"])
        .execute()
    )
    credentials = creds_resp.data[0] if creds_resp.data else {}

    try:
        platform = get_platform(listing["platform"])
        await platform.delete_listing(listing["platform_listing_id"], credentials)
        db.table("listings").update({
            "status": "delisted",
        }).eq("id", listing["id"]).execute()
        _log_event(listing["id"], "delisted", {})
    except Exception as e:
        logger.error(f"Delist failed for {listing['id']}: {e}")
        _log_event(listing["id"], "error", {"error": str(e)})
        raise


def _log_event(listing_id: str, event_type: str, payload: dict):
    db = get_db()
    db.table("sync_events").insert({
        "listing_id": listing_id,
        "event_type": event_type,
        "payload": payload,
    }).execute()
