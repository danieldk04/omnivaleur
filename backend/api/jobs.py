from fastapi import APIRouter, HTTPException, Depends, Request
from backend.database import get_db, fetch_all
from backend.api.deps import get_current_user, require_active_subscription
from backend.api.imports import _backfill_item_from_candidate
from backend.services.crosslist import handle_item_sold
from datetime import datetime, timezone, timedelta
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# A claim older than this with no progress means the run was interrupted (the
# MV3 service worker gets killed the moment Chrome closes or after ~30s idle, so
# a job can be claimed but never reach /complete or /error). Nothing ever
# re-surfaced those, so they hung "claimed" forever — blocking paired relists and
# tripping the "extension is working" banner. We recover them below.
STALE_CLAIM_MINUTES = 5
MAX_RECLAIMS = 2

# The optional import_candidates snapshot columns, dropped together if the
# migration hasn't run (see _store_scan_results).
RICH_KEYS = ("photo_urls", "description", "brand", "size", "condition",
             "category", "gender", "color", "material", "is_hidden")

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
def get_pending_jobs(request: Request, platform: str = None, user_id: str = Depends(require_active_subscription)):
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
def extension_status(user_id: str = Depends(get_current_user)):
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
def relist_status(user_id: str = Depends(get_current_user)):
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
def active_jobs(user_id: str = Depends(get_current_user)):
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

    # Settle anything stuck 'claimed' with no activity. The stale sweep used to run
    # ONLY from /pending, i.e. only while the extension was still polling — but the
    # cases that strand a job (content script hung on a Vinted colour panel, MV3
    # service worker killed so armJobWatchdog's setTimeout never fires, Chrome
    # closed) are exactly the cases where that poll may never come. The dashboard
    # polls THIS endpoint every 4s, so sweeping here makes a stuck job go terminal
    # on its own, with no user action. Anti-duplicate protection is unchanged: the
    # sweep marks a create 'error' and never re-dispatches it.
    if any(j["status"] == "claimed" and not _is_working(j) for j in rows):
        try:
            _recover_stale_claims(db, user_id, None, now_dt)
        except Exception as e:  # never let the banner endpoint fail on a sweep
            logger.warning(f"active_jobs: stale-claim sweep failed: {e}")

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
def reschedule_now(body: dict, user_id: str = Depends(require_active_subscription)):
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
async def relist_retry(body: dict, user_id: str = Depends(require_active_subscription)):
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
def relist_cancel(body: dict, user_id: str = Depends(get_current_user)):
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
def claim_job(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension claims jobs
    result = db.table("jobs").update({
        "status": "claimed",
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).eq("user_id", user_id).eq("status", "pending").execute()
    if not result.data:
        raise HTTPException(status_code=409, detail="Job already claimed or not found")
    return result.data[0]


@router.post("/{job_id}/progress")
def report_job_progress(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    """
    Lightweight live-progress channel for long-running jobs (mainly scans). The
    extension posts a small {stage, message, current, total} object at each phase;
    the dashboard polls /status/{job_id} and renders it so the user can see exactly
    what's happening and how far along it is. Stored in `result` under `_progress`
    (the final /complete overwrites `result`, so this never lingers).
    """
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # progress pings only come from the extension
    db.table("jobs").update({
        "result": {"_progress": {**body, "at": datetime.now(timezone.utc).isoformat()}},
    }).eq("id", job_id).eq("user_id", user_id).execute()
    return {"ok": True}


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension completes jobs
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
        # De extensie kan tijdens het verwijderen ontdekken dat de advertentie op
        # DIT platform verkocht is (Vinted: is_closed; MP/2dehands: een
        # "Verkocht"-label op de rij). Dan is verwijderen precies het verkeerde:
        # we boeken de verkoop, waardoor het item uit "live" verdwijnt en juist de
        # ándere platforms worden opgeruimd.
        if body.get("sold_on_platform"):
            from backend.services.crosslist import handle_item_sold
            logger.info("[sold] delete job %s reported a sale on %s — booking it instead of deleting",
                        job_id, job["platform"])
            try:
                await handle_item_sold(job["item_id"], job["platform"], body.get("sold_price"))
            except Exception as e:  # noqa: BLE001
                logger.warning("[sold] booking sale from delete job %s failed: %s", job_id, e)
            return {"ok": True, "status": "sold_on_platform"}

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
        # Saving a full wardrobe is the heaviest write this app does. The Supabase
        # client is synchronous, so running it inline froze the entire server for
        # as long as it took — which is exactly what left the extension stuck on
        # "Saving to your dashboard…" while the gateway timed the request out.
        import asyncio
        listings = body.get("listings", [])
        await asyncio.to_thread(_store_scan_results, db, job, listings)
        if job["platform"] == "vinted":
            await asyncio.to_thread(_sync_vinted_hidden, db, job, listings)
            await _reconcile_vinted_sales(db, job, listings, body.get("scan_meta") or {})

    return {"ok": True}


def _sync_vinted_hidden(db, job, scraped: list[dict]):
    """
    Mirror Vinted's `is_hidden` onto our listings.

    A hidden listing still exists and is still yours, but nobody can see or buy
    it — so it must not sit in the dashboard next to what's genuinely for sale
    (and it must not be counted as stale stock, which measures how long
    something has been ON SALE without selling).

    Unlike the sale reconcile this is safe on a PARTIAL snapshot: it only ever
    changes listings whose id we actually saw, so a truncated scan simply
    updates fewer rows instead of drawing a wrong conclusion from absence.
    Hidden is fully reversible — unhide on Vinted and the next scan flips it
    straight back to active.
    """
    if not scraped:
        return

    hidden_ids, visible_ids = set(), set()
    for r in scraped:
        pid = r.get("platform_listing_id")
        if pid is None or r.get("is_closed"):
            continue
        (hidden_ids if r.get("is_hidden") else visible_ids).add(str(pid))
    if not hidden_ids and not visible_ids:
        return

    item_ids = [it["id"] for it in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", job["user_id"]))]
    if not item_ids:
        return

    rows = (
        db.table("listings")
        .select("id,platform_listing_id,status")
        .eq("platform", "vinted")
        .in_("item_id", item_ids)
        .in_("status", ["active", "relisting", "hidden"])
        .execute()
        .data or []
    )

    to_hide, to_show = [], []
    for l in rows:
        pid = l.get("platform_listing_id")
        if pid is None:
            continue
        pid = str(pid)
        if pid in hidden_ids and l["status"] != "hidden":
            to_hide.append(l["id"])
        # Only un-hide on positive evidence that it's visible again.
        elif pid in visible_ids and l["status"] == "hidden":
            to_show.append(l["id"])

    for ids, new_status in ((to_hide, "hidden"), (to_show, "active")):
        if not ids:
            continue
        try:
            db.table("listings").update({"status": new_status}).in_("id", ids).execute()
        except Exception as e:
            logger.warning(f"Vinted hidden sync ({new_status}) failed: {e}")
    if to_hide or to_show:
        logger.info(
            "Vinted hidden sync for user %s: %d hidden, %d back to active",
            job["user_id"], len(to_hide), len(to_show),
        )


async def _reconcile_vinted_sales(db, job, scraped: list[dict], scan_meta: dict | None = None):
    """
    Vinted has no webhook and (deliberately, after a past incident with a stale
    session) no server-side polling — so a Vinted sale is otherwise invisible
    until the user notices it themselves. A COMPLETE wardrobe scan lets us spot
    one: a listing Vinted marks `is_closed` has sold or ended, and one that has
    vanished from the wardrobe entirely was deleted.

    Two hard safety rules, both learned the hard way:

    1. Only ever act on a COMPLETE snapshot. The scan used to read just the
       newest 96 listings (Vinted caps per_page at 96, and the pager mistook
       that short page for the last one). Every older listing therefore looked
       "missing" and was marked sold — and handle_item_sold then delisted it
       from every other platform. Absence is only meaningful if we truly saw
       everything, so an incomplete scan reconciles nothing.

    2. Absence is the weaker signal; `is_closed` is the real one. Sold listings
       stay in the wardrobe, so the closed flag is what actually tells us.
       Hidden listings are NOT sold — the seller just took them out of view —
       so they're deliberately left alone.
    """
    if not scraped:
        return

    meta = scan_meta or {}
    # No meta at all means an old extension build, whose snapshot we now know
    # was truncated. Refuse rather than repeat the damage.
    if not meta.get("complete"):
        logger.warning(
            "Vinted reconcile skipped for user %s — snapshot not complete (%s; %s of %s fetched). "
            "Update the extension so sold-detection can run again.",
            job["user_id"],
            meta.get("truncated_reason") or "no scan_meta (old extension build)",
            meta.get("fetched"), meta.get("total_entries"),
        )
        return

    # Everything Vinted still knows about, and which of those are closed.
    seen_ids: set[str] = set()
    closed_ids: set[str] = set()
    # Een advertentie zonder opgeslagen Vinted-nummer was tot nu toe onzichtbaar
    # voor deze controle: geen nummer = geen match = verkoop gemist, en het item
    # bleef bij "live" staan (en werd later alsnog "verwijderd" op Vinted).
    # Daarom twee vervangende sleutels, allebei alleen geldig als ze binnen de
    # garderobe naar precies één advertentie wijzen:
    #   1. de titel, 1-op-1 vergeleken na normalisatie (accenten, leestekens,
    #      hoofdletters en een eventuele "(1337)"-prefix doen niet mee);
    #   2. dat nummer tussen haakjes, als de verkoper dat gebruikt.
    # Dubbele titels of dubbele nummers worden bewust weggegooid: liever geen
    # match dan het verkeerde item als verkocht boeken.
    closed_id_by_sku: dict[str, str | None] = {}
    closed_id_by_title: dict[str, str | None] = {}

    def _sku_of(t: str) -> str:
        m = re.match(r"^\s*\(([^)]{1,24})\)", t or "")
        return m.group(1).strip().lower() if m else ""

    def _norm_title(t: str) -> str:
        t = unicodedata.normalize("NFKD", t or "")
        t = "".join(c for c in t if not unicodedata.combining(c)).lower()
        t = re.sub(r"^\s*\([^)]{1,24}\)\s*", "", t)     # SKU-prefix telt niet mee
        return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())

    def _register(index: dict, key: str, pid: str) -> None:
        if not key:
            return
        # None = dubbel gezien, dus onbruikbaar als sleutel.
        index[key] = pid if key not in index else (pid if index[key] == pid else None)

    for r in scraped:
        pid = r.get("platform_listing_id")
        if pid is None:
            continue
        pid = str(pid)
        seen_ids.add(pid)
        if r.get("is_closed"):
            closed_ids.add(pid)
            _register(closed_id_by_title, _norm_title(r.get("title")), pid)
            _register(closed_id_by_sku, _sku_of(r.get("title")), pid)

    items_rows = fetch_all(
        lambda: db.table("items").select("id,sku,title").eq("user_id", job["user_id"]))
    item_ids = [it["id"] for it in items_rows]
    items_by_id = {it["id"]: it for it in items_rows}
    own_title_counts: dict[str, int] = {}
    for it in items_rows:
        key = _norm_title(it.get("title"))
        if key:
            own_title_counts[key] = own_title_counts.get(key, 0) + 1
    if not item_ids:
        return

    active = (
        db.table("listings")
        .select("id,item_id,platform_listing_id")
        .eq("platform", "vinted")
        .in_("item_id", item_ids)
        # 'hidden' hoort erbij: een verborgen advertentie kan gewoon verkocht zijn
        # (Vinted zet hem dan op closed), en die verkoop werd anders nooit gezien.
        .in_("status", ["active", "relisting", "hidden"])
        .execute()
        .data or []
    )
    # Two very different signals, handled differently on purpose:
    #   is_closed  → Vinted's own "sold/ended" flag. On Vinted a listing doesn't
    #                expire on its own, so closed ≈ sold → book it as a sale.
    #   vanished   → gone from a COMPLETE wardrobe with no sold flag. Could be sold
    #                then removed, but could equally be manually deleted/expired.
    #                We do NOT fabricate a sale from absence (that would inflate
    #                revenue and cross-delist live listings). Instead we just take
    #                it off "Live" → 'delisted', so it lands in Archived for the
    #                user to confirm and mark sold themselves if it really sold.
    newly_sold, set_aside, matched_without_id = 0, 0, 0
    for l in active:
        pid = l.get("platform_listing_id")
        if pid is None:
            # Geen Vinted-nummer bekend: match op de SKU-prefix van de titel, en
            # anders op de exacte titel. Alleen een POSITIEF "gesloten" kaartje
            # telt — afwezigheid blijft betekenisloos, precies zoals hieronder.
            item = items_by_id.get(l["item_id"]) or {}
            title = _norm_title(item.get("title"))
            # De titel is de gewone sleutel; het nummer tussen haakjes (of het
            # SKU-veld) is een extra, voor wie dat gebruikt. Een titel die bij
            # meerdere eigen items hoort is geen sleutel — dan liever niets doen.
            hit = None
            if title and own_title_counts.get(title) == 1:
                hit = closed_id_by_title.get(title)
            if not hit:
                keys = [k for k in (str(item.get("sku") or "").strip().lower(),
                                    _sku_of(item.get("title"))) if k]
                hit = next((closed_id_by_sku[k] for k in keys if closed_id_by_sku.get(k)), None)
            if not hit:
                continue
            matched_without_id += 1
            # Meteen het nummer vastleggen, zodat de volgende ronde gewoon op id matcht.
            try:
                db.table("listings").update({"platform_listing_id": hit}).eq("id", l["id"]).execute()
            except Exception as e:  # noqa: BLE001
                logger.warning("Vinted reconcile: could not backfill listing id for %s: %s", l["item_id"], e)
            try:
                await handle_item_sold(l["item_id"], "vinted")
                newly_sold += 1
            except Exception as e:
                logger.warning(f"Vinted sale reconcile failed for item {l['item_id']}: {e}")
            continue
        pid = str(pid)
        if pid in closed_ids:
            try:
                await handle_item_sold(l["item_id"], "vinted")
                newly_sold += 1
            except Exception as e:
                logger.warning(f"Vinted sale reconcile failed for item {l['item_id']}: {e}")
        elif pid not in seen_ids:
            try:
                db.table("listings").update({"status": "delisted"}) \
                    .eq("item_id", l["item_id"]).eq("platform", "vinted").execute()
                set_aside += 1
            except Exception as e:
                logger.warning(f"Vinted reconcile: could not archive vanished listing {l['item_id']}: {e}")
    logger.info(
        "[sold] Vinted reconcile for user %s: %d marked sold (is_closed, of which %d matched by SKU/title), "
        "%d vanished → archived for review",
        job["user_id"], newly_sold, matched_without_id, set_aside,
    )


def _store_scan_results(db, job, scraped: list[dict]):
    """
    Persist scraped "my listings" cards as import_candidates for manual review.
    Never touches the items/listings tables directly — a human links or
    imports each candidate explicitly via /api/imports.
    """
    if not scraped:
        return
    from backend.api.imports import BACKFILL_FIELDS, _backfill_patch

    # Read the items ONCE, with every field the backfill needs. This used to be a
    # select per candidate inside the loop below, so a 500-listing wardrobe meant
    # ~1000 round-trips and "Saving to your dashboard…" sat there for minutes.
    items = fetch_all(lambda: db.table("items").select(BACKFILL_FIELDS + ",title").eq("user_id", job["user_id"]))
    items_by_id = {it["id"]: it for it in items}
    # (platform, listing id) → item_id, so a re-scan of an already-known listing
    # links back to the exact same item. Scoped by the user's item ids because
    # the listings table has no user_id column.
    item_ids = [it["id"] for it in items]
    listings_by_id = {}
    # (item_id, platform) → de bestaande listing-rij, zodat we hieronder kunnen
    # zien of het dashboard al wéét dat dit item op dit platform staat.
    listing_by_item = {}
    if item_ids:
        lrows = fetch_all(lambda: db.table("listings")
                          .select("id,item_id,platform,status,platform_listing_id")
                          .in_("item_id", item_ids))
        for l in lrows:
            pid = l.get("platform_listing_id")
            if pid is not None and l.get("item_id"):
                listings_by_id[(l.get("platform"), str(pid))] = l["item_id"]
            if l.get("item_id"):
                listing_by_item[(l["item_id"], l.get("platform"))] = l

    # De titel die de extensie daadwerkelijk in het formulier zette (uit de
    # publicatie-opdracht). Die staat op het platform, terwijl de itemtitel in
    # het dashboard anders kan zijn (vertaald of ingekort) — daarom herkende hij
    # zelf afgemaakte advertenties niet.
    job_titles = {}
    try:
        jrows = fetch_all(lambda: db.table("jobs")
                          .select("item_id,payload")
                          .eq("user_id", job["user_id"])
                          .eq("platform", job["platform"])
                          .eq("action", "create"))
        for j in jrows:
            t = ((j.get("payload") or {}).get("title") or "").strip().lower()
            t = " ".join(t.split())
            if t and j.get("item_id"):
                # Bij twijfel (twee items met dezelfde formuliertitel) liever geen
                # koppeling dan de verkeerde.
                job_titles[t] = None if t in job_titles and job_titles[t] != j["item_id"] else j["item_id"]
    except Exception as e:
        logger.warning(f"Scan store: could not read create-job titles: {e}")

    # What we already decided about each candidate. The upsert below refreshes the
    # scraped snapshot, but it must NOT undo a decision: it used to write
    # status='pending' unconditionally, so a re-scan resurrected every listing you
    # had already imported, linked or ignored straight back into the review list.
    prior_status = {}
    prev = (
        db.table("import_candidates")
        .select("platform_listing_id,status")
        .eq("user_id", job["user_id"])
        .eq("platform", job["platform"])
        .execute()
        .data or []
    )
    for c in prev:
        pid = c.get("platform_listing_id")
        if pid is not None:
            prior_status[str(pid)] = c.get("status") or "pending"

    rows = []          # candidate rows, upserted in bulk below
    backfills = {}     # item_id -> merged patch, applied in bulk below
    live_links = {}    # item_id -> listing data we saw live on this platform

    for row in scraped:
        platform_listing_id = row.get("platform_listing_id")
        title = row.get("title") or ""
        if not platform_listing_id:
            continue
        # Sold/ended and draft listings ride along in the scan payload purely so
        # the sale reconcile can see them — nobody wants to import them. Without
        # this a full wardrobe scan would dump every listing ever sold into the
        # import queue for manual review.
        if row.get("is_closed") or row.get("is_draft"):
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
        if not best_id:
            # Laatste, even harde sleutel: exact de titel die wij zelf in het
            # formulier hebben gezet voor dit platform.
            best_id = job_titles.get(" ".join(title.lower().split())) or None
        if not best_id:
            # Twee even harde, maar veel robuustere sleutels. Zonder deze bleef
            # een advertentie die de gebruiker zélf plaatste (of die op het
            # platform in het Nederlands staat terwijl het dashboard Engels is)
            # ongekoppeld — en dan kan hij bij verkoop nergens automatisch
            # weggehaald worden. Dubbel voorkomende sleutels tellen niet mee, dus
            # liever geen koppeling dan de verkeerde.
            best_id = _sku_index.get(_scan_sku(title)) or _norm_title_index.get(_scan_norm_title(title))

        # Dit item staat aantoonbaar live op dit platform (we hebben zijn kaartje
        # net gezien). Zet dat vast in `listings`, zodat een handmatig geplaatste
        # advertentie in het dashboard ook als "online" telt — voorheen bleef die
        # onbekend en bood de app hem gewoon opnieuw aan om te publiceren.
        if best_id:
            live_links[best_id] = {
                "platform_listing_id": str(platform_listing_id),
                "platform_listing_url": row.get("platform_listing_url"),
                "platform_listed_at": row.get("platform_listed_at"),
            }

        # If this scanned listing already belongs to an item, push the freshly
        # scraped rich data straight into that item's empty fields. This is what
        # makes a re-scan actually enrich already-imported items (description,
        # colour, …) without the user having to re-import anything.
        if best_id:
            try:
                current = items_by_id.get(best_id)
                if current:
                    patch = _backfill_patch(current, row)
                    if patch:
                        # Collect now, write later in one pass — and keep the local
                        # copy in step so a second listing for the same item sees
                        # the fields we're about to fill.
                        backfills[best_id] = {**backfills.get(best_id, {}), **patch}
                        current.update(patch)
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
            # Keep whatever we already decided; only genuinely new rows start pending.
            "status": prior_status.get(str(platform_listing_id), "pending"),
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
        # is_hidden is the newest optional column, so it gets its own tier: if only
        # THAT one is missing we still want the description/brand/photos to land,
        # instead of dropping every rich field over one absent column.
        hidden = {"is_hidden": bool(row.get("is_hidden"))}
        rows.append({**base, **rich, **hidden})

    # ── Write everything in as few round-trips as possible ────────────────
    # PostgREST upserts a whole list in one request, so a 500-listing wardrobe
    # costs a handful of calls instead of 500. Chunked so no single request grows
    # large enough for the gateway to time out on.
    CHUNK = 100
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        # Optional columns may not exist yet on an un-migrated database. Drop the
        # newest tier first, then the whole rich snapshot — never the base fields.
        for attempt in range(3):
            drop = () if attempt == 0 else (("is_hidden",) if attempt == 1 else RICH_KEYS)
            payload = [{k: v for k, v in r.items() if k not in drop} for r in chunk]
            try:
                db.table("import_candidates").upsert(
                    payload, on_conflict="user_id,platform,platform_listing_id"
                ).execute()
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Scan store: is_hidden column missing ({e}); run the import_candidates ALTER migration.")
                elif attempt == 1:
                    logger.warning(f"Scan store: rich upsert failed ({e}); falling back to base fields. Run the import_candidates ALTER migration.")
                else:
                    logger.error(f"Scan store: base upsert failed for {len(chunk)} rows: {e}")

    # Item backfills: one update per item that actually gained something, rather
    # than a select+update per scanned listing. On a re-scan most items are
    # already complete, so this is usually a handful of writes.
    for item_id, patch in backfills.items():
        try:
            db.table("items").update(patch).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"Scan store: item backfill failed for {item_id}: {e}")

    # Live-koppelingen: markeer items die we zojuist op het platform zagen als
    # daadwerkelijk online. Een 'sold' rij blijft met rust — die is bewust zo
    # gezet en mag niet terug naar actief.
    platform = job["platform"]
    for item_id, link in live_links.items():
        existing = listing_by_item.get((item_id, platform))
        try:
            if existing:
                if existing.get("status") == "sold":
                    continue
                if (existing.get("status") == "active"
                        and str(existing.get("platform_listing_id") or "") == link["platform_listing_id"]):
                    continue
                db.table("listings").update({
                    "status": "active",
                    "error_message": None,
                    "platform_listing_id": link["platform_listing_id"],
                    "platform_listing_url": link["platform_listing_url"],
                }).eq("id", existing["id"]).execute()
            else:
                db.table("listings").insert({
                    "item_id": item_id,
                    "platform": platform,
                    "status": "active",
                    "platform_listing_id": link["platform_listing_id"],
                    "platform_listing_url": link["platform_listing_url"],
                }).execute()
        except Exception as e:
            logger.warning(f"Scan store: live link failed for {item_id}/{platform}: {e}")

        # We hebben deze advertentie zojuist LIVE gezien. Staat er dan nog een
        # plaatsingsopdracht te wachten (bijvoorbeeld een republicatie die bleef
        # hangen en die de verkoper daarom zelf heeft afgemaakt), dan moet die
        # weg: anders komt er straks alsnog een tweede advertentie bij, en blijft
        # het kaartje "Publishing now…" eeuwig staan.
        try:
            done = (
                db.table("jobs").update({
                    "status": "done",
                    "done_at": datetime.now(timezone.utc).isoformat(),
                    "result": {"note": "already live on the platform (seen by scan)",
                               "platform_listing_id": link["platform_listing_id"],
                               "platform_listing_url": link["platform_listing_url"]},
                })
                .eq("user_id", job["user_id"]).eq("item_id", item_id).eq("platform", platform)
                .eq("action", "create").in_("status", ["pending", "claimed"])
                .execute().data
            )
            if done:
                logger.info("Scan store: closed %d queued publish job(s) for %s/%s — it's already live",
                            len(done), item_id, platform)
        except Exception as e:
            logger.warning(f"Scan store: could not close queued create for {item_id}/{platform}: {e}")

    logger.info(
        "Scan store for user %s: %d candidates upserted, %d items enriched",
        job["user_id"], len(rows), len(backfills),
    )


def _queue_scan(db, user_id: str, platform: str):
    """Zet een scan-opdracht klaar (tenzij er al één wacht). Nooit fataal."""
    from backend.api.imports import SCANNABLE_PLATFORMS
    if platform not in SCANNABLE_PLATFORMS:
        return
    try:
        existing = (db.table("jobs").select("id")
                    .eq("user_id", user_id).eq("platform", platform).eq("action", "scan")
                    .in_("status", ["pending", "claimed"]).limit(1).execute().data)
        if existing:
            return
        db.table("jobs").insert({
            "user_id": user_id, "item_id": None, "platform": platform,
            "action": "scan", "status": "pending", "payload": {},
        }).execute()
    except Exception as e:
        logger.warning(f"Could not queue follow-up scan for {platform}: {e}")


@router.post("/{job_id}/error")
def fail_job(job_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    _record_extension_heartbeat(db, user_id)  # only the extension reports job errors
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
        # Een mislukte publicatie betekent vaak dat de gebruiker het formulier
        # zelf heeft afgemaakt. Plan meteen een scan in, zodat de app binnen
        # enkele minuten zelf ziet dat de advertentie tóch online staat in
        # plaats van te wachten op de volgende ronde.
        _queue_scan(db, user_id, job["platform"])
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
def cancel_job(job_id: str, user_id: str = Depends(get_current_user)):
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
        # Vaak maakt de gebruiker de advertentie na een afbreking zelf af. Een
        # scan erachteraan zorgt dat het dashboard dat vanzelf oppikt.
        _queue_scan(db, user_id, job["platform"])
    return {"ok": True, "status": "cancelled"}


@router.get("/status/{job_id}")
def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data
