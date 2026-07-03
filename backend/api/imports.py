from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.models import ItemCreate
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/imports", tags=["imports"])

SCANNABLE_PLATFORMS = {"vinted", "marktplaats", "2dehands"}


@router.post("/scan/{platform}")
async def start_scan(platform: str, user_id: str = Depends(get_current_user)):
    if platform not in SCANNABLE_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Scanning isn't available for {platform}")
    db = get_db()
    job = db.table("jobs").insert({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "item_id": None,
        "platform": platform,
        "action": "scan",
        "status": "pending",
        "payload": {},
    }).execute()
    return {"job_id": job.data[0]["id"]}


@router.get("/")
async def list_import_candidates(platform: str = None, status: str = "pending", user_id: str = Depends(get_current_user)):
    db = get_db()
    q = db.table("import_candidates").select("*").eq("user_id", user_id)
    if platform:
        q = q.eq("platform", platform)
    if status:
        q = q.eq("status", status)
    result = q.order("created_at", desc=True).limit(500).execute()
    return result.data


@router.post("/{candidate_id}/link")
async def link_candidate(candidate_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """Attach a scraped listing to an existing item — no new item, no guessed fields."""
    item_id = body.get("item_id")
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    db = get_db()
    cand = db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute().data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = db.table("listings").select("id").eq("item_id", item_id).eq("platform", cand["platform"]).execute()
    now = datetime.now(timezone.utc).isoformat()
    if existing.data:
        db.table("listings").update({
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": now,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("listings").insert({
            "item_id": item_id,
            "platform": cand["platform"],
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": now,
        }).execute()

    db.table("import_candidates").update({"status": "linked"}).eq("id", candidate_id).execute()
    return {"ok": True}


@router.post("/{candidate_id}/create-item")
async def create_item_from_candidate(candidate_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """
    Create a new item from a scraped listing. `body` carries the fields scraping
    can't see (purchase_price, brand, size, condition, category, color, material, ...)
    plus optional overrides for title/price/photo_urls that were pre-filled from the scrape.
    """
    db = get_db()
    cand = db.table("import_candidates").select("*").eq("id", candidate_id).eq("user_id", user_id).single().execute().data
    if not cand:
        raise HTTPException(status_code=404, detail="Import candidate not found")

    item_data = {
        "title": body.get("title") or cand["title"] or "Untitled",
        "price": body.get("price") if body.get("price") is not None else (cand["price"] or 0),
        "photo_urls": body.get("photo_urls") or ([cand["photo_url"]] if cand.get("photo_url") else []),
        "description": body.get("description"),
        "purchase_price": body.get("purchase_price"),
        "brand": body.get("brand"),
        "size": body.get("size"),
        "condition": body.get("condition", "good"),
        "category": body.get("category"),
        "gender": body.get("gender"),
        "color": body.get("color"),
        "material": body.get("material"),
    }
    item = ItemCreate(**item_data)
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    data["sku"] = f"IMP-{data['id'][:8].upper()}"
    created = db.table("items").insert(data).execute().data[0]

    now = datetime.now(timezone.utc).isoformat()
    db.table("listings").insert({
        "item_id": created["id"],
        "platform": cand["platform"],
        "platform_listing_id": cand["platform_listing_id"],
        "platform_listing_url": cand["platform_listing_url"],
        "status": "active",
        "listed_at": now,
    }).execute()

    db.table("import_candidates").update({"status": "imported"}).eq("id", candidate_id).execute()
    return {"item": created}


@router.post("/{candidate_id}/ignore")
async def ignore_candidate(candidate_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    db.table("import_candidates").update({"status": "ignored"}).eq("id", candidate_id).eq("user_id", user_id).execute()
    return {"ok": True}
