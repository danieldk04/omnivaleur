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

    # A relist's "create" job (scheduled_for set) must never fire if the delete
    # job it's paired with actually failed — otherwise the old listing stays
    # live on the platform and this would create a duplicate. Hold/fail those
    # instead of handing them to the extension.
    ready = []
    for j in due:
        if j["action"] == "create" and j.get("scheduled_for"):
            paired_delete = (
                db.table("jobs")
                .select("status")
                .eq("user_id", user_id)
                .eq("item_id", j["item_id"])
                .eq("platform", j["platform"])
                .eq("action", "delete")
                .lte("created_at", j["created_at"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
                .data
            )
            if paired_delete and paired_delete[0]["status"] == "error":
                db.table("jobs").update({
                    "status": "error",
                    "result": {"error": "Skipped — the paired delist failed, so the old listing is still live; creating a new one would duplicate it."},
                    "done_at": now,
                }).eq("id", j["id"]).execute()
                db.table("listings").update({
                    "status": "error",
                    "error_message": "Relist aborted: delist of the old listing failed, so no new listing was created (would have duplicated it).",
                }).eq("item_id", j["item_id"]).eq("platform", j["platform"]).execute()
                continue
            # Delete not confirmed "done" yet (still pending/claimed, e.g. Chrome
            # was closed and just reopened) — hold the create job rather than
            # risk it firing before the old listing is actually gone. It stays
            # "pending" and will be re-checked on the next poll.
            if paired_delete and paired_delete[0]["status"] != "done":
                continue
        ready.append(j)

    return ready[:5]


@router.get("/relist-status")
async def relist_status(user_id: str = Depends(get_current_user)):
    """
    In-progress relists for the dashboard's Refresh view: any scheduled recreate
    ("create" job with a future/pending scheduled_for) plus the state of its
    paired delete, so the UI can show "old listing removed, new one in ~X min".
    """
    db = get_db()
    create_jobs = (
        db.table("jobs")
        .select("item_id,platform,status,scheduled_for,created_at")
        .eq("user_id", user_id)
        .eq("action", "create")
        .in_("status", ["pending", "claimed"])
        .execute()
        .data
    )
    out = []
    for j in create_jobs:
        if not j.get("scheduled_for"):
            continue  # only relist recreates carry a scheduled_for
        paired = (
            db.table("jobs")
            .select("status")
            .eq("user_id", user_id)
            .eq("item_id", j["item_id"])
            .eq("platform", j["platform"])
            .eq("action", "delete")
            .lte("created_at", j["created_at"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        out.append({
            "item_id": j["item_id"],
            "platform": j["platform"],
            "recreate_at": j["scheduled_for"],
            "recreate_status": j["status"],
            "delete_status": paired[0]["status"] if paired else None,
        })
    return out


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

        # If this delete is the first half of a relist, the extension may have
        # snapshotted the full live listing before removing it (imported items
        # otherwise carry almost no data). Merge that snapshot into the paired,
        # still-pending recreate ("create") job so the new listing is a faithful
        # copy instead of just title+price. Only fill fields that are actually
        # present in the snapshot and missing/empty in the current payload.
        captured = body.get("captured_listing") or {}
        if captured:
            paired = (
                db.table("jobs")
                .select("id,payload")
                .eq("user_id", user_id)
                .eq("item_id", job["item_id"])
                .eq("platform", job["platform"])
                .eq("action", "create")
                .eq("status", "pending")
                .gte("created_at", job["created_at"])
                .order("created_at")
                .limit(1)
                .execute()
                .data
            )
            if paired:
                payload = dict(paired[0].get("payload") or {})
                for key in ("description", "brand", "size", "condition", "color", "material", "category", "gender"):
                    val = captured.get(key)
                    if val and not payload.get(key):
                        payload[key] = val
                # Photos: prefer the fuller captured set (imports often keep only 1).
                cap_photos = captured.get("photo_urls") or []
                if len(cap_photos) > len(payload.get("photo_urls") or []):
                    payload["photo_urls"] = cap_photos
                # Price: the captured value is the real live Vinted price. The
                # dashboard's jittered price can be wrong for imported items, so
                # trust the captured one when present.
                cap_price = captured.get("price")
                if cap_price is not None:
                    try:
                        payload["price"] = float(cap_price)
                    except (TypeError, ValueError):
                        pass
                db.table("jobs").update({"payload": payload}).eq("id", paired[0]["id"]).execute()

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
            "suggested_item_id": best_id if best_score >= 0.9 else None,
            "platform_listed_at": row.get("platform_listed_at"),
            "status": "pending",
        }, on_conflict="user_id,platform,platform_listing_id").execute()


@router.post("/{job_id}/error")
async def fail_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    job = db.table("jobs").select("item_id,platform,action,payload").eq("id", job_id).eq("user_id", user_id).single().execute().data
    db.table("jobs").update({
        "status": "error",
        "result": body,
        "done_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()
    # A content-refresh or relist-delete bumped the listing's cooldown + daily
    # quota at enqueue time; since the job failed, give both back.
    rollback = ((job or {}).get("payload") or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)
    if job and job["action"] == "create":
        db.table("listings").update({
            "status": "error",
            "error_message": body.get("error", "Extension reported failure"),
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).eq("status", "pending").execute()
    elif job and job["action"] == "delete":
        # Without this, a failed delist leaves the listing "active" with no
        # visible error — the dashboard looks like the delist did nothing.
        db.table("listings").update({
            "status": "error",
            "error_message": body.get("error", "Delist failed — extension could not remove the listing"),
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()
    return {"ok": True}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data
