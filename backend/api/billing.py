"""
Stripe billing endpoints — subscription management for Omnivaleur Pro.
"""
import asyncio
import logging
import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from backend.database import get_admin_db, get_db, execute_with_retry
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
# Zonder eigen limiet wacht stripe-python tot 80 seconden per poging en probeert
# het daarna nóg eens. Dat is langer dan de proxy vóór de app accepteert, dus een
# trage of geblokkeerde verbinding naar Stripe kwam bij de gebruiker aan als een
# kale 502-pagina in plaats van een uitleg. Nu geven we binnen 20 seconden op.
stripe.max_network_retries = 0
try:
    try:
        from stripe import http_client as _stripe_http  # stripe 10.x
    except ImportError:
        from stripe import _http_client as _stripe_http  # stripe 12.x+
    stripe.default_http_client = _stripe_http.new_default_http_client(timeout=20)
except Exception:  # pragma: no cover - afhankelijk van de stripe-versie
    logger.warning("Kon geen timeout op de Stripe-client zetten")


# De excuus-actie na de betaalstoring. De code hoeft niemand te typen: de app
# past hem zelf toe zolang hij in Stripe actief en niet verlopen is. Loopt hij af,
# dan verdwijnt de korting van de betaalpagina en uit de app zonder dat er iets
# aangepast hoeft te worden.
PROMO_CODE = "OMNIVALEUR25"

# De actie verandert vrijwel nooit, maar de statuscontrole draait bij elke
# schermverversing. Zonder deze kortstondige onthouding zou elke gebruiker elke
# keer een aanroep naar Stripe uitlokken, en dat is precies het soort wachten dat
# de hele app eerder liet vastlopen.
_PROMO_CACHE_TTL = 300
_promo_cache: tuple[float, dict | None] | None = None


def find_active_promo() -> dict | None:
    """De actieve actiecode uit Stripe, of None. Nooit hard falen: een storing bij
    het ophalen van een korting mag het afrekenen niet blokkeren."""
    global _promo_cache

    if not settings.stripe_secret_key:
        return None
    import time as _time

    if _promo_cache and _promo_cache[0] > _time.monotonic():
        return _promo_cache[1]
    try:
        codes = stripe.PromotionCode.list(code=PROMO_CODE, active=True, limit=1)
    except Exception:
        logger.exception("Kon de actiecode niet ophalen")
        return None
    if not codes.data:
        # Ook "er is geen actie" is het onthouden waard: anders vraagt de app het
        # na de actie bij elke verversing opnieuw aan Stripe.
        _promo_cache = (_time.monotonic() + _PROMO_CACHE_TTL, None)
        return None
    # Twee vormen mogelijk: oudere API-versies zetten de coupon uitgeklapt onder
    # "coupon", nieuwere alleen het nummer onder "promotion". Beide moeten werken,
    # want Stripe verhoogt die versie zonder dat wij iets aanpassen.
    import json

    promo = json.loads(str(codes.data[0]))
    coupon = promo.get("coupon")
    if not isinstance(coupon, dict):
        coupon_id = (promo.get("promotion") or {}).get("coupon") or coupon
        try:
            coupon = json.loads(str(stripe.Coupon.retrieve(coupon_id))) if coupon_id else {}
        except Exception:
            logger.exception("Kon de coupon achter de actiecode niet ophalen")
            return None
    result = {
        "id": promo["id"],
        "code": promo["code"],
        "percent_off": coupon.get("percent_off"),
        "expires_at": promo.get("expires_at"),
    }
    _promo_cache = (_time.monotonic() + _PROMO_CACHE_TTL, result)
    return result


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
            # De actiekorting hoort in de app te staan, niet in een mail: een mail
            # met een kortingscode erin belandt bij Gmail in spam. Via een aparte
            # draad, want de Stripe-client wacht blokkerend op antwoord en zou
            # anders de hele app laten stilstaan zolang die aanroep loopt.
            "promo": await asyncio.to_thread(find_active_promo),
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"billing_status error for {user_id}: {e}")
        # Return trialing so the user isn't blocked if DB lookup fails
        return {"status": "trialing", "plan": "pro", "trial_ends_at": None, "current_period_end": None,
                "access_allowed": True, "grace_ends_at": None, "grace_days_left": None}


@router.post("/checkout")
def create_checkout(user=Depends(get_current_user_full)):
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe niet geconfigureerd")

    user_id = user.id
    db = get_db()
    sub = _get_or_create_subscription(user_id)

    # Get or create Stripe customer.
    # Het e-mailadres komt uit het al gevalideerde token. De vorige versie vroeg
    # het op via auth.admin.get_user_by_id, en die admin-route weigert ("User not
    # allowed") zodra de server met een gewone sleutel praat in plaats van de
    # service-role sleutel. Gevolg: iedere eerste betaalpoging klapte er hier op
    # stuk, nog voordat Stripe in zicht kwam.
    customer_id = sub.get("stripe_customer_id")

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
        if not customer_id:
            email = getattr(user, "email", None)
            customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})
            customer_id = customer.id
            try:
                db.table("subscriptions").update({"stripe_customer_id": customer_id}).eq("user_id", user_id).execute()
            except Exception:
                # Opslaan mislukt (bv. RLS) mag het afrekenen niet tegenhouden; de
                # webhook koppelt de klant later alsnog aan de gebruiker.
                logger.exception(f"Kon stripe_customer_id niet opslaan voor {user_id}")

        session_args = dict(
            customer=customer_id,
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.app_url}/app.html?billing=success",
            cancel_url=f"{settings.app_url}/app.html?billing=cancel",
            subscription_data=subscription_data,
            metadata={"user_id": user_id},
        )
        promo = find_active_promo()
        if promo:
            # Korting meteen toepassen in plaats van hem laten typen: elke letter
            # die iemand moet overtypen is een reden om af te haken. Stripe staat
            # een vast kortingsveld en een invulvakje niet samen toe, dus de keuze
            # valt op de variant zonder handwerk.
            session_args["discounts"] = [{"promotion_code": promo["id"]}]
        else:
            session_args["allow_promotion_codes"] = True
        try:
            session = stripe.checkout.Session.create(**session_args)
        except Exception:
            if "discounts" not in session_args:
                raise
            # De korting mag nooit de reden zijn dat iemand niet kan betalen. Raakt
            # de actie onderweg op of verloopt hij tussen twee kliks, dan gaat het
            # afrekenen door zonder korting in plaats van te weigeren.
            logger.exception("Afrekenen met korting mislukt, opnieuw zonder korting")
            session_args.pop("discounts")
            session_args["allow_promotion_codes"] = True
            session = stripe.checkout.Session.create(**session_args)
    except Exception as e:
        # Elke fout, niet alleen die van Stripe: een onverwachte crash gaf een
        # kale 500 waar de app niets zinnigs over kon zeggen.
        logger.exception(f"Checkout mislukt voor {user_id}")
        detail = getattr(e, "user_message", None) or f"{type(e).__name__}: {e}"
        # Bewust geen 502: Cloudflare vervangt de inhoud van een 502 door zijn
        # eigen storingspagina, waardoor de gebruiker de uitleg nooit zag.
        raise HTTPException(status_code=400, detail=detail)
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
        result = get_admin_db().auth.admin.list_users(page=page, per_page=200)
        if not result:
            break
        target = next((u for u in result if u.email and u.email.lower() == email.lower()), None)
        if target or len(result) < 200:
            break
        page += 1

    if not target:
        raise HTTPException(status_code=404, detail="Geen account gevonden met dit e-mailadres — laat de gebruiker eerst registreren")

    _get_or_create_subscription(target.id)
    # Bewust 'trialing' met een datum ver vooruit in plaats van 'active': status
    # 'active' zonder Stripe-abonnement wordt sinds de dichtgezette gratis-toegang
    # juist geweigerd, en dan gaf deze knop het tegenovergestelde van wat hij belooft.
    db.table("subscriptions").update({
        "status": "trialing",
        "plan": "pro",
        "trial_ends_at": "2099-01-01T00:00:00+00:00",
    }).eq("user_id", target.id).execute()
    invalidate_access_cache(target.id)

    return {"ok": True, "user_id": target.id, "email": target.email}


@router.post("/admin/announcement")
def send_announcement(dry_run: bool = True, emails: str = "", user=Depends(get_current_user_full)):
    """De eenmalige 'afrekenen werkt weer'-mail. Standaard een proefronde die
    alleen vertelt wie hem zou krijgen; pas met dry_run=false gaat hij echt weg.
    Eigenaar-only.

    `emails` is een handmatige lijst adressen. Nodig omdat de server met de
    publieke Supabase-sleutel praat en de gebruikerslijst dus niet mag opvragen
    ("User not allowed"). Blijft het veld leeg, dan probeert hij het alsnog zelf."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Niet toegestaan")

    from backend.services.announcement import BODY, SUBJECT, collect_recipients, parse_email_list
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email_checked

    if emails.strip():
        recipients = parse_email_list(emails)
        if not recipients:
            raise HTTPException(status_code=400, detail="Geen geldig e-mailadres in de lijst gevonden")
    else:
        try:
            recipients = collect_recipients()
        except Exception as e:
            logger.exception("Kon de ontvangerslijst niet ophalen")
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Ontvangers ophalen mislukt: {type(e).__name__}: {e}. "
                    "Plak de adressen zelf, of zet de service-role sleutel van Supabase op Railway."
                ),
            )

    if dry_run:
        return {"dry_run": True, "count": len(recipients), "recipients": recipients}

    sent, failed = [], []
    for email in recipients:
        try:
            send_email_checked(SUBJECT, BODY, to=email, reply_to=CONTACT_EMAIL)
            sent.append(email)
        except Exception as e:
            # Eén geweigerd adres mag de rest van de verzending niet stoppen.
            logger.exception(f"Aankondiging mislukt voor {email}")
            failed.append({"email": email, "error": f"{type(e).__name__}: {e}"})
    logger.info(f"Aankondiging verstuurd naar {len(sent)}, mislukt {len(failed)}")
    return {"dry_run": False, "sent": len(sent), "failed": failed, "recipients": sent}


@router.post("/admin/test-reminder-mail")
def test_reminder_mail(kind: str = "reminder", user=Depends(get_current_user_full)):
    """Stuurt de herinneringsmail naar de eigenaar zelf, zodat de tekst en de
    mailinstellingen te controleren zijn zonder op de dagelijkse taak te wachten.
    Raakt geen enkele klantrij aan."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Niet toegestaan")

    from backend.services.billing import (
        CONTACT_EMAIL, final_warning_email, locked_email, trial_reminder_email,
    )
    from backend.services.email import send_email_checked

    if kind == "final":
        subject, body = final_warning_email(1)
    elif kind == "locked":
        subject, body = locked_email()
    else:
        subject, body = trial_reminder_email(2)
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


@router.post("/admin/reminder-dryrun")
def reminder_dryrun(user=Depends(get_current_user_full)):
    """Wie zou er nu een proefmail krijgen, en lukt het opzoeken van hun adres?

    Verstuurt NIETS en verandert NIETS. Bestaat omdat de mails maandenlang
    geruisloos niet aankwamen: het opzoeken van een e-mailadres mag alleen met de
    service_role-sleutel, en die fout werd weggeslikt. Met deze controle zie je
    dat in één keer, zonder te wachten op de dagelijkse taak van 09:00 en zonder
    per ongeluk een klant te mailen.
    """
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Niet toegestaan")

    from datetime import datetime, timedelta, timezone
    from backend.services.billing import GRACE_DAYS, LOCK_NOTICE_MAX_AGE_DAYS, REMINDER_DAYS_BEFORE

    db = get_db()
    now = datetime.now(timezone.utc)
    lock_moment = now - timedelta(days=GRACE_DAYS)

    def _rows(bouw, kolom):
        # Twee heel verschillende fouten, en die moeten niet op één hoop.
        # Een ontbrekende kolom is werk voor jou (een ALTER draaien); een
        # weggevallen verbinding is ruis die vanzelf overgaat. De eerste versie
        # noemde álles "kolom ontbreekt" en wees zo de verkeerde kant op.
        try:
            return execute_with_retry(bouw()).data or []
        except Exception as e:
            tekst = str(e)
            if "42703" in tekst or "does not exist" in tekst.lower():
                return {"fout": f"kolom {kolom} bestaat nog niet in Supabase — draai de ALTER TABLE"}
            return {"fout": f"tijdelijke fout bij het opvragen ({type(e).__name__}) — probeer het zo nog eens"}

    groepen = {
        "1_proef_loopt_af": _rows(lambda: db.table("subscriptions")
            .select("user_id, trial_ends_at").eq("status", "trialing")
            .gte("trial_ends_at", now.isoformat())
            .lt("trial_ends_at", (now + timedelta(days=REMINDER_DAYS_BEFORE)).isoformat())
            .is_("trial_reminder_sent_at", "null"), "trial_reminder_sent_at"),
        "2_laatste_oproep": _rows(lambda: db.table("subscriptions")
            .select("user_id, trial_ends_at").eq("status", "trial_expired")
            .gte("trial_ends_at", (now - timedelta(days=GRACE_DAYS)).isoformat())
            .lt("trial_ends_at", (now + timedelta(days=1) - timedelta(days=GRACE_DAYS)).isoformat())
            .is_("final_reminder_sent_at", "null"), "final_reminder_sent_at"),
        "3_account_op_pauze": _rows(lambda: db.table("subscriptions")
            .select("user_id, trial_ends_at").eq("status", "trial_expired")
            .lt("trial_ends_at", lock_moment.isoformat())
            .gte("trial_ends_at", (lock_moment - timedelta(days=LOCK_NOTICE_MAX_AGE_DAYS)).isoformat())
            .is_("locked_notice_sent_at", "null"), "locked_notice_sent_at"),
    }

    uit = {}
    for naam, rijen in groepen.items():
        if isinstance(rijen, dict):
            uit[naam] = rijen
            continue
        wie = []
        for r in rijen:
            try:
                gevonden = get_admin_db().auth.admin.get_user_by_id(r["user_id"])
                adres = gevonden.user.email if gevonden and gevonden.user else None
                wie.append({"adres": adres or "GEEN ADRES", "proef_eindigde": (r.get("trial_ends_at") or "")[:10]})
            except Exception as e:
                wie.append({"adres": f"OPZOEKEN MISLUKT: {e}", "proef_eindigde": (r.get("trial_ends_at") or "")[:10]})
        uit[naam] = {"aantal": len(rijen), "ontvangers": wie}
    return {"verstuurt_niets": True, "groepen": uit}


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
