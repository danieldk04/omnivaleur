"""
Listing refresh ("bump old listings back up").

Every strategy here operates only within each platform's own rules — nothing
fakes engagement, spoofs bot traffic, or evades a platform's abuse detection.
Nothing is "guaranteed" to change ranking; it's rate-limited on purpose so it
can't look like scripted spam.

Per-platform, what's actually available differs a lot:

- "content" (Vinted only): light edit of an existing listing (price nudge,
  photo re-order). Lowest impact, zero account risk. Not offered for
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
from datetime import datetime, timezone, timedelta
from backend.database import get_db
from backend.platforms import get_platform

logger = logging.getLogger(__name__)

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
RELIST_DELAY_MIN_MINUTES = 45   # recreate happens 45min-4h after delete
RELIST_DELAY_MAX_MINUTES = 240
CONTENT_PRICE_JITTER_PCT = 0.02  # +/-2% nudge, rounded to a sane price


class RefreshError(Exception):
    pass


def _check_and_increment_quota(db, user_id: str) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    row = db.table("refresh_quota").select("count").eq("user_id", user_id).eq("day", today).execute()
    count = row.data[0]["count"] if row.data else 0
    if count >= MAX_REFRESHES_PER_USER_PER_DAY:
        raise RefreshError(
            f"Daily refresh limit reached ({MAX_REFRESHES_PER_USER_PER_DAY}/day). "
            "This cap is intentional — it keeps refresh activity looking like normal "
            "shop upkeep instead of a bulk/bot pattern."
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


def _check_cooldown(listing: dict) -> None:
    last = listing.get("last_refreshed_at")
    if not last:
        return
    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    elapsed = datetime.now(timezone.utc) - last_dt
    if elapsed < timedelta(days=MIN_COOLDOWN_DAYS):
        remaining = timedelta(days=MIN_COOLDOWN_DAYS) - elapsed
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


async def refresh_listing(item_id: str, platform: str, user_id: str, strategy: str) -> dict:
    """
    Queue a refresh for one listing.
    strategy: "content" (safe edit-in-place, Vinted only) or
              "relist" (delete + scheduled recreate, Vinted/Marktplaats/2dehands).
    """
    allowed = PLATFORM_STRATEGIES.get(platform, set())
    if strategy not in allowed:
        raise RefreshError(
            f"'{strategy}' isn't available for {platform}. "
            f"Available here: {', '.join(sorted(allowed)) or 'none'}."
        )

    db = get_db()

    item_resp = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise RefreshError("Item not found")
    item = item_resp.data[0]

    listing_resp = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("status", "active")
        .execute()
    )
    if not listing_resp.data:
        raise RefreshError("No active listing on this platform")
    listing = listing_resp.data[0]

    if platform not in REFRESH_CAPABLE_PLATFORMS:
        raise RefreshError(f"Refresh isn't available for {platform} yet")

    _check_cooldown(listing)
    _check_and_increment_quota(db, user_id)

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
        payload = {
            **item,
            "platform_listing_id": listing["platform_listing_id"],
            "platform_listing_url": listing["platform_listing_url"],
            "price": float(item["price"]) if item.get("price") not in (None, "") else None,
            "photo_urls": _shuffled_photos(item.get("photo_urls") or []),
            "_refresh_rollback": rollback,
        }
        job = db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": platform,
            "action": "content_refresh",
            "status": "pending",
            "payload": payload,
        }).execute().data[0]

        db.table("listings").update({
            "last_refreshed_at": now.isoformat(),
            "refresh_count": (listing.get("refresh_count") or 0) + 1,
        }).eq("id", listing["id"]).execute()

        return {"strategy": "content", "job_id": job["id"], "status": "queued"}

    # strategy == "relist": delete now, recreate after a randomized delay.
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
    }
    db.table("jobs").insert({
        "user_id": user_id,
        "item_id": item_id,
        "platform": platform,
        "action": "delete",
        "status": "pending",
        "payload": delete_payload,
    }).execute()

    delay_minutes = random.randint(RELIST_DELAY_MIN_MINUTES, RELIST_DELAY_MAX_MINUTES)
    scheduled_for = (now + timedelta(minutes=delay_minutes)).isoformat()

    create_payload = {
        **item,
        # Slight variation so the new listing isn't byte-identical to the old one —
        # legitimate reasons (price update, reordered photos), not spoofing.
        "price": _jittered_price(float(item.get("price") or 0)) or item.get("price"),
        "photo_urls": _shuffled_photos(item.get("photo_urls") or []),
    }
    # A Vinted account lives on ONE country domain (e.g. vinted.nl). The create
    # form must be opened on that same domain, otherwise the recreate lands on
    # the wrong catalog — the same domain trap that broke delete. Carry the real
    # origin (recovered from the old listing URL) so the extension opens
    # {origin}/items/new instead of a hardcoded vinted.com.
    if platform == "vinted" and listing.get("platform_listing_url"):
        try:
            from urllib.parse import urlparse
            p = urlparse(listing["platform_listing_url"])
            if p.scheme and p.netloc:
                create_payload["_create_origin"] = f"{p.scheme}://{p.netloc}"
        except Exception:
            pass
    db.table("jobs").insert({
        "user_id": user_id,
        "item_id": item_id,
        "platform": platform,
        "action": "create",
        "status": "pending",
        "payload": create_payload,
        "scheduled_for": scheduled_for,
    }).execute()

    db.table("listings").update({
        "status": "relisting",
        "last_refreshed_at": now.isoformat(),
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
    }).eq("id", listing["id"]).execute()

    logger.info(f"Queued relist for item {item_id} on {platform}, recreate scheduled in {delay_minutes}min")
    return {
        "strategy": "relist",
        "status": "queued",
        "recreate_scheduled_for": scheduled_for,
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
    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(days=MIN_COOLDOWN_DAYS)).isoformat()

    item_ids = [r["id"] for r in db.table("items").select("id").eq("user_id", user_id).execute().data]
    if not item_ids:
        return []

    q = (
        db.table("listings")
        .select("*")
        .in_("item_id", item_ids)
        .eq("platform", platform)
        .eq("status", "active")
        .lt("listed_at", cutoff)
        .order("listed_at")
        .limit(limit)
    )
    candidates = [
        l for l in q.execute().data
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
    item_resp = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise RefreshError("Item not found")

    listing_resp = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", "etsy")
        .in_("status", ["active", "sold", "error"])
        .execute()
    )
    if not listing_resp.data:
        raise RefreshError("No Etsy listing found for this item")
    listing = listing_resp.data[0]
    if not listing.get("platform_listing_id"):
        raise RefreshError("This Etsy listing has no known listing ID")

    creds_resp = (
        db.table("platform_credentials")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "etsy")
        .execute()
    )
    if not creds_resp.data:
        raise RefreshError("Etsy isn't connected")
    credentials = creds_resp.data[0]

    platform = get_platform("etsy")
    result = await platform.renew_listing(listing["platform_listing_id"], credentials)

    now = datetime.now(timezone.utc).isoformat()
    db.table("listings").update({
        "status": "active",
        "last_refreshed_at": now,
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
    }).eq("id", listing["id"]).execute()

    return {"strategy": "renew", "status": "renewed", "etsy_state": result.get("state")}


async def relist_ended_ebay_listing(item_id: str, user_id: str) -> dict:
    """
    Republish an ENDED eBay offer via eBay's own relist mechanism. Refuses to run
    if the listing is still active — eBay's duplicate-listing policy prohibits two
    live listings for the same item, so this only ever touches offers that have
    already ended (sold, withdrawn, or expired).
    """
    db = get_db()
    item_resp = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise RefreshError("Item not found")

    listing_resp = (
        db.table("listings")
        .select("*")
        .eq("item_id", item_id)
        .eq("platform", "ebay")
        .execute()
    )
    if not listing_resp.data:
        raise RefreshError("No eBay listing found for this item")
    listing = listing_resp.data[0]
    offer_id = listing.get("platform_offer_id") or listing.get("platform_listing_id")
    if not offer_id:
        raise RefreshError("This eBay listing has no known offer ID")

    creds_resp = (
        db.table("platform_credentials")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "ebay")
        .execute()
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
    db.table("listings").update({
        "status": "active",
        "platform_listing_id": result["platform_listing_id"],
        "platform_listing_url": result["platform_listing_url"],
        "listed_at": now,
        "last_refreshed_at": now,
        "refresh_count": (listing.get("refresh_count") or 0) + 1,
    }).eq("id", listing["id"]).execute()

    return {"strategy": "relist_ended", "status": "relisted", **result}
