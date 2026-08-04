"""
Billing service — background jobs and access control for subscription lifecycle.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from backend.database import get_db
from backend.config import settings

logger = logging.getLogger(__name__)

# Days of continued access after a trial ends or a payment fails. Long enough to
# fix a card or think it over, short enough that it isn't a free plan.
GRACE_DAYS = 2

# How long before the trial ends the reminder mail goes out.
REMINDER_DAYS_BEFORE = 2

# Statuses that mean "paid and current" — no grace maths needed.
_ALLOWED = {"active", "trialing"}

# The access check runs on every crosslist and on the extension's job polling
# (every few seconds per user), so the subscription row is cached briefly rather
# than re-read from Supabase each time. The cache is dropped the moment Stripe
# reports a change (see invalidate_access_cache).
_CACHE_TTL = 60
_cache: dict[str, tuple[float, dict]] = {}


async def expire_trials():
    """
    Runs hourly. Marks trialing subscriptions as 'trial_expired'
    when trial_ends_at has passed and no Stripe subscription is active.
    """
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    result = (
        db.table("subscriptions")
        .select("id, user_id, trial_ends_at")
        .eq("status", "trialing")
        .lt("trial_ends_at", now)
        .is_("stripe_subscription_id", "null")
        .execute()
    )
    if not result.data:
        return

    logger.info(f"Expiring {len(result.data)} trial(s)")
    for sub in result.data:
        db.table("subscriptions").update({
            "status": "trial_expired",
            "updated_at": now,
        }).eq("id", sub["id"]).execute()
        logger.info(f"Trial expired for user {sub['user_id']}")
        _cache.pop(sub["user_id"], None)


def trial_reminder_email(days_left: int, grace_days: int = GRACE_DAYS) -> tuple[str, str]:
    """Subject + body of the reminder. Kept apart from the sending so the wording
    can be changed (and previewed) without touching the scheduling."""
    day_word = "day" if days_left == 1 else "days"
    subject = f"Quick heads up: Your Omnivaleur trial ends in {days_left} {day_word}"
    grace_word = "day" if grace_days == 1 else "days"
    body = f"""Hi there,

Daniel here, founder of Omnivaleur.

I noticed your free trial is coming to an end in just {days_left} {day_word}. I wanted to
reach out personally to make sure everything has been running smoothly for you
so far.

Here is what happens next:

  * Next {days_left} {day_word}: Your trial remains fully active.

  * After that: You will get a {grace_days}-day grace period to make your decision.

  * Once those {grace_days} {grace_word} are up: Your account will be locked. Your active
    cross-listings will stay untouched on your platforms, but cross-listing
    functions and new outgoing listings will pause until you upgrade.

Upgrading takes less than a minute. Your items, connected channels, and history
will stay completely intact so you can keep going without missing a beat.

Activate Pro here: {settings.app_url} (€19.99/month, cancel anytime)

If you hit any snags, have questions, or feel something is missing for your
workflow, please email me directly at {settings.smtp_from_email or "info@revaleur.com"}
or simply reply to this message. I read every email and I am always happy to
help you get the most out of Omnivaleur.

Best regards,

Daniel
Founder, Omnivaleur
{settings.smtp_from_email or "info@revaleur.com"}
"""
    return subject, body


async def send_trial_reminders():
    """
    Runs daily. Mails every trialing user whose trial ends in REMINDER_DAYS_BEFORE
    days. The sent date is written back to the row, so a restart or a second run
    on the same day cannot mail anyone twice.
    """
    from backend.services.email import send_email

    db = get_db()
    now = datetime.now(timezone.utc)
    # Everyone whose trial still runs but ends within two days, and who has not
    # been mailed yet. Deliberately not a one-day slice: someone who signed up
    # 30 hours before the end would otherwise fall between two daily runs and
    # never hear from us. The sent-marker keeps it to one mail per person.
    window_start = now
    window_end = now + timedelta(days=REMINDER_DAYS_BEFORE)

    try:
        result = (
            db.table("subscriptions")
            .select("id, user_id, trial_ends_at, trial_reminder_sent_at")
            .eq("status", "trialing")
            .gte("trial_ends_at", window_start.isoformat())
            .lt("trial_ends_at", window_end.isoformat())
            .is_("trial_reminder_sent_at", "null")
            .execute()
        )
    except Exception:
        # The column has to be added to Supabase by hand. Without it there is no
        # way to remember who was already mailed, and mailing daily would be
        # worse than not mailing at all — so this stays off until the column exists.
        logger.exception(
            "Herinneringsmails overgeslagen: kolom trial_reminder_sent_at ontbreekt nog in Supabase"
        )
        return

    if not result.data:
        return

    logger.info(f"Trial reminder: {len(result.data)} gebruiker(s)")
    for sub in result.data:
        try:
            user = db.auth.admin.get_user_by_id(sub["user_id"])
            email = user.user.email if user and user.user else None
        except Exception:
            logger.exception(f"Geen e-mailadres gevonden voor {sub['user_id']}")
            continue
        if not email:
            continue

        ends = _parse_ts(sub.get("trial_ends_at"))
        days_left = max(1, int(-(-((ends - now).total_seconds()) // 86400))) if ends else REMINDER_DAYS_BEFORE
        subject, body = trial_reminder_email(days_left)
        if not send_email(subject=subject, body=body, to=email):
            # Not marked as sent, so tomorrow's run tries again.
            continue
        db.table("subscriptions").update(
            {"trial_reminder_sent_at": now.isoformat()}
        ).eq("id", sub["id"]).execute()
        logger.info(f"Trial reminder verstuurd naar {email}")


def invalidate_access_cache(user_id: str | None = None) -> None:
    """Drop the cached subscription so a payment takes effect immediately."""
    if user_id:
        _cache.pop(user_id, None)
    else:
        _cache.clear()


def is_owner_email(email: str | None) -> bool:
    if not email or not settings.owner_email:
        return False
    owners = {e.strip().lower() for e in settings.owner_email.split(",") if e.strip()}
    return email.lower() in owners


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_subscription(user_id: str) -> dict | None:
    cached = _cache.get(user_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    result = (
        get_db().table("subscriptions").select("*").eq("user_id", user_id).execute()
    )
    sub = result.data[0] if result.data else None
    if sub is not None:
        _cache[user_id] = (time.monotonic() + _CACHE_TTL, sub)
    return sub


def evaluate_access(sub: dict | None) -> dict:
    """
    Decides whether this subscription may still use the paid features.

    Returns {"allowed": bool, "reason": str, "grace_ends_at": iso|None,
             "grace_days_left": int|None}. A missing row is allowed: it means the
    account row was never written (RLS has bitten us before) and locking those
    people out would be worse than letting them through.
    """
    if sub is None:
        return {"allowed": True, "reason": "unknown", "grace_ends_at": None, "grace_days_left": None}

    status = (sub.get("status") or "trialing").lower()
    now = datetime.now(timezone.utc)

    if status == "active":
        return {"allowed": True, "reason": "active", "grace_ends_at": None, "grace_days_left": None}

    if status == "trialing":
        # The hourly job flips expired trials, but don't wait for it: a trial
        # whose clock has run out starts its grace period right away.
        ends = _parse_ts(sub.get("trial_ends_at"))
        if ends is None or ends > now:
            return {"allowed": True, "reason": "trialing", "grace_ends_at": None, "grace_days_left": None}
        grace_start = ends
        reason = "trial_expired"
    elif status == "trial_expired":
        grace_start = _parse_ts(sub.get("trial_ends_at")) or _parse_ts(sub.get("updated_at")) or now
        reason = "trial_expired"
    elif status in ("past_due", "unpaid", "incomplete"):
        # Payment failed: grace runs from the moment Stripe told us.
        grace_start = _parse_ts(sub.get("updated_at")) or now
        reason = "past_due"
    else:
        # canceled, incomplete_expired, anything unknown — no grace.
        return {"allowed": False, "reason": status, "grace_ends_at": None, "grace_days_left": 0}

    grace_ends = grace_start + timedelta(days=GRACE_DAYS)
    allowed = now < grace_ends
    days_left = max(0, -(-(grace_ends - now).total_seconds() // 86400)) if allowed else 0
    return {
        "allowed": allowed,
        "reason": reason,
        "grace_ends_at": grace_ends.isoformat(),
        "grace_days_left": int(days_left),
    }


async def check_access(user_id: str, email: str | None = None) -> dict:
    """Access verdict for this user. Owners always pass."""
    if is_owner_email(email):
        return {"allowed": True, "reason": "owner", "grace_ends_at": None, "grace_days_left": None}
    try:
        sub = await asyncio.to_thread(_fetch_subscription, user_id)
    except Exception:
        # A Supabase hiccup must not lock paying customers out of their own work.
        logger.exception(f"Kon abonnement niet ophalen voor {user_id}")
        return {"allowed": True, "reason": "lookup_failed", "grace_ends_at": None, "grace_days_left": None}
    return evaluate_access(sub)
