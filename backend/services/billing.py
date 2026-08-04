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
GRACE_DAYS = 3

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
