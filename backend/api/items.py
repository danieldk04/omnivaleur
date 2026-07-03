from fastapi import APIRouter, HTTPException, Depends
from backend.models import ItemCreate, ItemOut
from backend.database import get_db
from backend.api.deps import get_current_user
import uuid

_PENDING_COLUMNS = set()

router = APIRouter(prefix="/items", tags=["items"])


def _strip_missing(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in _PENDING_COLUMNS}


@router.post("/", response_model=dict)
async def create_item(item: ItemCreate, user_id: str = Depends(get_current_user)):
    db = get_db()
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    if not data.get("sku"):
        data["sku"] = f"REV-{data['id'][:8].upper()}"
    result = db.table("items").insert(_strip_missing(data)).execute()
    return result.data[0]


@router.get("/", response_model=list)
async def list_items(limit: int = 50, offset: int = 0, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = (
        db.table("items")
        .select("*")
        .eq("user_id", user_id)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


@router.get("/{item_id}")
async def get_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    return result.data


@router.patch("/{item_id}")
async def update_item(item_id: str, updates: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = (
        db.table("items")
        .update(_strip_missing(updates))
        .eq("id", item_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    return result.data[0]


@router.delete("/{item_id}")
async def delete_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    # Verify ownership
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    listing_ids = [l["id"] for l in (db.table("listings").select("id").eq("item_id", item_id).execute().data or [])]
    for lid in listing_ids:
        db.table("sync_events").delete().eq("listing_id", lid).execute()
    db.table("listings").delete().eq("item_id", item_id).execute()
    db.table("jobs").delete().eq("item_id", item_id).execute()
    db.table("items").delete().eq("id", item_id).execute()
    return {"deleted": item_id}


@router.post("/{item_id}/delist")
async def delist_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    from backend.services.crosslist import delist_all_platforms
    results = await delist_all_platforms(item_id, user_id)
    return {"item_id": item_id, "results": results}


@router.post("/{item_id}/crosslist")
async def crosslist_item(item_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    platforms = body.get("platforms", [])
    if not platforms:
        raise HTTPException(status_code=400, detail="No platforms specified")
    from backend.services.crosslist import publish_to_platforms
    results = await publish_to_platforms(item_id, platforms, user_id)
    return {"item_id": item_id, "results": results}
