from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.models import ItemCreate
from datetime import datetime, timezone
from difflib import SequenceMatcher
import uuid

router = APIRouter(prefix="/imports", tags=["imports"])

SCANNABLE_PLATFORMS = {"vinted", "marktplaats", "2dehands"}
MATCH_THRESHOLD = 0.9


def _map_condition(raw: str | None) -> str:
    """Map a platform's free-text condition onto our new/good/fair/poor scale."""
    s = (raw or "").strip().lower()
    if not s:
        return "good"
    if "new" in s or "nieuw" in s or "tags" in s or "prijskaartje" in s:
        return "new"
    if "very good" in s or "zo goed als nieuw" in s or "good" in s or "goed" in s:
        return "good"
    if "satisf" in s or "redelijk" in s or "fair" in s:
        return "fair"
    if "poor" in s or "slecht" in s or "gebruikt" in s:
        return "poor"
    return "good"


def _photos_from_candidate(cand: dict) -> list[str]:
    """Full photo list if the scan captured it, else the single thumbnail."""
    photos = cand.get("photo_urls")
    if isinstance(photos, list) and photos:
        return [p for p in photos if p]
    return [cand["photo_url"]] if cand.get("photo_url") else []


def _item_data_from_candidate(cand: dict, body: dict | None = None) -> dict:
    """
    Build the full item payload from a scraped candidate, so an import lands
    with everything the scan captured (all photos, description, brand, size,
    condition, category, colour, material). `body` overrides any field the user
    edited in the import dialog and carries data the scan can't see (e.g.
    purchase_price).
    """
    body = body or {}

    def pick(key, cand_key=None, default=None):
        v = body.get(key)
        return v if v is not None else (cand.get(cand_key or key) or default)

    return {
        "title": pick("title") or "Untitled",
        "price": body.get("price") if body.get("price") is not None else (cand.get("price") or 0),
        "photo_urls": body.get("photo_urls") or _photos_from_candidate(cand),
        "description": pick("description"),
        "purchase_price": body.get("purchase_price"),
        "brand": pick("brand"),
        "size": pick("size"),
        "condition": body.get("condition") or _map_condition(cand.get("condition")),
        "category": pick("category"),
        "gender": pick("gender"),
        "color": pick("color"),
        "material": pick("material"),
    }


def _best_match(title: str, items: list[dict]) -> str | None:
    """Titles are published verbatim to the platform, so a genuine match scores near 1.0."""
    best_id, best_score = None, 0.0
    for it in items:
        score = SequenceMatcher(None, (title or "").lower(), (it.get("title") or "").lower()).ratio()
        if score > best_score:
            best_id, best_score = it["id"], score
    return best_id if best_score >= MATCH_THRESHOLD else None


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
    candidates = result.data or []
    if candidates:
        items = db.table("items").select("id,title").eq("user_id", user_id).execute().data or []
        for c in candidates:
            c["suggested_item_id"] = _best_match(c.get("title"), items)
    return candidates


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
    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    if existing.data:
        db.table("listings").update({
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": listed_at,
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("listings").insert({
            "item_id": item_id,
            "platform": cand["platform"],
            "platform_listing_id": cand["platform_listing_id"],
            "platform_listing_url": cand["platform_listing_url"],
            "status": "active",
            "listed_at": listed_at,
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

    item_data = _item_data_from_candidate(cand, body)
    item = ItemCreate(**item_data)
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    data["sku"] = f"IMP-{data['id'][:8].upper()}"
    created = db.table("items").insert(data).execute().data[0]

    listed_at = cand.get("platform_listed_at") or datetime.now(timezone.utc).isoformat()
    db.table("listings").insert({
        "item_id": created["id"],
        "platform": cand["platform"],
        "platform_listing_id": cand["platform_listing_id"],
        "platform_listing_url": cand["platform_listing_url"],
        "status": "active",
        "listed_at": listed_at,
    }).execute()

    db.table("import_candidates").update({"status": "imported"}).eq("id", candidate_id).execute()
    return {"item": created}


@router.post("/bulk-import")
async def bulk_import_candidates(body: dict = None, user_id: str = Depends(get_current_user)):
    """
    Process every pending import candidate in one go: candidates with a high-confidence
    suggested_item_id get linked to that item, everything else becomes a new item
    (title/price/photo straight from the scrape, condition defaults to 'good' since
    scraping can't see purchase price/brand/size — those stay editable on the item after).
    """
    db = get_db()
    platform = (body or {}).get("platform")
    q = db.table("import_candidates").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    candidates = q.execute().data or []

    linked, created, failed = 0, 0, 0
    now = datetime.now(timezone.utc).isoformat()
    items = db.table("items").select("id,title").eq("user_id", user_id).execute().data or []

    for cand in candidates:
        try:
            listed_at = cand.get("platform_listed_at") or now
            match_id = _best_match(cand.get("title"), items)
            if match_id:
                existing = db.table("listings").select("id").eq("item_id", match_id).eq("platform", cand["platform"]).execute()
                if existing.data:
                    db.table("listings").update({
                        "platform_listing_id": cand["platform_listing_id"],
                        "platform_listing_url": cand["platform_listing_url"],
                        "status": "active",
                        "listed_at": listed_at,
                    }).eq("id", existing.data[0]["id"]).execute()
                else:
                    db.table("listings").insert({
                        "item_id": match_id,
                        "platform": cand["platform"],
                        "platform_listing_id": cand["platform_listing_id"],
                        "platform_listing_url": cand["platform_listing_url"],
                        "status": "active",
                        "listed_at": listed_at,
                    }).execute()
                db.table("import_candidates").update({"status": "linked"}).eq("id", cand["id"]).execute()
                linked += 1
            else:
                item_data = {
                    "title": cand["title"] or "Untitled",
                    "price": cand["price"] or 0,
                    "photo_urls": [cand["photo_url"]] if cand.get("photo_url") else [],
                    "condition": "good",
                }
                item = ItemCreate(**item_data)
                data = item.model_dump()
                data["id"] = str(uuid.uuid4())
                data["user_id"] = user_id
                data["sku"] = f"IMP-{data['id'][:8].upper()}"
                created_item = db.table("items").insert(data).execute().data[0]

                db.table("listings").insert({
                    "item_id": created_item["id"],
                    "platform": cand["platform"],
                    "platform_listing_id": cand["platform_listing_id"],
                    "platform_listing_url": cand["platform_listing_url"],
                    "status": "active",
                    "listed_at": listed_at,
                }).execute()

                db.table("import_candidates").update({"status": "imported"}).eq("id", cand["id"]).execute()
                items.append({"id": created_item["id"], "title": created_item["title"]})
                created += 1
        except Exception:
            failed += 1

    return {"linked": linked, "created": created, "failed": failed}


@router.post("/{candidate_id}/ignore")
async def ignore_candidate(candidate_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    db.table("import_candidates").update({"status": "ignored"}).eq("id", candidate_id).eq("user_id", user_id).execute()
    return {"ok": True}
