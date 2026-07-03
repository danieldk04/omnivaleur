from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from backend.models import ListingCreate
from backend.database import get_db
from backend.services.crosslist import publish_to_platforms, handle_item_sold
from backend.services.relist import refresh_listing, refresh_stale_listings, RefreshError, REFRESH_CAPABLE_PLATFORMS
from backend.api.deps import get_current_user
from datetime import datetime, timezone

router = APIRouter(prefix="/listings", tags=["listings"])


def _user_item_ids(db, user_id: str) -> list[str]:
    """Return all item IDs belonging to this user."""
    rows = db.table("items").select("id").eq("user_id", user_id).execute()
    return [r["id"] for r in (rows.data or [])]


@router.get("/")
async def list_all_listings(
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
    return result.data


@router.post("/publish")
async def publish_listing(
    body: ListingCreate,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    results = await publish_to_platforms(body.item_id, body.platforms, user_id)
    return {"results": results}


@router.get("/item/{item_id}")
async def get_listings_for_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    result = db.table("listings").select("*").eq("item_id", item_id).execute()
    return result.data


@router.post("/mark-active")
async def mark_listing_active(body: dict, user_id: str = Depends(get_current_user)):
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform required")
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    now = datetime.now(timezone.utc).isoformat()
    existing = db.table("listings").select("id").eq("item_id", item_id).eq("platform", platform).execute()
    if existing.data:
        db.table("listings").update({
            "status": "active",
            "error_message": None,
            "listed_at": now,
        }).eq("item_id", item_id).eq("platform", platform).execute()
    else:
        db.table("listings").insert({
            "item_id": item_id,
            "platform": platform,
            "status": "active",
            "listed_at": now,
        }).execute()
    return {"ok": True}


@router.post("/sold")
async def mark_sold(item_id: str, platform: str, background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    background_tasks.add_task(handle_item_sold, item_id, platform)
    return {"status": "delist_triggered"}
