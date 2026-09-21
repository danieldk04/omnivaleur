"""
De "verbinding"-campagne: één persoonlijke update-mail aan bestaande gebruikers,
in drie tonen. Besloten 21-09-2026 met Daniel, zie docs/team-notes.md voor de
volledige afweging (segmenten, taalkeuze, toon).

Drie groepen naar HUIDIGE abonnementsstatus, niet naar geschiedenis, zodat
niemand in twee groepen tegelijk kan vallen (een eerdere versie koppelde de
groep aan "ooit iets geplaatst" en overlapte daardoor met "proef verlopen"):

    trial     subscriptions.status == 'trialing'
    inactive  subscriptions.status == 'trial_expired'
    customer  subscriptions.status in ('active', 'complimentary', 'payment_processing')

Wie 'canceled' is valt bewust buiten alle drie: geen van de drie tonen past op
iemand die zelf heeft opgezegd. Zie terughaalcampagne.py voor de eerdere,
aparte actie richting oud-klanten (08-09-2026) met een heel andere insteek
(bugfix-excuus + proefverlenging) — deze mail belooft niets en verlengt niets.

TAAL. Er is geen betrouwbaar taal- of landveld per gebruiker (7 van 53 hebben
Preferences ingevuld, allemaal 'Nederland'; auth-metadata kent geen taalveld).
Daarom is dit ÉÉN mail voor iedereen: Engels als hoofdtaal (zoals het
dashboard), met de Nederlandse vertaling direct onder elk stuk tekst in
kleiner, gedempt lettertype. Geen aparte NL/EN-variant per gebruiker.

NAAM. Er wordt nergens een voornaam bewaard (niet in auth-metadata, niet in
een eigen tabel, niet vanuit Stripe). "Hi {voornaam}," is daardoor in de
praktijk altijd "Hi," — dat is geen bug, dat is de huidige stand van de data.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

CTA_URL = "https://omnivaleur.com/app"
UNSUBSCRIBE_BASE = "https://omnivaleur.com/api/mail-verbinding/unsubscribe"

# Geldige groepen en hun abonnementsstatussen. 'customer' bevat ook
# payment_processing (SEPA-incasso onderweg): die persoon is voor onze
# boodschap al klant, ook al staat Stripe nog niet op 'active'.
GROEP_STATUSSEN = {
    "trial": ("trialing",),
    "inactive": ("trial_expired",),
    "customer": ("active", "complimentary", "payment_processing"),
}

# ── Inhoud van de vier blokjes, gedeeld door alle drie de groepen ───────────
# Elk feit is nagekeken tegen de code/kennisbank op 21-09-2026 (zie
# docs/team-notes.md), niet verzonnen. De laatste (verwijzing) krijgt een
# ander accent (mint) om hem visueel te onderscheiden van "wat we gebouwd
# hebben": dit is iets VOOR de lezer, geen changelog-regel.
BLOKJES = [
    {
        "titel_en": "Instant failure alerts in your dashboard",
        "tekst_en": "If a listing fails, you'll know within seconds, right in your "
                     "dashboard, with the exact time of the last attempt.",
        "titel_nl": "Je ziet nu meteen of het gelukt is",
        "tekst_nl": "Loopt een plaatsing vast, dan zie je dat nu meteen in je dashboard, "
                     "met het tijdstip van de laatste poging.",
        "accent": "blue",
    },
    {
        "titel_en": "Facebook Marketplace: up to 10 photos, automatically",
        "tekst_en": "Your listings go up with more photos, no extra clicks from you.",
        "titel_nl": "Facebook Marketplace: automatisch tot 10 foto's",
        "tekst_nl": "Op Facebook Marketplace gaan er nu automatisch tot tien foto's mee, "
                     "zonder dat je daar iets voor hoeft te doen.",
        "accent": "blue",
    },
    {
        "titel_en": "2dehands listings now renew instead of restart",
        "tekst_en": "A refresh renews the listing in place. It no longer risks "
                     "disappearing by accident.",
        "titel_nl": "2dehands verlengt nu, in plaats van opnieuw te plaatsen",
        "tekst_nl": "Op 2dehands wordt een advertentie nu verlengd in plaats van "
                     "opnieuw geplaatst, zodat hij niet meer per ongeluk verdwijnt.",
        "accent": "blue",
    },
    {
        "titel_en": "Earn a free month, without limits",
        "tekst_en": "Every seller you refer who becomes a paying customer earns you a "
                     "free month. Bring in three, get three months free.",
        "titel_nl": "Elke aanbreng levert een gratis maand op",
        "tekst_nl": "Elke verkoper die je aanbrengt en klant wordt, levert jou een "
                     "gratis maand op. Breng je er drie aan, dan zijn dat drie maanden "
                     "gratis.",
        "accent": "mint",
    },
]

# ── Per-groep toon: aanhef, onderwerp, knop, slotzin ────────────────────────
GROEPEN = {
    "trial": {
        "subject_en": "How's it going with your first listings?",
        "subject_nl": "Hoe gaat het met je eerste advertenties?",
        "greeting_en": "Daniel here, founder of Omnivaleur. Wanted to reach out "
                        "personally instead of another system email. A lot has "
                        "shipped lately, here's what actually matters to you:",
        "greeting_nl": "Daniel hier, oprichter van Omnivaleur. Ik wilde je persoonlijk "
                        "laten weten hoe het gaat, in plaats van een systeemmailtje. "
                        "Er is best wat gebouwd, dit is wat voor jou telt:",
        "extra_en": None,
        "extra_nl": None,
        "cta_en": "List your first item",
        "cta_nl": "Plaats je eerste advertentie",
        "closing_en": "Takes about two minutes. Stuck? Just reply, I read these myself.",
        "closing_nl": "Kost ongeveer twee minuten. Loop je vast? Antwoord gewoon, ik lees dit zelf.",
    },
    "inactive": {
        "subject_en": "A lot has changed since you last checked",
        "subject_nl": "Er is best wat veranderd sinds je laatst keek",
        "greeting_en": "Daniel here, founder of Omnivaleur. It's been a while since "
                        "you last used Omnivaleur, and quite a bit has shipped since then.",
        "greeting_nl": "Daniel hier, oprichter van Omnivaleur. Het is een tijdje "
                        "geleden dat je Omnivaleur gebruikte, en er is sindsdien best "
                        "wat gebouwd.",
        "extra_en": "Still EUR 19.99/month, up to 5 channels at once. Pick up right "
                     "where you left off, nothing is lost.",
        "extra_nl": "Nog steeds EUR 19,99 per maand, tot 5 kanalen tegelijk. Je begint "
                     "precies waar je gebleven was, niets is kwijt.",
        "cta_en": "Start again",
        "cta_nl": "Opnieuw beginnen",
        "closing_en": "Hit a specific snag before? Just reply, I read these myself.",
        "closing_nl": "Liep je ergens specifiek tegenaan? Antwoord gewoon, ik lees dit zelf.",
    },
    "customer": {
        "subject_en": "Thank you for using Omnivaleur",
        "subject_nl": "Bedankt dat je Omnivaleur gebruikt",
        "greeting_en": "Daniel here, founder. No sales pitch this time, just a thank "
                        "you. Here's what's improved for you lately:",
        "greeting_nl": "Daniel hier, oprichter. Geen verkooppraatje deze keer, gewoon "
                        "een bedankje. Dit is wat er recent voor jou is verbeterd:",
        "extra_en": "Everything you already use works exactly the way you're used to. "
                     "Nothing you need to do here.",
        "extra_nl": "Alles wat je al gebruikt werkt precies zoals je gewend bent. Hier "
                     "hoef je niets voor te doen.",
        "cta_en": "Go to your dashboard",
        "cta_nl": "Naar je dashboard",
        "closing_en": "Questions or something that could be better? Just reply, I read these myself.",
        "closing_nl": "Vragen of iets wat beter kan? Antwoord gewoon, ik lees dit zelf.",
    },
}

_ACCENT_BG = {"blue": "#f0f9ff", "mint": "#ecfdf5"}
_ACCENT_BORDER = {"blue": None, "mint": "1px solid #a7f3d0"}


def _blok_html(b: dict) -> str:
    # .get() met een veilige terugval: "accent" is optioneel (ook voor de
    # wekelijkse update, zie scripts/mail_update_prompt.txt), en een onbekende
    # waarde mag de hele mail nooit laten crashen op een KeyError.
    accent = b.get("accent") if b.get("accent") in _ACCENT_BG else "blue"
    achtergrond = _ACCENT_BG[accent]
    rand = f'border:{_ACCENT_BORDER[accent]};' if _ACCENT_BORDER[accent] else ""
    # "afbeelding_url" is optioneel: een echte screenshot van de live app,
    # nooit AI-gegenereerd. Alleen https, anders negeren we hem stil in
    # plaats van een kapotte afbeelding te tonen.
    afbeelding_url = b.get("afbeelding_url") or ""
    afbeelding_html = ""
    if afbeelding_url.startswith("https://"):
        afbeelding_html = (
            f'<tr><td style="padding:0 0 12px;">'
            f'<img src="{afbeelding_url}" alt="" width="100%" '
            f'style="display:block;max-width:100%;border-radius:8px;border:1px solid #e2e8f0;">'
            f'</td></tr>'
        )
    return f"""
  <tr><td style="padding:10px 28px 6px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{achtergrond};border-radius:10px;{rand}">
      <tr><td style="padding:16px 20px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        {afbeelding_html}
        <tr><td>
        <p style="margin:0 0 5px;font-size:14.5px;font-weight:700;color:#0f172a;">{b['titel_en']}</p>
        <p style="margin:0 0 4px;font-size:13.5px;line-height:1.55;color:#334155;">{b['tekst_en']}</p>
        <p style="margin:0;font-size:11.5px;line-height:1.5;color:#64748b;font-style:italic;">{b['titel_nl']}. {b['tekst_nl']}</p>
        </td></tr>
        </table>
      </td></tr>
    </table>
  </td></tr>"""


def _blok_text(b: dict) -> str:
    return (f"{b['titel_en']}\n{b['tekst_en']}\n"
            f"({b['titel_nl']}. {b['tekst_nl']})\n")


def render_html(groep: str, afmeldlink: str, blokjes: list[dict] | None = None) -> str:
    g = GROEPEN[groep]
    blokjes_html = "".join(_blok_html(b) for b in (blokjes or BLOKJES))
    extra_html = ""
    if g["extra_en"]:
        extra_html = f"""
  <tr><td style="padding:18px 28px 4px;">
    <p style="margin:0;font-size:13.5px;line-height:1.55;color:#334155;">{g['extra_en']}</p>
    <p style="margin:2px 0 0;font-size:11.5px;line-height:1.5;color:#94a3b8;font-style:italic;">{g['extra_nl']}</p>
  </td></tr>"""
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f9ff;">
<tr><td align="center" style="padding:28px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

  <tr><td style="background:#2563eb;background:linear-gradient(135deg,#2563eb,#34d399);padding:22px 28px;" bgcolor="#2563eb">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="vertical-align:middle;"><img src="https://omnivaleur.com/logo.png" width="28" height="28" alt="" style="display:block;border-radius:6px;"></td>
      <td style="vertical-align:middle;padding-left:10px;font-size:17px;font-weight:800;color:#ffffff;letter-spacing:-.2px;">Omnivaleur</td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:32px 28px 4px;">
    <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#0f172a;">Hi,</p>
    <p style="margin:0 0 4px;font-size:15px;line-height:1.6;color:#0f172a;">{g['greeting_en']}</p>
    <p style="margin:0 0 22px;font-size:12.5px;line-height:1.55;color:#94a3b8;font-style:italic;">{g['greeting_nl']}</p>
  </td></tr>
{blokjes_html}{extra_html}

  <tr><td style="padding:24px 28px 6px;" align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="border-radius:10px;background:#2563eb;" bgcolor="#2563eb">
        <a href="{CTA_URL}" style="display:inline-block;padding:13px 30px;font-size:14.5px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;">{g['cta_en']}</a>
      </td>
    </tr></table>
    <p style="margin:14px 0 0;font-size:12px;color:#64748b;">{g['closing_en']}<br><span style="font-style:italic;color:#94a3b8;">{g['closing_nl']}</span></p>
  </td></tr>

  <tr><td style="padding:28px 28px 8px;border-top:1px solid #e2e8f0;margin-top:10px;">
    <p style="margin:22px 0 0;font-size:14px;color:#0f172a;">Daniel<br><span style="color:#64748b;font-size:13px;">Founder, Omnivaleur</span></p>
  </td></tr>

  <tr><td style="padding:18px 28px 26px;">
    <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.6;">You're getting this because you have an Omnivaleur account. <a href="{afmeldlink}" style="color:#94a3b8;">Unsubscribe from updates like this</a>.<br>Je krijgt deze mail omdat je een Omnivaleur-account hebt. <a href="{afmeldlink}" style="color:#94a3b8;">Afmelden voor dit soort updates</a>.</p>
  </td></tr>

</table>
</td></tr>
</table>"""


def render_text(groep: str, afmeldlink: str, blokjes: list[dict] | None = None) -> str:
    g = GROEPEN[groep]
    delen = [
        "Hi,",
        "",
        g["greeting_en"],
        f"({g['greeting_nl']})",
        "",
    ]
    delen += [_blok_text(b) for b in (blokjes or BLOKJES)]
    if g["extra_en"]:
        delen += [g["extra_en"], f"({g['extra_nl']})", ""]
    delen += [
        f"{g['cta_en']}: {CTA_URL}",
        "",
        g["closing_en"],
        f"({g['closing_nl']})",
        "",
        "Daniel",
        "Founder, Omnivaleur",
        "",
        "You're getting this because you have an Omnivaleur account.",
        f"Unsubscribe: {afmeldlink}",
        "Je krijgt deze mail omdat je een Omnivaleur-account hebt.",
        f"Afmelden: {afmeldlink}",
    ]
    return "\n".join(delen)


def render_subject(groep: str) -> str:
    g = GROEPEN[groep]
    return f"{g['subject_en']} / {g['subject_nl']}"


# ── Afmeldlink: ondertekend zodat niemand andermans account kan afmelden ───
def _token(user_id: str) -> str:
    if not settings.secret_key or settings.secret_key == "change-me":
        logger.warning("SECRET_KEY staat nog op de standaardwaarde — afmeldlinks zijn "
                        "hierdoor te raden. Zet een echte waarde op Railway.")
    return hmac.new(settings.secret_key.encode(), user_id.encode(), hashlib.sha256).hexdigest()[:24]


def afmeldlink(user_id: str) -> str:
    return f"{UNSUBSCRIBE_BASE}?u={user_id}&t={_token(user_id)}"


def token_geldig(user_id: str, token: str) -> bool:
    return hmac.compare_digest(_token(user_id), token or "")


# ── Segmenten bepalen ────────────────────────────────────────────────────────
def _is_afgemeld(afgemeld_ids: set[str], user_id: str) -> bool:
    return user_id in afgemeld_ids


def segmenten() -> dict[str, list[dict]]:
    """Elk van de drie groepen: [{'user_id':, 'email':}, ...].

    Sluit test-/beoordelaarsaccounts uit (dezelfde herkenning als de
    terughaalcampagne: plus-adressering, eigen domeinen, test/demo/reviewer in
    het adres) en iedereen die zich al heeft afgemeld. Leest uitsluitend met
    de service-sleutel."""
    from backend.database import get_admin_db
    from backend.services.terughaalcampagne import _is_testaccount

    db = get_admin_db()

    gebruikers: dict[str, str] = {}
    page = 1
    while True:
        batch = db.auth.admin.list_users(page=page, per_page=200)
        if not batch:
            break
        for u in batch:
            email = (getattr(u, "email", None) or "").strip().lower()
            if email:
                gebruikers[u.id] = email
        if len(batch) < 200:
            break
        page += 1

    subs = db.table("subscriptions").select("user_id,status").execute().data or []
    status_van = {s["user_id"]: s.get("status") for s in subs}

    afgemeld = {r["user_id"] for r in
                (db.table("mail_unsubscribed").select("user_id").execute().data or [])}

    resultaat: dict[str, list[dict]] = {"trial": [], "inactive": [], "customer": []}
    for uid, email in gebruikers.items():
        if _is_afgemeld(afgemeld, uid) or _is_testaccount(email):
            continue
        status = status_van.get(uid)
        for groep, statussen in GROEP_STATUSSEN.items():
            if status in statussen:
                resultaat[groep].append({"user_id": uid, "email": email})
                break
    return resultaat


# ── Versturen ────────────────────────────────────────────────────────────────
DRIE_DAGEN_SECONDEN = 3 * 24 * 3600


def _recent_gemaild(user_ids: list[str]) -> set[str]:
    """Wie van deze mensen kreeg de laatste drie dagen AL campagnemail, van
    welke soort dan ook. Regel 5: hoogstens één mail per persoon per drie
    dagen, over alle soorten heen."""
    from datetime import datetime, timedelta, timezone

    from backend.database import fetch_all_in, get_admin_db

    if not user_ids:
        return set()
    grens = (datetime.now(timezone.utc) - timedelta(seconds=DRIE_DAGEN_SECONDEN)).isoformat()
    db = get_admin_db()
    rijen = fetch_all_in(
        lambda: db.table("mail_campaign_log").select("user_id,sent_at").gte("sent_at", grens),
        "user_id", user_ids, order_by="id",
    )
    return {r["user_id"] for r in rijen}


def _log(user_id: str, email: str, kind: str, groep: str, resend_id: str | None) -> None:
    from backend.database import get_admin_db
    get_admin_db().table("mail_campaign_log").insert({
        "user_id": user_id, "email": email, "kind": kind, "segment": groep,
        "taal": "en", "resend_id": resend_id,
    }).execute()


# Regel 8: bounce onder 2%, klachten onder 0,1%. Boven die grens stopt de
# reeks vanzelf en krijgt Daniel een melding. Pas boven MINIMUM_STEEKPROEF
# metingen: één bounce op de eerste drie verstuurde mails is 33% en zegt
# niets, dat zou de hele campagne op de eerste dag al blokkeren.
BOUNCE_GRENS = 0.02
KLACHT_GRENS = 0.001
MINIMUM_STEEKPROEF = 15


def _campagne_gezondheid() -> dict:
    """Bounce- en klachtenpercentage over ALLE eerder verstuurde verbinding-mail
    tot nu toe (elke groep samen), gemeten via mail_events (de Resend-webhook),
    gekoppeld op resend_id/email_id. Onbekend als de webhook een event nog niet
    heeft afgeleverd; dat telt dan simpelweg nog niet mee."""
    from backend.database import fetch_all_in, get_admin_db

    db = get_admin_db()
    log = db.table("mail_campaign_log").select("resend_id").execute().data or []
    verstuurd = len(log)
    ids = [r["resend_id"] for r in log if r.get("resend_id")]
    if not ids:
        return {"verstuurd": verstuurd, "bounced": 0, "geklaagd": 0, "bounce_pct": 0.0, "klacht_pct": 0.0}
    events = fetch_all_in(lambda: db.table("mail_events").select("email_id,type"),
                          "email_id", ids, order_by="id")
    bounced = len({e["email_id"] for e in events if e.get("type") == "email.bounced"})
    geklaagd = len({e["email_id"] for e in events if e.get("type") == "email.complained"})
    return {
        "verstuurd": verstuurd, "bounced": bounced, "geklaagd": geklaagd,
        "bounce_pct": bounced / verstuurd if verstuurd else 0.0,
        "klacht_pct": geklaagd / verstuurd if verstuurd else 0.0,
    }


def _meld_gestopt(gezondheid: dict) -> None:
    from backend.services.email import send_email

    send_email(
        "Omnivaleur: verbinding-campagne automatisch gestopt",
        "De bounce- of klachtengrens is overschreden, dus er is niets meer "
        "verstuurd voor deze aanroep.\n\n"
        f"Verstuurd tot nu toe: {gezondheid['verstuurd']}\n"
        f"Bounces: {gezondheid['bounced']} ({gezondheid['bounce_pct']:.1%}, grens {BOUNCE_GRENS:.0%})\n"
        f"Klachten: {gezondheid['geklaagd']} ({gezondheid['klacht_pct']:.1%}, grens {KLACHT_GRENS:.1%})\n\n"
        "Kijk in het Resend-dashboard welke adressen het zijn voor je verder gaat.\n",
    )


def verstuur_groep(groep: str, dry_run: bool = True, blokjes: list[dict] | None = None,
                   kind_label: str = "verbinding") -> dict:
    """Verstuurt (of toont, bij dry_run) de mail aan iedereen in deze groep die
    niet al de laatste drie dagen campagnemail kreeg.

    `blokjes` is None voor de vaste (evergreen) inhoud, of een lijst voor de
    wekelijkse update (zie huidige_weekupdate). `kind_label` scheidt de twee
    soorten in mail_campaign_log, zodat de 3-dagenregel ze wel samen telt
    (dezelfde functie, dezelfde tabel) maar de meting uit STAP 4 ze uit elkaar
    kan houden."""
    from backend.services.email import send_email_checked

    if groep not in GROEPEN:
        raise ValueError(f"onbekende groep: {groep}")

    leden = segmenten()[groep]
    recent = _recent_gemaild([r["user_id"] for r in leden])
    te_mailen = [r for r in leden if r["user_id"] not in recent]

    if dry_run:
        return {
            "dry_run": True, "groep": groep, "aantal_in_groep": len(leden),
            "overgeslagen_recent_gemaild": len(leden) - len(te_mailen),
            "zou_versturen_aan": len(te_mailen),
            "voorbeeld": [r["email"] for r in te_mailen[:10]],
        }

    gezondheid = _campagne_gezondheid()
    if gezondheid["verstuurd"] >= MINIMUM_STEEKPROEF and (
            gezondheid["bounce_pct"] > BOUNCE_GRENS or gezondheid["klacht_pct"] > KLACHT_GRENS):
        _meld_gestopt(gezondheid)
        return {"dry_run": False, "groep": groep, "gestopt": True,
                "reden": "bounce- of klachtengrens overschreden", **gezondheid}

    kind = f"{kind_label}_{groep}"
    subject = render_subject(groep)
    verstuurd, mislukt = [], []
    for r in te_mailen:
        link = afmeldlink(r["user_id"])
        html = render_html(groep, link, blokjes=blokjes)
        text = render_text(groep, link, blokjes=blokjes)
        try:
            resend_id = send_email_checked(subject, text, to=r["email"],
                                           reply_to=settings.reply_to_email, html=html,
                                           unsubscribe_url=link)
            _log(r["user_id"], r["email"], kind, groep, resend_id)
            verstuurd.append(r["email"])
        except Exception as e:
            logger.exception(f"Mail ({kind}) mislukt voor {r['email']}")
            mislukt.append({"email": r["email"], "error": f"{type(e).__name__}: {e}"})
    logger.info(f"Mail {kind}: {len(verstuurd)} verstuurd, {len(mislukt)} mislukt")
    return {"dry_run": False, "groep": groep, "verstuurd": len(verstuurd), "mislukt": mislukt,
            "ontvangers": verstuurd}


def verstuur_test(groep: str, naar: str, blokjes: list[dict] | None = None) -> None:
    """[TEST]-mail naar één adres, met een nep-afmeldlink zodat er niets aan de
    echte tabel verandert. Raakt geen enkele klantrij aan."""
    from backend.services.email import send_email_checked

    if groep not in GROEPEN:
        raise ValueError(f"onbekende groep: {groep}")
    link = f"{UNSUBSCRIBE_BASE}?u=test&t=test"
    subject = f"[TEST] {render_subject(groep)}"
    html = render_html(groep, link, blokjes=blokjes)
    text = render_text(groep, link, blokjes=blokjes)
    send_email_checked(subject, text, to=naar, reply_to=settings.reply_to_email, html=html,
                       unsubscribe_url=link)


# ── Wekelijkse update: inhoud die een lokale, geplande sessie klaarzet ──────
#
# WAAROM EEN APARTE TABEL EN NIET GEWOON BLOKJES OVERSCHRIJVEN. De evergreen
# BLOKJES hierboven blijven werken als niemand deze week iets nieuws heeft
# klaargezet — anders zou een wekelijkse sessie die zelf niets vond de vaste
# inhoud kunnen laten verlopen. Regel 21-09-2026 (Daniel): "alleen als er echt
# iets nieuws is". Bewijs voor de inhoud is nagekeken tegen git log en
# docs/team-notes.md, nooit verzonnen: REGEL 2 verbiedt een AI-aanroep bij het
# versturen zelf, dus de sessie die dit schrijft doet dat vooraf, niet live.
def stel_weekupdate_op(blokjes: list[dict], week_van: str) -> None:
    from backend.database import get_admin_db

    if not blokjes:
        raise ValueError("geen blokjes meegegeven — een lege update wordt nooit klaargezet")
    for b in blokjes:
        for veld in ("titel_en", "tekst_en", "titel_nl", "tekst_nl"):
            if not b.get(veld):
                raise ValueError(f"blokje mist '{veld}': {b}")
        b.setdefault("accent", "blue")
    get_admin_db().table("mail_update_actueel").upsert({
        "id": "current", "blokjes": blokjes, "week_van": week_van, "status": "concept",
    }, on_conflict="id").execute()


def huidige_weekupdate() -> dict | None:
    from backend.database import get_admin_db

    rij = (get_admin_db().table("mail_update_actueel").select("*")
           .eq("id", "current").limit(1).execute().data or [])
    return rij[0] if rij else None


def ontbrekende_screenshots(blokjes: list[dict]) -> list[str]:
    """Koppen (titel_en) van blokjes die de automatische sessie heeft
    gemarkeerd met "screenshot_nodig": true, maar die nog geen (geldige
    https-)afbeelding_url hebben. Wordt gebruikt om de echte verzending van
    de wekelijkse update tegen te houden totdat Daniel de screenshot heeft
    toegevoegd — zie docs/team-notes.md 21-09-2026."""
    ontbrekend = []
    for b in blokjes:
        if not b.get("screenshot_nodig"):
            continue
        url = (b.get("afbeelding_url") or "").strip()
        if not url.startswith("https://"):
            ontbrekend.append(b.get("titel_en", "(zonder titel)"))
    return ontbrekend
