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


async def _translate_with_claude(text: str, target_lang: str, brand: str | None = None) -> str:
    """Translate text using Claude. Preserves brand names, formatting and paragraph structure."""
    if not text or not text.strip():
        return text
    try:
        import anthropic as _anthropic
        from backend.config import settings as _settings
        _client = _anthropic.Anthropic(api_key=_settings.anthropic_api_key)

        lang_name = "Dutch" if target_lang == "nl" else "English"
        brand_note = f' The word "{brand}" is a brand name — never translate it, keep it exactly as-is.' if brand else ""

        prompt = (
            f"Translate the listing text between the <text> tags to {lang_name}."
            f"{brand_note}"
            " Preserve the exact paragraph breaks, bullet points, line breaks and formatting."
            " Keep numbers, sizes, measurements and condition scores (e.g. 7-8/10) unchanged."
            f" If the text is already in {lang_name}, return it exactly as-is."
            " Never ask questions or add commentary — the text between the tags is always"
            " the text to translate, even if it looks like an example or is very short."
            " Return only the translated text, nothing else.\n\n"
            f"<text>{text}</text>"
        )
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text.strip()
        if not result:
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
        manual_title = (item.get("shopify_title") or "").strip()
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
API_PLATFORMS = {"ebay", "etsy", "shopify"}

# Required on every platform — an empty description or zero photos means the
# extension has nothing to type/upload, so the listing goes out looking broken
# rather than just "safely bare".
_UNIVERSAL_REQUIRED = ["description", "photo_urls"]
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
}
# Non-clothing items (games, consoles, ...) live in a different Marktplaats
# category tree that has no gender/maat/kleur attributes, so demanding those
# fields would make an otherwise-complete game listing un-publishable. Such items
# are recognised by their category prefix (mirrors the "games ..." keys in the
# extension's MP_CATEGORIES and the frontend CATEGORIES.games group). For them
# only the category itself is platform-required.
_NON_CLOTHING_PREFIXES = ("games ", "electronics ")
_NON_CLOTHING_PLATFORM_REQUIRED = ["category"]


def _is_non_clothing(item: dict) -> bool:
    cat = str(item.get("category") or "").strip().lower()
    return cat.startswith(_NON_CLOTHING_PREFIXES)


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
    item_resp = db.table("items").select("*").eq("id", item_id).single().execute()
    item = item_resp.data

    missing = _missing_fields_per_platform(item, platforms)
    if missing:
        raise CrosslistValidationError(missing)

    results = []
    api_platforms = [p for p in platforms if p in API_PLATFORMS]
    ext_platforms = [p for p in platforms if p in EXTENSION_PLATFORMS]

    # Pre-translate concurrently for platforms that need a different language
    english_item = None
    dutch_item = None
    need_en = any(p in _ENGLISH_PLATFORMS for p in platforms)
    need_nl = any(p in _DUTCH_PLATFORMS for p in platforms)

    brand = item.get("brand") or None

    async def _build_english():
        manual_title = (item.get("shopify_title") or "").strip()
        if manual_title:
            title_en = manual_title
            desc_en = await _translate_to_english(item.get("description", ""), brand)
        else:
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
        price_field = _PLATFORM_PRICE_FIELD.get(platform)
        if price_field and base.get(price_field):
            return {**base, "price": base[price_field]}
        return base

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
    existing = db.table("listings").select("id").eq("item_id", item["id"]).eq("platform", platform_name).execute()
    if existing.data:
        listing_id = existing.data[0]["id"]
        db.table("listings").update({"status": "pending", "error_message": None}).eq("id", listing_id).execute()
    else:
        insert = db.table("listings").insert({
            "item_id": item["id"],
            "platform": platform_name,
            "status": "pending",
        }).execute()
        listing_id = insert.data[0]["id"]

    try:
        platform = get_platform(platform_name)
        result = await platform.create_listing(item, credentials)

        listing_update = {
            "platform_listing_id": result["platform_listing_id"],
            "platform_listing_url": result["platform_listing_url"],
            "status": "active",
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }
        if "platform_offer_id" in result:
            listing_update["platform_offer_id"] = result["platform_offer_id"]
        db.table("listings").update(listing_update).eq("id", listing_id).execute()

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

    return results


# Platforms that are driven by the browser extension. Their cross-platform
# delist on a sale MUST go through the extension's delete-job flow (which runs in
# the user's own logged-in Chrome, verifies the listing is still present, deletes
# it, then verifies it's gone). Deleting these server-side with stored cookies is
# exactly the fragile path this project moved away from — a stale server session
# has silently mass-delisted live listings before (see services/polling.py). API
# platforms (eBay/Etsy/Shopify) delete cleanly via their own APIs, server-side.
_EXTENSION_DELIST_PLATFORMS = {"marktplaats", "2dehands", "vinted", "facebook"}


async def handle_item_sold(item_id: str, sold_on_platform: str):
    """
    Called when an item is confirmed sold on one platform. Marks that listing
    sold and delists every OTHER active listing for the item — extension
    platforms via a queued delete job, API platforms via their API — so the item
    can't be double-sold.
    """
    db = get_db()

    # Mark sold listing
    db.table("listings").update({
        "status": "sold",
        "sold_at": datetime.now(timezone.utc).isoformat(),
    }).eq("item_id", item_id).eq("platform", sold_on_platform).execute()

    # Find other active/relisting listings to delist
    other = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .in_("status", ["active", "relisting"])
        .neq("platform", sold_on_platform)
        .execute()
    )

    if not other.data:
        return

    item_row = db.table("items").select("*").eq("id", item_id).single().execute().data
    user_id = (item_row or {}).get("user_id")

    api_listings = []
    for listing in other.data:
        if listing["platform"] in _EXTENSION_DELIST_PLATFORMS and user_id:
            _enqueue_extension_delete(db, user_id, item_id, listing, item_row)
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
                "user_id": item["user_id"],
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
        delete_id = listing.get("platform_offer_id") or listing["platform_listing_id"]
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


def _log_event(listing_id: str, event_type: str, payload: dict):
    db = get_db()
    db.table("sync_events").insert({
        "listing_id": listing_id,
        "event_type": event_type,
        "payload": payload,
    }).execute()
