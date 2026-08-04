from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from backend.models import ListingCreate
from backend.database import get_db
from backend.services.crosslist import publish_to_platforms, handle_item_sold, CrosslistValidationError
from backend.services.relist import (
    refresh_listing, refresh_stale_listings, renew_etsy_listing, relist_ended_ebay_listing,
    RefreshError, REFRESH_CAPABLE_PLATFORMS,
)
from backend.api.deps import get_current_user, require_active_subscription
from datetime import datetime, timezone
import re
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
    """Return all item IDs belonging to this user."""
    rows = db.table("items").select("id").eq("user_id", user_id).execute()
    return [r["id"] for r in (rows.data or [])]


@router.get("/")
def list_all_listings(
    limit: int = 200,
    platform: str = None,
    status: str = None,
    user_id: str = Depends(get_current_user),
):
    db = get_db()
    item_ids = _user_item_ids(db, user_id)
    if not item_ids:
        return []
    q = db.table("listings").select("*").in_("item_id", item_ids)
    if platform:
        q = q.eq("platform", platform)
    if status:
        q = q.eq("status", status)
    result = q.limit(2000).execute()
    listings = result.data or []
    # Attach each listing's item title so the extension can title-match sold ads
    # for listings that have no platform_listing_id (hand-marked / unconfirmed).
    ids = list({l["item_id"] for l in listings if l.get("item_id")})
    if ids:
        items = db.table("items").select("id,title").in_("id", ids).execute().data or []
        titles = {it["id"]: it.get("title") for it in items}
        for l in listings:
            l["title"] = titles.get(l.get("item_id"))
    return listings


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
    return {"ok": True, "listing": (row[0] if row else None)}


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

    Each order carries the item's SKU (the "(1234)" prefix the app embeds in every
    Vinted title), the price paid, and whether it's a genuine sale (`sold: true`)
    or a cancelled/refunded order (`sold: false`, ignored).

    Safety: we only act on an EXACT, UNIQUE SKU match scoped to the caller's own
    items — an ambiguous or unknown SKU is skipped, never guessed, so a bad scrape
    can't mark the wrong item sold (and trigger its cross-platform delist).
    Already-sold items are only touched to backfill a missing sold_price, so this
    endpoint can run every few minutes without re-queuing delist jobs.

    Body: {orders: [{sku, price, sold}]}
    """
    orders = body.get("orders")
    if not isinstance(orders, list):
        raise HTTPException(status_code=400, detail="orders must be a list")

    db = get_db()
    marked_sold = 0
    price_backfilled = 0
    matched = 0
    unmatched_skus = []
    sold_orders = [o for o in orders if isinstance(o, dict) and o.get("sold")]
    logger.info("[sold] reconcile-vinted-orders: received %d orders (%d marked sold) for user=%s",
                len(orders), len(sold_orders), user_id)

    for o in orders:
        if not isinstance(o, dict) or not o.get("sold"):
            continue
        sku = str(o.get("sku") or "").strip()
        if not sku:
            continue
        price = _parse_sku_price(o.get("price"))

        # Exact + UNIQUE match only. len != 1 → ambiguous/unknown → skip.
        items = db.table("items").select("id").eq("user_id", user_id).eq("sku", sku).execute().data or []
        if len(items) != 1:
            unmatched_skus.append(sku)
            continue
        matched += 1
        item_id = items[0]["id"]

        vinted_rows = (
            db.table("listings").select("id,status,sold_price")
            .eq("item_id", item_id).eq("platform", "vinted").execute().data or []
        )
        sold_row = next((l for l in vinted_rows if l["status"] == "sold"), None)

        if sold_row:
            # Already recorded — just fill in the real price if we didn't have it.
            if price is not None and sold_row.get("sold_price") in (None, 0):
                try:
                    db.table("listings").update({"sold_price": price}).eq("id", sold_row["id"]).execute()
                    price_backfilled += 1
                except Exception:
                    pass
            continue

        # New sale. Ensure a Vinted listing row exists so it shows in analytics,
        # then run the canonical sold flow (records price + delists other platforms).
        if not vinted_rows:
            db.table("listings").insert({
                "item_id": item_id, "platform": "vinted", "status": "active",
            }).execute()
        try:
            await handle_item_sold(item_id, "vinted", price)
            marked_sold += 1
        except Exception:
            pass

    logger.info("[sold] reconcile-vinted-orders: matched=%d newly_sold=%d price_backfilled=%d unmatched=%d unmatched_skus=%s",
                matched, marked_sold, price_backfilled, len(unmatched_skus), unmatched_skus)
    return {"ok": True, "marked_sold": marked_sold, "price_backfilled": price_backfilled}
