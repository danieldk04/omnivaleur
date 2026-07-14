from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.api.imports import _backfill_item_from_candidate
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# A claim older than this with no progress means the run was interrupted (the
# MV3 service worker gets killed the moment Chrome closes or after ~30s idle, so
# a job can be claimed but never reach /complete or /error). Nothing ever
# re-surfaced those, so they hung "claimed" forever — blocking paired relists and
# tripping the "extension is working" banner. We recover them below.
STALE_CLAIM_MINUTES = 5
MAX_RECLAIMS = 2


def _parse_ts(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _recover_stale_claims(db, user_id: str, platform: str, now_dt: datetime) -> None:
    """
    Find jobs stuck in 'claimed' with no recent activity and get them unstuck.

    Retry-safe jobs are reset to 'pending' so the extension runs them again:
      - delete: the extension verifies the listing is still in the wardrobe and
        no-ops if it's already gone, so a re-run can't double-delete.
      - scan: read-only.
      - content_refresh: re-edits the same listing (idempotent).
      - RELIST create (has scheduled_for): its paired delete already removed the
        old listing, so republishing can't create a duplicate.

    NOT retry-safe → marked 'error' instead of retried:
      - an INITIAL crosslist create (no scheduled_for): if the first attempt did
        publish but the completion just wasn't recorded, re-running would post a
        DUPLICATE listing. Safer to surface an error and let the user republish.
      - anything that already hit the reclaim cap (persistently failing).
    """
    stale_before = (now_dt - timedelta(minutes=STALE_CLAIM_MINUTES)).isoformat()
    q = (
        db.table("jobs")
        .select("id,action,item_id,platform,scheduled_for,claimed_at,result")
        .eq("user_id", user_id)
        .eq("status", "claimed")
    )
    if platform:
        q = q.eq("platform", platform)
    for j in q.execute().data:
        claimed = _parse_ts(j.get("claimed_at"))
        if claimed and claimed.isoformat() > stale_before:
            continue  # claimed recently — genuinely in progress
        res = j.get("result") or {}
        prog_at = _parse_ts((res.get("_progress") or {}).get("at")) if isinstance(res, dict) else None
        if prog_at and prog_at.isoformat() > stale_before:
            continue  # long job (e.g. scan) still posting progress

        reclaims = (res.get("_reclaims", 0) if isinstance(res, dict) else 0)
        is_relist_create = j["action"] == "create" and j.get("scheduled_for")
        retry_safe = j["action"] in ("delete", "scan", "content_refresh") or is_relist_create

        if retry_safe and reclaims < MAX_RECLAIMS:
            db.table("jobs").update({
                "status": "pending",
                "claimed_at": None,
                "result": {"_reclaims": reclaims + 1, "_last_reclaim": now_dt.isoformat()},
            }).eq("id", j["id"]).eq("status", "claimed").execute()
        else:
            msg = (
                "Publishing was interrupted (Chrome likely closed mid-run) and couldn't be "
                "verified. Nothing was double-listed — publish this item again when Chrome is open."
                if j["action"] == "create" else
                f"This {j['action']} job was interrupted and couldn't finish after retries. Try it again."
            )
            db.table("jobs").update({
                "status": "error",
                "result": {"error": msg},
                "done_at": now_dt.isoformat(),
            }).eq("id", j["id"]).eq("status", "claimed").execute()
            if is_relist_create:
                db.table("listings").update({
                    "status": "error",
                    "error_message": "Relist recreate was interrupted before it finished — the old listing was removed but the new one wasn't confirmed. Refresh again to retry.",
                }).eq("item_id", j["item_id"]).eq("platform", j["platform"]).execute()


@router.get("/pending")
async def get_pending_jobs(platform: str = None, user_id: str = Depends(get_current_user)):
    db = get_db()
    now_dt = datetime.now(timezone.utc)
    # First, rescue anything stuck 'claimed' from an interrupted run.
    _recover_stale_claims(db, user_id, platform, now_dt)

    q = db.table("jobs").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    result = q.order("created_at").limit(20).execute()
    now = now_dt.isoformat()

    # Per-platform in-flight guard: publishing opens a real browser tab and the
    # create path doesn't wait for one to finish before the next is claimed, so a
    # bulk publish used to open many tabs at once — most of which failed and got
    # stuck. Only hand out a create for a platform that has no create currently
    # in flight (a fresh claim), so publishes run one-at-a-time per platform.
    busy_create_platforms = set()
    for c in (
        db.table("jobs").select("platform,claimed_at")
        .eq("user_id", user_id).eq("status", "claimed").eq("action", "create")
        .execute().data
    ):
        ct = _parse_ts(c.get("claimed_at"))
        if ct and ct >= now_dt - timedelta(minutes=STALE_CLAIM_MINUTES):
            busy_create_platforms.add(c["platform"])
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


@router.get("/active")
async def active_jobs(user_id: str = Depends(get_current_user)):
    """
    Everything the extension is either actively running or about to run, so the
    dashboard can warn the user to stay hands-off while it works.

    Two buckets:
      - "working": jobs the extension claimed RECENTLY — a Chrome tab is genuinely
        open and it's deleting/creating/scanning right now. Critically, we only
        count a claim as "working" if it happened within the last few minutes: a
        publish/delete finishes in seconds, so a job still "claimed" long after
        that isn't being worked — it's stuck (Chrome was closed mid-run, the tab
        failed, etc.). Without this window those abandoned claims made the
        "extension is working — don't touch" banner show forever even though
        nothing was happening.
      - "queued": pending jobs that are due now (no future scheduled_for). These
        will be picked up within one poll (~15s). Relist recreates sitting on a
        future timer are deliberately excluded — nothing is happening yet, so
        they shouldn't trip the "busy, don't touch" warning.
    """
    db = get_db()
    rows = (
        db.table("jobs")
        .select("id,action,platform,item_id,status,scheduled_for,claimed_at,result")
        .eq("user_id", user_id)
        .in_("status", ["pending", "claimed"])
        .order("created_at")
        .limit(50)
        .execute()
        .data
    )
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    # A genuinely active claim is very recent. Beyond this the run is stuck/abandoned.
    active_cutoff = now_dt - timedelta(minutes=3)

    def _fresh(ts) -> bool:
        if not ts:
            return False
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= active_cutoff

    def _is_working(j) -> bool:
        # Fresh claim = a publish/delete tab is open right now.
        if _fresh(j.get("claimed_at")):
            return True
        # Long-running jobs (mainly Vinted scans) can legitimately run past the
        # claim window, but they post live progress — treat a recent progress
        # ping as "still working" so the tab stays flagged, while a claim with no
        # recent activity at all is correctly treated as stuck and dropped.
        prog = (j.get("result") or {}).get("_progress")
        if isinstance(prog, dict) and _fresh(prog.get("at")):
            return True
        return False

    working, queued = [], []
    for j in rows:
        if j["status"] == "claimed":
            if _is_working(j):
                # Don't leak the raw progress/result blob to the client.
                j.pop("result", None)
                working.append(j)
        elif not j.get("scheduled_for") or j["scheduled_for"] <= now:
            j.pop("result", None)
            queued.append(j)
    return {"working": working, "queued": queued}


@router.post("/reschedule-now")
async def reschedule_now(body: dict, user_id: str = Depends(get_current_user)):
    """
    Bring a scheduled relist recreate forward so it fires on the next poll —
    clears the jittered delay for a specific item's still-pending "create" job.
    Only touches the caller's own pending job. Body: {item_id, platform}.
    """
    db = get_db()
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")
    rows = (
        db.table("jobs")
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "create")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No pending recreate job found for this item")
    now = datetime.now(timezone.utc).isoformat()
    db.table("jobs").update({"scheduled_for": now}).eq("id", rows[0]["id"]).execute()
    return {"ok": True, "job_id": rows[0]["id"], "scheduled_for": now}


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


@router.post("/{job_id}/progress")
async def report_job_progress(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """
    Lightweight live-progress channel for long-running jobs (mainly scans). The
    extension posts a small {stage, message, current, total} object at each phase;
    the dashboard polls /status/{job_id} and renders it so the user can see exactly
    what's happening and how far along it is. Stored in `result` under `_progress`
    (the final /complete overwrites `result`, so this never lingers).
    """
    db = get_db()
    db.table("jobs").update({
        "result": {"_progress": {**body, "at": datetime.now(timezone.utc).isoformat()}},
    }).eq("id", job_id).eq("user_id", user_id).execute()
    return {"ok": True}


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
    # (platform, listing id) → item_id, so a re-scan of an already-known listing
    # links back to the exact same item. Scoped by the user's item ids because
    # the listings table has no user_id column.
    item_ids = [it["id"] for it in items]
    listings_by_id = {}
    if item_ids:
        lrows = db.table("listings").select("item_id,platform,platform_listing_id").in_("item_id", item_ids).execute().data or []
        for l in lrows:
            pid = l.get("platform_listing_id")
            if pid is not None and l.get("item_id"):
                listings_by_id[(l.get("platform"), str(pid))] = l["item_id"]

    for row in scraped:
        platform_listing_id = row.get("platform_listing_id")
        title = row.get("title") or ""
        if not platform_listing_id:
            continue
        # Strongest signal: the exact same listing id already lives on an item.
        # Otherwise a UNIQUE exact title match. Fuzzy matching wrongly links items
        # differing only by size/colour/number (see imports._best_match), so a
        # wrong suggestion is worse than none.
        best_id = listings_by_id.get((job["platform"], str(platform_listing_id)))
        if not best_id:
            want = " ".join(title.lower().split())
            title_matches = [it["id"] for it in items if " ".join((it.get("title") or "").lower().split()) == want and want]
            best_id = title_matches[0] if len(title_matches) == 1 else None

        # If this scanned listing already belongs to an item, push the freshly
        # scraped rich data straight into that item's empty fields. This is what
        # makes a re-scan actually enrich already-imported items (description,
        # colour, …) without the user having to re-import anything.
        if best_id:
            try:
                _backfill_item_from_candidate(db, best_id, row)
            except Exception as e:
                logger.warning(f"Scan store: item backfill failed for {platform_listing_id}: {e}")

        # `photo_urls` (the full ordered list) is the source of truth; keep the
        # single `photo_url` populated too for the old thumbnail/UI path.
        photo_urls = row.get("photo_urls") or ([row["photo_url"]] if row.get("photo_url") else [])
        photo_url = row.get("photo_url") or (photo_urls[0] if photo_urls else None)

        base = {
            "user_id": job["user_id"],
            "platform": job["platform"],
            "platform_listing_id": platform_listing_id,
            "platform_listing_url": row.get("platform_listing_url"),
            "title": title,
            "price": row.get("price"),
            "photo_url": photo_url,
            "suggested_item_id": best_id,
            "platform_listed_at": row.get("platform_listed_at"),
            "status": "pending",
        }
        # Full snapshot columns — only present once the schema migration has run.
        # If they don't exist yet, PostgREST rejects the whole upsert, so retry
        # with just the base fields so scanning never breaks on an un-migrated DB.
        rich = {
            "photo_urls": photo_urls or None,
            "description": (row.get("description") or None),
            "brand": (row.get("brand") or None),
            "size": (row.get("size") or None),
            "condition": (row.get("condition") or None),
            "category": (row.get("category") or None),
            "gender": (row.get("gender") or None),
            "color": (row.get("color") or None),
            "material": (row.get("material") or None),
        }
        try:
            db.table("import_candidates").upsert(
                {**base, **rich}, on_conflict="user_id,platform,platform_listing_id"
            ).execute()
        except Exception as e:
            logger.warning(f"Scan store: rich upsert failed ({e}); falling back to base fields. Run the import_candidates ALTER migration.")
            db.table("import_candidates").upsert(
                base, on_conflict="user_id,platform,platform_listing_id"
            ).execute()


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
