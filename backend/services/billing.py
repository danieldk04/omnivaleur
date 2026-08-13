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

# Hoe ver terug de "je account staat op pauze"-mail nog verstuurd wordt. Houdt de
# eerste run klein: alleen wie net is buitengesloten, niet iedereen uit het
# verleden. Wil je die oude groep alsnog benaderen, doe dat dan bewust en met een
# eigen tekst.
LOCK_NOTICE_MAX_AGE_DAYS = 5

# Het adres in de handtekening en in Reply-To: hier komen antwoorden binnen.
# Bewust niet de afzender: uitgaand heet alles Omnivaleur, maar de postbus die
# gelezen wordt is een andere.
CONTACT_EMAIL = settings.reply_to_email

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


def _in_phrase(days_left: int) -> str:
    """'today' / 'tomorrow' / 'in 2 days' — een mail die "in 1 day" zegt terwijl
    de proef diezelfde middag afloopt, leest als een fout."""
    if days_left <= 0:
        return "today"
    if days_left == 1:
        return "tomorrow"
    return f"in {days_left} days"


def _days_until(moment, now) -> int:
    """Aantal kalenderdagen tot dat moment. Vandaag = 0, morgen = 1.

    Bewust op de kalender en niet op 24-uursblokken: een proef die vanmiddag om
    drie uur afloopt is 'today', niet 'in 1 day'.
    """
    if not moment:
        return 0
    return max(0, (moment.date() - now.date()).days)


def trial_reminder_email(days_left: int, grace_days: int = GRACE_DAYS) -> tuple[str, str]:
    """Eerste herinnering: twee dagen voor het einde van de proefperiode."""
    when = _in_phrase(days_left)
    subject = f"Quick heads up: Your Omnivaleur trial ends {when}"
    grace_word = "day" if grace_days == 1 else "days"
    body = f"""Hi there,

Daniel here, founder of Omnivaleur.

I noticed your free trial is coming to an end {when}. I wanted to reach out
personally to make sure everything has been running smoothly for you so far.

Here is what happens next:

  * Until then: Your trial remains fully active.

  * After that: You will get a {grace_days}-day grace period to make your decision.

  * Once those {grace_days} {grace_word} are up: Your account will be locked. Your active
    cross-listings will stay untouched on your platforms, but cross-listing
    functions and new outgoing listings will pause until you upgrade.

Upgrading takes less than a minute. Your items, connected channels, and history
will stay completely intact so you can keep going without missing a beat.

Activate Pro here: {settings.app_url} (€19.99/month, cancel anytime)

If you hit any snags, have questions, or feel something is missing for your
workflow, please email me directly at {CONTACT_EMAIL}
or simply reply to this message. I read every email and I am always happy to
help you get the most out of Omnivaleur.

Best regards,

Daniel
Founder, Omnivaleur
{CONTACT_EMAIL}
"""
    return subject, body


def final_warning_email(days_left: int) -> tuple[str, str]:
    """Tweede en laatste herinnering: de laatste dag van de bedenktijd, vlak
    voordat het account op slot gaat."""
    when = _in_phrase(days_left)
    subject = f"Last call: Your Omnivaleur account locks {when}"
    body = f"""Hi,

Daniel here again from Omnivaleur.

Quick heads-up: your grace period ends {when}, and this is the last email I will
send you about it. Once the clock runs out, your account will lock and automatic
cross-listing will stop.

A quick reminder of what happens:

  * No new listings: The extension pauses and no new items go out.

  * Your items stay live: Everything on Vinted, Marktplaats, eBay, and your
    other channels stays published. Nothing gets deleted.

  * Your setup is safe: Your history, items, and connected accounts stay intact
    for whenever you are ready to return.

If Omnivaleur is saving you time and keeping your store organized, you can keep
everything running without a break.

Keep Pro active: {settings.app_url} (€19.99/month, cancel anytime)

If you have decided to pass, I would genuinely appreciate knowing why. A single
sentence in reply to this mail or sent to {CONTACT_EMAIL} helps me make the
platform better.

Best regards,

Daniel
Founder, Omnivaleur
{CONTACT_EMAIL}
"""
    return subject, body


def locked_email(days_left: int = 0) -> tuple[str, str]:
    """Derde en laatste mail: het slot is dicht.

    Tot nu toe stopte de communicatie vlak vóór het slot. Wie er daarna tegenaan
    liep, kreeg alleen nog een foutmelding in de app — en een actieve gebruiker
    verdween zo geruisloos, zonder ooit iets van zich te laten horen. Dat is
    precies hoe we een klant kwijtraakten die het product gewoon gebruikte.
    """
    subject = "Your Omnivaleur account is now paused"
    body = f"""Hi,

Daniel here from Omnivaleur.

Your trial and grace period have both ended, so your account is paused as of
today. I did not want that to happen quietly, so here is exactly where you stand.

What this means right now:

  * Your listings are untouched. Everything you published on Vinted,
    Marktplaats, 2dehands, eBay and your other channels is still live and still
    yours. Nothing was removed.

  * Cross-listing is paused. The extension will not send out new listings until
    the account is active again.

  * Nothing is lost. Your items, photos, connected accounts and history are all
    still there, exactly as you left them. Turning Pro back on picks up where
    you stopped.

Pick up where you left off: {settings.app_url} (€19.99/month, cancel anytime)

And if you are not coming back, would you tell me why? One sentence is enough,
and it is genuinely the most useful thing you can send me. Maybe something was
broken, maybe a channel you needed was missing, maybe it just was not for you —
I would rather know than guess.

Reply to this email or write to {CONTACT_EMAIL}. It comes straight to me.

Best regards,

Daniel
Founder, Omnivaleur
{CONTACT_EMAIL}
"""
    return subject, body


def _mail_batch(rows: list[dict], marker_column: str, build_mail, moment_key) -> None:
    """Stuurt één mail per rij en zet daarna het vinkje. Mislukt het versturen,
    dan blijft het vinkje leeg en probeert de taak het morgen opnieuw."""
    from backend.services.email import send_email

    db = get_db()
    now = datetime.now(timezone.utc)
    for sub in rows:
        try:
            user = db.auth.admin.get_user_by_id(sub["user_id"])
            email = user.user.email if user and user.user else None
        except Exception as e:
            # Dit was een stille `continue`, en daardoor is er in 27 abonnementen
            # nooit één herinnering verstuurd zonder dat iemand het merkte: het
            # opzoeken van een e-mailadres mag alleen met de service_role-sleutel,
            # en met de anon-sleutel geeft Supabase hier "User not allowed".
            # Zie /health → supabase_key_role.
            logger.error(
                f"HERINNERING NIET VERSTUURD aan {sub['user_id']}: e-mailadres niet op te "
                f"vragen ({e}). Draait de server op de anon-sleutel in plaats van service_role?"
            )
            continue
        if not email:
            logger.error(f"HERINNERING NIET VERSTUURD: gebruiker {sub['user_id']} heeft geen e-mailadres")
            continue

        subject, body = build_mail(_days_until(moment_key(sub), now))
        if not send_email(subject=subject, body=body, to=email, reply_to=CONTACT_EMAIL):
            continue
        db.table("subscriptions").update({marker_column: now.isoformat()}).eq("id", sub["id"]).execute()
        logger.info(f"{marker_column} verstuurd naar {email}")


def _select_or_warn(query_fn, column: str):
    """De markeerkolommen worden met de hand in Supabase gezet. Ontbreekt er een,
    dan zou de taak niet kunnen onthouden wie hij al gemaild heeft en zou hij
    iedereen dagelijks opnieuw mailen — dus stopt hij dan liever."""
    try:
        return query_fn().data
    except Exception:
        logger.exception(f"Mails overgeslagen: kolom {column} ontbreekt nog in Supabase")
        return None


async def send_trial_reminders():
    """
    Draait dagelijks. Twee mails, allebei precies één keer per gebruiker:

    1. De proef loopt nog en eindigt binnen twee dagen.
    2. De proef is voorbij en de laatste dag bedenktijd is aangebroken.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # 1 — proef eindigt binnen twee dagen. Bewust geen schijfje van één dag:
    # wie zich 30 uur voor het einde aanmeldt zou anders tussen twee dagelijkse
    # runs door vallen en nooit iets horen.
    rows = _select_or_warn(
        lambda: db.table("subscriptions")
        .select("id, user_id, trial_ends_at")
        .eq("status", "trialing")
        .gte("trial_ends_at", now.isoformat())
        .lt("trial_ends_at", (now + timedelta(days=REMINDER_DAYS_BEFORE)).isoformat())
        .is_("trial_reminder_sent_at", "null")
        .execute(),
        "trial_reminder_sent_at",
    )
    if rows:
        logger.info(f"Trial reminder: {len(rows)} gebruiker(s)")
        _mail_batch(rows, "trial_reminder_sent_at", trial_reminder_email,
                    lambda sub: _parse_ts(sub.get("trial_ends_at")))

    # 2 — laatste dag van de bedenktijd: de proef is voorbij en het slot valt
    # binnen 24 uur. Wie inmiddels betaalt heeft geen status trial_expired meer
    # en krijgt deze mail dus niet.
    lock_within_a_day = now + timedelta(days=1)
    rows = _select_or_warn(
        lambda: db.table("subscriptions")
        .select("id, user_id, trial_ends_at")
        .eq("status", "trial_expired")
        .gte("trial_ends_at", (now - timedelta(days=GRACE_DAYS)).isoformat())
        .lt("trial_ends_at", (lock_within_a_day - timedelta(days=GRACE_DAYS)).isoformat())
        .is_("final_reminder_sent_at", "null")
        .execute(),
        "final_reminder_sent_at",
    )
    if rows:
        logger.info(f"Final warning: {len(rows)} gebruiker(s)")
        _mail_batch(rows, "final_reminder_sent_at", final_warning_email,
                    lambda sub: (_parse_ts(sub.get("trial_ends_at")) + timedelta(days=GRACE_DAYS))
                    if _parse_ts(sub.get("trial_ends_at")) else None)

    # 3 — het slot is dicht. Hiervoor stopte de communicatie vlák voor het slot,
    # en daarna hoorde niemand meer iets: een actieve gebruiker werd stilletjes
    # buitengesloten en meldde zich nooit. Eén mail, één keer, zonder deadline
    # erin — hij mag ook gewoon vertellen waarom hij stopt.
    #
    # Bewust alleen sloten van de afgelopen LOCK_NOTICE_MAX_AGE_DAYS dagen. Zonder
    # die ondergrens zou de eerste run ineens iedereen aanschrijven die ooit is
    # verlopen — een mailronde naar oud-klanten die niemand heeft besteld, en die
    # bij spamfilters hard aankomt. Wie eerder is buitengesloten mail je liever
    # bewust, met een tekst die daarbij past.
    lock_moment = now - timedelta(days=GRACE_DAYS)
    rows = _select_or_warn(
        lambda: db.table("subscriptions")
        .select("id, user_id, trial_ends_at")
        .eq("status", "trial_expired")
        .lt("trial_ends_at", lock_moment.isoformat())
        .gte("trial_ends_at", (lock_moment - timedelta(days=LOCK_NOTICE_MAX_AGE_DAYS)).isoformat())
        .is_("locked_notice_sent_at", "null")
        .execute(),
        "locked_notice_sent_at",
    )
    if rows:
        logger.info(f"Lock notice: {len(rows)} gebruiker(s)")
        _mail_batch(rows, "locked_notice_sent_at", lambda _days: locked_email(),
                    lambda sub: _parse_ts(sub.get("trial_ends_at")))


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
        # "active" zonder Stripe-abonnement is geen betaling maar een handmatig
        # gezette rij: die gaf gratis toegang die nooit verliep. Alleen de webhook
        # zet deze status, en die vult altijd stripe_subscription_id.
        if not sub.get("stripe_subscription_id"):
            return {"allowed": False, "reason": "active_zonder_betaling",
                    "grace_ends_at": None, "grace_days_left": 0}
        # Blijft een verlenging uit (bijvoorbeeld doordat webhooks niet aankomen),
        # dan verloopt de toegang na de bedenktijd in plaats van eeuwig door te lopen.
        period_end = _parse_ts(sub.get("current_period_end"))
        if period_end:
            grace_ends = period_end + timedelta(days=GRACE_DAYS)
            if now >= grace_ends:
                return {"allowed": False, "reason": "period_ended",
                        "grace_ends_at": grace_ends.isoformat(), "grace_days_left": 0}
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
