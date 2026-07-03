from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user
from datetime import datetime, timezone
from difflib import SequenceMatcher

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/pending")
async def get_pending_jobs(platform: str = None, user_id: str = Depends(get_current_user)):
    db = get_db()
    q = db.table("jobs").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    result = q.order("created_at").limit(20).execute()
    now = datetime.now(timezone.utc).isoformat()
    # Jobs with a future scheduled_for (used to jitter relist recreates) aren't due yet.
    due = [j for j in result.data if not j.get("scheduled_for") or j["scheduled_for"] <= now]
    return due[:5]


@router.post("/{job_id}/claim")
async def claim_job(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").update({
        "status": "claimed",
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).eq("user_id", user_id).eq("status", "pending").execute()
    if not result.data:
        raise HTTPException(status_code=409, detail="Job already claimed or not found")
    return result.data[0]


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    job = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute().data
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    db.table("jobs").update({
        "status": "done",
        "result": body,
        "done_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    if job["action"] == "create":
        if body.get("platform_listing_id"):
            existing = db.table("listings").select("id").eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()
            if existing.data:
                db.table("listings").update({
                    "platform_listing_id": body["platform_listing_id"],
                    "platform_listing_url": body.get("platform_listing_url"),
                    "status": "active",
                    "listed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()
            else:
                db.table("listings").insert({
                    "item_id": job["item_id"],
                    "platform": job["platform"],
                    "platform_listing_id": body["platform_listing_id"],
                    "platform_listing_url": body.get("platform_listing_url"),
                    "status": "active",
                    "listed_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
        else:
            db.table("listings").update({
                "status": "error",
                "error_message": "Extension completed job but returned no platform_listing_id",
            }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()

    elif job["action"] == "delete":
        db.table("listings").update({"status": "delisted"}).eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()

    elif job["action"] == "content_refresh":
        # Listing stays active — this is an in-place edit, not a new listing.
        pass

    elif job["action"] == "scan":
        _store_scan_results(db, job, body.get("listings", []))

    return {"ok": True}


def _store_scan_results(db, job, scraped: list[dict]):
    """
    Persist scraped "my listings" cards as import_candidates for manual review.
    Never touches the items/listings tables directly — a human links or
    imports each candidate explicitly via /api/imports.
    """
    if not scraped:
        return
    items = db.table("items").select("id,title").eq("user_id", job["user_id"]).execute().data or []
    for row in scraped:
        platform_listing_id = row.get("platform_listing_id")
        title = row.get("title") or ""
        if not platform_listing_id:
            continue
        best_id, best_score = None, 0.0
        for it in items:
            score = SequenceMatcher(None, title.lower(), (it.get("title") or "").lower()).ratio()
            if score > best_score:
                best_id, best_score = it["id"], score
        db.table("import_candidates").upsert({
            "user_id": job["user_id"],
            "platform": job["platform"],
            "platform_listing_id": platform_listing_id,
            "platform_listing_url": row.get("platform_listing_url"),
            "title": title,
            "price": row.get("price"),
            "photo_url": row.get("photo_url"),
            "suggested_item_id": best_id if best_score >= 0.6 else None,
            "status": "pending",
        }, on_conflict="user_id,platform,platform_listing_id").execute()


@router.post("/{job_id}/error")
async def fail_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    job = db.table("jobs").select("item_id,platform,action").eq("id", job_id).eq("user_id", user_id).single().execute().data
    db.table("jobs").update({
        "status": "error",
        "result": body,
        "done_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()
    if job and job["action"] == "create":
        db.table("listings").update({
            "status": "error",
            "error_message": body.get("error", "Extension reported failure"),
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).eq("status", "pending").execute()
    return {"ok": True}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data
