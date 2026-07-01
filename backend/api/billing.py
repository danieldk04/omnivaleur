"""
Stripe billing endpoints — subscription management for CrossList EU Pro.
"""
import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from backend.database import get_db
from backend.api.deps import get_current_user
from backend.config import settings

router = APIRouter(prefix="/api/billing", tags=["billing"])

stripe.api_key = settings.stripe_secret_key


def _get_or_create_subscription(user_id: str) -> dict:
    db = get_db()
    result = db.table("subscriptions").select("*").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]
    from datetime import datetime, timedelta, timezone
    trial_ends_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    try:
        new_sub = db.table("subscriptions").insert({
            "user_id": user_id,
            "status": "trialing",
            "plan": "pro",
            "trial_ends_at": trial_ends_at,
        }).execute()
        return new_sub.data[0]
    except Exception:
        return {"user_id": user_id, "status": "trialing", "plan": "pro", "trial_ends_at": trial_ends_at}


@router.get("/status")
async def billing_status(user_id: str = Depends(get_current_user)):
    try:
        sub = _get_or_create_subscription(user_id)
        return {
            "status": sub["status"],
            "plan": sub.get("plan", "pro"),
            "trial_ends_at": sub.get("trial_ends_at"),
            "current_period_end": sub.get("current_period_end"),
            "stripe_subscription_id": sub.get("stripe_subscription_id"),
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"billing_status error for {user_id}: {e}")
        # Return trialing so the user isn't blocked if DB lookup fails
        return {"status": "trialing", "plan": "pro", "trial_ends_at": None, "current_period_end": None}


@router.post("/checkout")
async def create_checkout(user_id: str = Depends(get_current_user)):
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe niet geconfigureerd")

    db = get_db()
    sub = _get_or_create_subscription(user_id)

    # Get or create Stripe customer
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        user_resp = get_db().auth.admin.get_user_by_id(user_id)
        email = user_resp.user.email if user_resp.user else None
        customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})
        customer_id = customer.id
        db.table("subscriptions").update({"stripe_customer_id": customer_id}).eq("user_id", user_id).execute()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card", "ideal", "bancontact"],
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.app_url}/app.html?billing=success",
        cancel_url=f"{settings.app_url}/app.html?billing=cancel",
        subscription_data={
            "trial_period_days": 7,
            "metadata": {"user_id": user_id},
        },
        metadata={"user_id": user_id},
    )
    return {"url": session.url}


@router.post("/portal")
async def customer_portal(user_id: str = Depends(get_current_user)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe niet geconfigureerd")

    sub = _get_or_create_subscription(user_id)
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Geen actief abonnement gevonden")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.app_url}/app.html",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret niet geconfigureerd")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Ongeldige webhook handtekening")

    db = get_db()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        stripe_sub_id = session.get("subscription")
        customer_id = session.get("customer")
        if user_id and stripe_sub_id:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            db.table("subscriptions").update({
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": stripe_sub_id,
                "status": stripe_sub["status"],
                "current_period_end": _ts(stripe_sub["current_period_end"]),
            }).eq("user_id", user_id).execute()

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        stripe_sub = event["data"]["object"]
        stripe_sub_id = stripe_sub["id"]
        result = db.table("subscriptions").select("user_id").eq("stripe_subscription_id", stripe_sub_id).execute()
        if result.data:
            db.table("subscriptions").update({
                "status": stripe_sub["status"],
                "current_period_end": _ts(stripe_sub["current_period_end"]),
            }).eq("stripe_subscription_id", stripe_sub_id).execute()

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        stripe_sub_id = invoice.get("subscription")
        if stripe_sub_id:
            db.table("subscriptions").update({"status": "past_due"}).eq("stripe_subscription_id", stripe_sub_id).execute()

    return {"ok": True}


def _ts(unix_ts: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()
