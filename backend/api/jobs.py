from fastapi import APIRouter, HTTPException, Depends, Request
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.api.imports import _backfill_item_from_candidate
from backend.services.crosslist import handle_item_sold
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

# How recently the extension must have checked in for us to call a computer
# "online". The extension's poll alarm is nominally 15s, but Chrome MV3 throttles
# background alarms to ~30-60s in practice, so a tight window flipped to a false
# "offline" right before each poll even though Chrome was open. 120s tolerates a
# throttled alarm plus a couple of missed check-ins; the trade-off is that
# closing Chrome now shows as offline within ~2 min instead of within one.
EXTENSION_ONLINE_WINDOW_SECONDS = 120


def _record_extension_heartbeat(db, user_id: str, user_agent: str | None = None) -> None:
    """
    Stamp that the extension just checked in, so a user on their phone can see
    whether a computer is online to run their queued jobs. Called from every
    extension-only endpoint (the platform poll AND claim/progress/complete/error),
    so any extension activity — not just the dispatch poll — keeps the computer
    marked online.

    Best-effort: it must never slow down or break dispatch — if the heartbeat
    table hasn't been created yet, or the write fails, we silently move on.
    The user_agent is only written when provided, so a check-in without it (e.g.
    from /complete) refreshes last_seen without wiping the UA the poll captured.
    """
    try:
        row = {
            "user_id": user_id,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        ua = (user_agent or "")[:300]
        if ua:
            row["user_agent"] = ua
        db.table("extension_heartbeat").upsert(row).execute()
    except Exception:
        pass


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

    NOT retry-safe → marked 'error' instead of retried:
      - ANY create job (initial crosslist OR relist recreate): if the first
        attempt did publish but the completion just wasn't recorded (e.g. the
        MV3 service worker was killed right after the tab confirmed the
        listing), re-running would post a DUPLICATE listing. A relist's create
        is no more idempotent than an initial create — its paired delete only
        guarantees the OLD listing is gone, not that THIS run didn't already
        publish the new one. Safer to surface an error and let the user retry
        manually.
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
        retry_safe = j["action"] in ("delete", "scan", "content_refresh")

        if retry_safe and reclaims < MAX_RECLAIMS:
            db.table("jobs").update({
                "status": "pending",
                "claimed_at": None,
                "result": {"_reclaims": reclaims + 1, "_last_reclaim": now_dt.isoformat()},
            }).eq("id", j["id"]).eq("status", "claimed").execute()
        else:
            msg = (
                "Publishing was interrupted (Chrome likely closed mid-run) and couldn't be "
                "verified either way — check whether it actually listed before publishing again "
                "to avoid a duplicate."
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
async def get_pending_jobs(request: Request, platform: str = None, user_id: str = Depends(get_current_user)):
    db = get_db()
    now_dt = datetime.now(timezone.utc)
    # A poll WITH a platform is a real extension dispatch poll (the dashboard
    # polls without one, just to count) — treat it as the extension's heartbeat
    # so the "computer online" indicator works without any extension change.
    if platform is not None:
        _record_extension_heartbeat(db, user_id, request.headers.get("user-agent"))
    # First, rescue anything stuck 'claimed' from an interrupted run.
    _recover_stale_claims(db, user_id, platform, now_dt)

    q = db.table("jobs").select("*").eq("user_id", user_id).eq("status", "pending")
    if platform:
        q = q.eq("platform", platform)
    result = q.order("created_at").limit(20).execute()
    now = now_dt.isoformat()

    # STRICT GLOBAL SERIALISATION (extension dispatch only).
    # Every job drives a REAL browser tab. The create path doesn't wait for one
    # publish to finish before the next is claimed, and the extension stores the
    # active job under a single per-platform key — so running two at once let a
    # second tab overwrite the first's data, publishing listings with each other's
    # photos, prices, titles and descriptions. To make that impossible we hand the
    # extension exactly ONE job at a time and refuse to dispatch anything while a
    # job is genuinely in flight (a fresh claim). The dashboard (which calls
    # /pending WITHOUT a platform, just to count the queue) is never throttled.
    is_extension_dispatch = platform is not None
    if is_extension_dispatch:
        for c in (
            db.table("jobs").select("claimed_at")
            .eq("user_id", user_id).eq("status", "claimed").execute().data
        ):
            ct = _parse_ts(c.get("claimed_at"))
            if ct and ct >= now_dt - timedelta(minutes=STALE_CLAIM_MINUTES):
                return []  # something is running right now — never open a 2nd tab

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
                # The delist failed, so the OLD listing is still live. Keep the
                # listing "active" (its true state) rather than "error" — the item
                # never left the platform, so it must not vanish from the dashboard.
                # The message lets the refresh view offer a one-click retry.
                db.table("listings").update({
                    "status": "active",
                    "error_message": "Relist aborted: the old listing couldn't be removed, so it's still live and no duplicate was created. You can retry the relist.",
                }).eq("item_id", j["item_id"]).eq("platform", j["platform"]).execute()
                continue
            # Delete not confirmed "done" yet (still pending/claimed, e.g. Chrome
            # was closed and just reopened) — hold the create job rather than
            # risk it firing before the old listing is actually gone. It stays
            # "pending" and will be re-checked on the next poll.
            if paired_delete and paired_delete[0]["status"] != "done":
                continue
        ready.append(j)

    # A relist's "create" job can sit queued for 45min-4h (the jittered
    # recreate delay) before it's actually dispatched. Its payload price was
    # snapshotted when the job was queued, so if the user edits the item's
    # price in the frontend in the meantime, the stale snapshot would win and
    # the relist would silently keep republishing the old price. Re-read the
    # item's current price right before handing the job to the extension so
    # the recreate always reflects what the user set, not what was true when
    # the delay started.
    for j in ready:
        if j["action"] == "create" and j.get("scheduled_for") and isinstance(j.get("payload"), dict):
            current = db.table("items").select("price").eq("id", j["item_id"]).execute().data
            if current and current[0].get("price") not in (None, ""):
                j["payload"]["price"] = current[0]["price"]

    # Extension: exactly one job at a time. Dashboard: the whole queue, to count.
    return ready[:1] if is_extension_dispatch else ready


@router.get("/extension-status")
async def extension_status(user_id: str = Depends(get_current_user)):
    """
    Is a computer with the extension online for this user? Powers the dashboard
    indicator so someone working from their phone knows whether their queued
    publishes/relists will run now or just wait. Reads the heartbeat stamped by
    the extension's own /pending polls.

    Returns online=None ("unknown") when the heartbeat table doesn't exist yet,
    so the frontend can simply hide the indicator instead of showing a wrong
    "offline". online=False means we've never seen it, or not recently.
    """
    db = get_db()
    try:
        row = (
            db.table("extension_heartbeat")
            .select("last_seen")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )
    except Exception:
        return {"online": None}  # table not migrated yet — hide the indicator

    if not row or not row[0].get("last_seen"):
        return {"online": False, "last_seen": None, "seconds_ago": None}

    last_seen = _parse_ts(row[0]["last_seen"])
    if not last_seen:
        return {"online": False, "last_seen": None, "seconds_ago": None}

    seconds_ago = int((datetime.now(timezone.utc) - last_seen).total_seconds())
    return {
        "online": seconds_ago <= EXTENSION_ONLINE_WINDOW_SECONDS,
        "last_seen": last_seen.isoformat(),
        "seconds_ago": max(0, seconds_ago),
    }


@router.get("/relist-status")
async def relist_status(user_id: str = Depends(get_current_user)):
    """
    In-progress relists for the dashboard's Refresh view: any scheduled recreate
    ("create" job with a future/pending scheduled_for) plus the state of its
    paired delete, so the UI can show "old listing removed, new one in ~X min".
    """
    db = get_db()
    # Include recently-DONE recreates too, not just in-flight ones: when the
    # extension finishes, the create job flips to "done" and would instantly drop
    # out of this list — so the dashboard card vanished mid-"Publishing now" with
    # no "it's live" confirmation, which read as "nothing happened / stuck". We
    # keep a completed recreate around for a short window so the UI can show an
    # explicit "✓ New listing is live" before clearing it.
    JUST_DONE_WINDOW = timedelta(seconds=90)
    now_dt = datetime.now(timezone.utc)
    create_jobs = (
        db.table("jobs")
        .select("item_id,platform,status,scheduled_for,created_at,done_at,result")
        .eq("user_id", user_id)
        .eq("action", "create")
        .in_("status", ["pending", "claimed", "done"])
        .execute()
        .data
    )
    out = []
    for j in create_jobs:
        if not j.get("scheduled_for"):
            continue  # only relist recreates carry a scheduled_for
        if j["status"] == "done":
            done_at = _parse_ts(j.get("done_at"))
            if not done_at or (now_dt - done_at) > JUST_DONE_WINDOW:
                continue  # long-finished — no longer "in progress"
        paired = (
            db.table("jobs")
            .select("status,result")
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
        entry = {
            "item_id": j["item_id"],
            "platform": j["platform"],
            "recreate_at": j["scheduled_for"],
            "recreate_status": j["status"],
            "delete_status": paired[0]["status"] if paired else None,
            # Surface WHY the delist failed: without this the dashboard could
            # only say "Failed", which hid a real bug for weeks.
            "delete_error": (
                ((paired[0].get("result") or {}).get("error") or None)
                if paired and paired[0]["status"] == "error" else None
            ),
        }
        # Hand the new listing's URL to the UI so the "live" confirmation can link
        # straight to it.
        if j["status"] == "done":
            entry["recreate_url"] = (j.get("result") or {}).get("platform_listing_url")
        out.append(entry)
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


@router.post("/relist-retry")
async def relist_retry(body: dict, user_id: str = Depends(get_current_user)):
    """
    Retry a relist that failed at the delist step. The old listing is still live
    on the platform (a failed delist removes nothing), so retrying is safe and is
    exactly what the user wants after "Relist failed".

    Ordering matters for correctness: we FIRST cancel any leftover delete/create
    jobs from the failed attempt (a still-pending recreate would otherwise fire
    later and duplicate the listing), reset the listing to a clean "active"
    state, and only THEN queue a brand-new relist via refresh_listing().
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()

    # Cancel any outstanding jobs from the failed relist so nothing fires twice.
    # Only pending/claimed/error jobs — never a job that already completed ("done").
    stale = (
        db.table("jobs")
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()
        .data
        or []
    )
    for j in stale:
        db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", j["id"]).execute()

    # Reset the listing to a clean active state before re-queuing. The failed
    # delist left it live, so "active" is correct; clearing error_message stops
    # the failed-relist banner from lingering after a successful retry.
    db.table("listings").update({
        "status": "active",
        "error_message": None,
    }).eq("item_id", item_id).eq("platform", platform).execute()

    from backend.services.relist import refresh_listing, RefreshError
    try:
        result = await refresh_listing(item_id, platform, user_id, "relist")
    except RefreshError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, **result}


@router.post("/relist-cancel")
async def relist_cancel(body: dict, user_id: str = Depends(get_current_user)):
    """
    Cancel a relist that's still mid-flight and put the listing back where it was.

    A relist is only safely reversible WHILE THE OLD LISTING IS STILL LIVE — i.e.
    the paired "delete" job hasn't completed yet. In that window we cancel both the
    (pending) delete and the (scheduled) recreate, roll back the cooldown/quota the
    refresh optimistically spent, and flip the listing straight back to "active".
    Nothing was ever removed from the platform, so this is a true no-op undo.

    Once the delete HAS completed, the old listing is already gone from the
    platform and there's nothing to restore — cancelling here would strand the
    item off-platform forever (exactly the "my listing vanished" bug). So we
    refuse and tell the UI to offer "Publish now" (reschedule-now) instead, which
    brings the item back live immediately.
    """
    item_id = body.get("item_id")
    platform = body.get("platform")
    if not item_id or not platform:
        raise HTTPException(status_code=400, detail="item_id and platform are required")

    db = get_db()

    # Most recent delete for this relist — its status tells us whether the old
    # listing is still live (safe to undo) or already gone (can't undo).
    del_rows = (
        db.table("jobs")
        .select("id,status,payload")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .eq("action", "delete")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    delete_job = del_rows[0] if del_rows else None

    if delete_job and delete_job["status"] == "done":
        # Old listing already removed — a cancel can't bring it back. Steer the
        # user to publish the new listing now instead of stranding the item.
        raise HTTPException(
            status_code=409,
            detail="The old listing has already been removed, so this relist can't "
                   "be cancelled without leaving your item offline. Use \"Publish now\" "
                   "to bring it back live immediately.",
        )

    # Old listing is still live (delete pending/claimed/errored, or never ran).
    # Cancel every outstanding job from this relist so nothing fires later.
    outstanding = (
        db.table("jobs")
        .select("id")
        .eq("user_id", user_id)
        .eq("item_id", item_id)
        .eq("platform", platform)
        .in_("action", ["delete", "create"])
        .in_("status", ["pending", "claimed", "error"])
        .execute()
        .data
        or []
    )
    for j in outstanding:
        db.table("jobs").update({
            "status": "cancelled",
            "done_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", j["id"]).execute()

    # Give back the cooldown + daily-quota slot the refresh spent up front, so a
    # cancelled relist doesn't count against the user (same rollback the failed-job
    # path uses).
    rollback = ((delete_job or {}).get("payload") or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)

    # The listing was flipped to "relisting" at enqueue time; nothing was ever
    # removed, so "active" is its true state again. Clear any stale error banner.
    db.table("listings").update({
        "status": "active",
        "error_message": None,
    }).eq("item_id", item_id).eq("platform", platform).execute()

    return {"ok": True, "cancelled": len(outstanding), "status": "active"}


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

    # The user explicitly cancelled this run — honour that and don't silently
    # revive the listing to "active" if a late completion trickles in afterwards.
    if job["status"] == "cancelled":
        return {"ok": True, "status": "cancelled"}

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
                    # This completion may arrive AFTER the job was marked failed
                    # (the user fixed the form by hand and published themselves —
                    # the extension's auto-detect then completes it late). Clear
                    # the stale error, otherwise the listing shows as live and
                    # broken at the same time.
                    "error_message": None,
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
        if job["platform"] == "vinted":
            await _reconcile_vinted_sales(db, job, body.get("listings", []))

    return {"ok": True}


async def _reconcile_vinted_sales(db, job, scraped: list[dict]):
    """
    Vinted has no webhook and (deliberately, after a past incident with a stale
    session) no server-side polling — so a Vinted sale is otherwise invisible
    until the user notices it themselves. A wardrobe scan IS an authoritative
    snapshot of everything still live on Vinted right now: if one of our
    "active"/"relisting" Vinted listings isn't in that snapshot anymore, it was
    sold, removed, or ended, and we treat it as sold so the item gets delisted
    everywhere else automatically.

    Only trust this when the scan actually returned data — an empty list here
    almost always means the scrape failed/was cut short, not that everything
    sold at once (see the page-1-failure/throw handling in bgScanVinted).
    """
    if not scraped:
        return
    scraped_ids = {str(r["platform_listing_id"]) for r in scraped if r.get("platform_listing_id")}

    items = db.table("items").select("id").eq("user_id", job["user_id"]).execute().data or []
    item_ids = [it["id"] for it in items]
    if not item_ids:
        return

    active = (
        db.table("listings")
        .select("item_id,platform_listing_id")
        .eq("platform", "vinted")
        .in_("item_id", item_ids)
        .in_("status", ["active", "relisting"])
        .execute()
        .data or []
    )
    for l in active:
        pid = l.get("platform_listing_id")
        if pid is not None and str(pid) not in scraped_ids:
            try:
                await handle_item_sold(l["item_id"], "vinted")
            except Exception as e:
                logger.warning(f"Vinted sale reconcile failed for item {l['item_id']}: {e}")


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
        # A failed delist means NOTHING was removed — the listing is still live on
        # the platform. Setting it to "error" hid it from the dashboard's active
        # views, so it looked deleted while it was actually still up (and, for a
        # relist, left the item in limbo). Keep it "active" (its true state) and
        # attach a visible message so the UI can offer a retry instead of hiding it.
        db.table("listings").update({
            "status": "active",
            "error_message": body.get("error", "Delist failed — the listing is still live. You can retry."),
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).execute()
    return {"ok": True}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, user_id: str = Depends(get_current_user)):
    """
    User-triggered abort of a still-running/queued job. Used when a publish run got
    stuck — e.g. the extension picked a wrong category and the user touched the tab,
    so the job never reaches complete/error and the "extension is working" banner
    hangs while the item is NOT actually published. Cancelling settles the job so the
    banner clears and the item correctly reads as not-listed.
    """
    db = get_db()
    job = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute().data
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Already finished — nothing to cancel; report where it landed.
    if job["status"] in ("done", "error", "cancelled"):
        return {"ok": True, "status": job["status"]}

    now = datetime.now(timezone.utc).isoformat()
    db.table("jobs").update({
        "status": "cancelled",
        "result": {"cancelled": "by user"},
        "done_at": now,
    }).eq("id", job_id).execute()

    # A content-refresh or relist-delete bumped the listing's cooldown/quota at enqueue
    # time; hand it back since the run was aborted.
    rollback = ((job.get("payload")) or {}).get("_refresh_rollback")
    if rollback:
        from backend.services.relist import rollback_refresh
        rollback_refresh(rollback, user_id)

    # For a create, drop the not-yet-confirmed "pending" listing so the item shows as
    # not-listed (its true state) — the publish didn't complete. An already-active
    # listing (a retry over a live one) is left untouched.
    if job["action"] == "create":
        db.table("listings").update({
            "status": "error",
            "error_message": "Publishing was cancelled — the item is not listed. Publish again, or mark it listed if it did go live.",
        }).eq("item_id", job["item_id"]).eq("platform", job["platform"]).eq("status", "pending").execute()
    return {"ok": True, "status": "cancelled"}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data
