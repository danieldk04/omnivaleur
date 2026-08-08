"""
Stripe billing endpoints — subscription management for Omnivaleur Pro.
"""
import logging
import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from backend.database import get_db
from backend.api.deps import get_current_user, get_current_user_full
from backend.config import settings
from backend.services.billing import (
    evaluate_access,
    invalidate_access_cache,
    is_owner_email as _is_owner_email,
)

logger = logging.getLogger(__name__)

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
        # Niet stil wegslikken: precies deze except verborg maandenlang dat RLS
        # alle inserts weigerde. De gebruiker zag een keurige proefperiode, maar
        # er stond niets in de database en expire_trials zag hem dus nooit.
        logger.exception(f"Kon geen abonnementsrij aanmaken voor {user_id}")
        return {"user_id": user_id, "status": "trialing", "plan": "pro", "trial_ends_at": trial_ends_at}


@router.get("/status")
async def billing_status(user=Depends(get_current_user_full)):
    user_id = user.id
    if _is_owner_email(user.email):
        return {
            "status": "active",
            "plan": "pro",
            "trial_ends_at": None,
            "current_period_end": None,
            "stripe_subscription_id": None,
            "access_allowed": True,
            "grace_ends_at": None,
            "grace_days_left": None,
            "is_owner": True,
        }
    try:
        sub = _get_or_create_subscription(user_id)
        access = evaluate_access(sub)
        return {
            "status": sub["status"],
            "plan": sub.get("plan", "pro"),
            "trial_ends_at": sub.get("trial_ends_at"),
            "current_period_end": sub.get("current_period_end"),
            "stripe_subscription_id": sub.get("stripe_subscription_id"),
            # The app shows a countdown instead of a flat "expired": access is
            # still on for a few days, and saying so is what creates the urgency.
            "access_allowed": access["allowed"],
            "grace_ends_at": access["grace_ends_at"],
            "grace_days_left": access["grace_days_left"],
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"billing_status error for {user_id}: {e}")
        # Return trialing so the user isn't blocked if DB lookup fails
        return {"status": "trialing", "plan": "pro", "trial_ends_at": None, "current_period_end": None,
                "access_allowed": True, "grace_ends_at": None, "grace_days_left": None}


@router.post("/checkout")
def create_checkout(user_id: str = Depends(get_current_user)):
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

    # De proefperiode loopt al vanaf de eerste login; hier nog eens 7 dagen
    # meegeven zou hem verdubbelen voor wie halverwege upgradet. Stripe wil een
    # trial_end van minimaal 48 uur vooruit — zit iemand daaronder, dan start
    # het abonnement meteen.
    subscription_data = {"metadata": {"user_id": user_id}}
    trial_end = _trial_end_ts(sub.get("trial_ends_at"))
    if trial_end:
        subscription_data["trial_end"] = trial_end

    # Geen expliciete payment_method_types: iDEAL en Bancontact zijn in
    # mode=subscription alleen toegestaan als sepa_debit in het Stripe-dashboard
    # aan staat, en zolang dat niet zo is weigerde Stripe ELKE checkout — niemand
    # kon dus betalen. Stripe kiest nu automatisch de methodes die op het account
    # actief zijn; zet je SEPA Direct Debit aan, dan verschijnt iDEAL er zelf bij.
    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.app_url}/app.html?billing=success",
            cancel_url=f"{settings.app_url}/app.html?billing=cancel",
            subscription_data=subscription_data,
            metadata={"user_id": user_id},
        )
    except stripe.error.StripeError as e:
        logger.exception(f"Stripe weigerde de checkout voor {user_id}")
        raise HTTPException(status_code=502, detail=f"Stripe: {e.user_message or str(e)}")
    return {"url": session.url}


@router.get("/invoices")
async def list_invoices(user_id: str = Depends(get_current_user)):
    if not settings.stripe_secret_key:
        return {"invoices": [], "payment_method": None}

    sub = _get_or_create_subscription(user_id)
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        return {"invoices": [], "payment_method": None}

    invoices = stripe.Invoice.list(customer=customer_id, limit=24)
    invoice_list = [{
        "id": inv["id"],
        "number": inv.get("number"),
        "status": inv["status"],
        "amount_paid": inv["amount_paid"] / 100,
        "currency": inv["currency"].upper(),
        "created": _ts(inv["created"]),
        "pdf_url": inv.get("invoice_pdf"),
        "hosted_url": inv.get("hosted_invoice_url"),
    } for inv in invoices.data]

    payment_method = None
    pm_id = None
    try:
        customer = stripe.Customer.retrieve(customer_id)
        pm_id = customer.get("invoice_settings", {}).get("default_payment_method")
    except Exception:
        pass
    if pm_id:
        try:
            pm = stripe.PaymentMethod.retrieve(pm_id)
            if pm["type"] == "card":
                payment_method = {"type": "card", "brand": pm["card"]["brand"], "last4": pm["card"]["last4"]}
            elif pm["type"] == "ideal":
                payment_method = {"type": "ideal", "bank": pm.get("ideal", {}).get("bank")}
            elif pm["type"] == "bancontact":
                payment_method = {"type": "bancontact"}
        except Exception:
            pass

    return {"invoices": invoice_list, "payment_method": payment_method}


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


@router.post("/admin/comp-account")
def comp_account(email: str, user=Depends(get_current_user_full)):
    """Grants a free-forever account to the given email. Owner-only."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Niet toegestaan")

    db = get_db()
    target = None
    page = 1
    while True:
        result = db.auth.admin.list_users(page=page, per_page=200)
        if not result:
            break
        target = next((u for u in result if u.email and u.email.lower() == email.lower()), None)
        if target or len(result) < 200:
            break
        page += 1

    if not target:
        raise HTTPException(status_code=404, detail="Geen account gevonden met dit e-mailadres — laat de gebruiker eerst registreren")

    _get_or_create_subscription(target.id)
    db.table("subscriptions").update({
        "status": "active",
        "plan": "pro",
    }).eq("user_id", target.id).execute()
    invalidate_access_cache(target.id)

    return {"ok": True, "user_id": target.id, "email": target.email}


@router.post("/admin/test-reminder-mail")
def test_reminder_mail(kind: str = "reminder", user=Depends(get_current_user_full)):
    """Stuurt de herinneringsmail naar de eigenaar zelf, zodat de tekst en de
    mailinstellingen te controleren zijn zonder op de dagelijkse taak te wachten.
    Raakt geen enkele klantrij aan."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Niet toegestaan")

    from backend.services.billing import CONTACT_EMAIL, final_warning_email, trial_reminder_email
    from backend.services.email import send_email_checked

    subject, body = final_warning_email(1) if kind == "final" else trial_reminder_email(2)
    try:
        send_email_checked(f"[TEST] {subject}", body, to=user.email, reply_to=CONTACT_EMAIL)
    except Exception as e:
        # De letterlijke melding van de mailserver: die zegt of het aan het
        # wachtwoord, de poort of de afzender ligt. "Het lukte niet" zei niets.
        logger.exception("Testmail mislukt")
        raise HTTPException(
            status_code=503,
            detail=(
                f"Versturen mislukt via {'Resend' if settings.resend_api_key else f'{settings.smtp_host}:{settings.smtp_port} als {settings.smtp_user}'}"
                f" — {type(e).__name__}: {e}"
            ),
        )
    return {"ok": True, "sent_to": user.email}


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
                "updated_at": _now(),
            }).eq("user_id", user_id).execute()
            invalidate_access_cache(user_id)

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        stripe_sub = event["data"]["object"]
        stripe_sub_id = stripe_sub["id"]
        result = db.table("subscriptions").select("user_id").eq("stripe_subscription_id", stripe_sub_id).execute()
        if result.data:
            db.table("subscriptions").update({
                "status": stripe_sub["status"],
                "current_period_end": _ts(stripe_sub["current_period_end"]),
                "updated_at": _now(),
            }).eq("stripe_subscription_id", stripe_sub_id).execute()
            invalidate_access_cache(result.data[0]["user_id"])

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        stripe_sub_id = invoice.get("subscription")
        if stripe_sub_id:
            # updated_at is the start of the grace period, so it must be stamped
            # here — otherwise a failed payment would inherit an old date and the
            # grace days would already be used up.
            db.table("subscriptions").update({
                "status": "past_due",
                "updated_at": _now(),
            }).eq("stripe_subscription_id", stripe_sub_id).execute()
            invalidate_access_cache()

    return {"ok": True}


def _trial_end_ts(trial_ends_at: str | None) -> int | None:
    """Resterende proeftijd als unix-timestamp, of None als die te kort is."""
    if not trial_ends_at:
        return None
    from datetime import datetime, timedelta, timezone
    try:
        ends = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    if ends < datetime.now(timezone.utc) + timedelta(hours=48):
        return None
    return int(ends.timestamp())


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _ts(unix_ts: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()
