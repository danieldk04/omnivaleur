"""
Billing service — background jobs for subscription lifecycle.
"""
import logging
from datetime import datetime, timezone
from backend.database import get_db

logger = logging.getLogger(__name__)


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
