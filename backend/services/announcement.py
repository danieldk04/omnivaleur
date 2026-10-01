"""
Eenmalige aankondiging aan bestaande gebruikers: het afrekenen werkte weken lang
voor niemand, dat is opgelost, en er hoort een kortingscode bij.

Bewust een apart bestand met de tekst erin: de mail gaat naar echte klanten, dus
hij moet leesbaar in de code staan en niet in elkaar gezet worden door een
opsomming van losse regels.
"""
import logging

from backend.database import get_admin_db, get_db

logger = logging.getLogger(__name__)

# Geen kortingspercentage en geen euroteken in de onderwerpregel: dat is precies
# waar Gmail op sorteert, en dan belandt de mail in het tabblad Promoties in plaats
# van in de inbox. Het aanbod staat in de mail zelf, onderaan.
SUBJECT = "Over het betaalprobleem, van Daniel / About the checkout problem"

BODY = """Hoi,

Ik ben Daniel, de man achter Omnivaleur. Ik schrijf dit zelf, dus vergeef me de directheid.

De afgelopen weken kon je simpelweg geen abonnement afsluiten. Niet bij jou, bij niemand. Het leek op je telefoon, je bank of je kaart, dat was het allemaal niet. Het lag aan mijn kant, en het was stuk vanaf de dag dat die knop bestond.

Het is opgelost. Ik heb het opgespoord, gerepareerd en zelf een abonnement van begin tot eind afgerekend om het zeker te weten. Is je proefperiode voorbij, dan kun je Pro nu direct activeren, op je telefoon of je computer, met iDEAL of creditcard. Het werkt zoals het altijd had moeten werken.

Dank aan iedereen die de moeite nam om te melden dat er iets niet klopte. Een bericht heeft meer voor dit product gedaan dan een week testen van mijzelf. Ik hoor liever vandaag een ongemakkelijke waarheid dan een maand vriendelijke stilte.

Als excuus krijg je 25 procent korting op je eerste maand: 14,99 euro in plaats van 19,99 euro, en daarna 19,99 euro per maand. Je hoeft geen code te typen. Open de accountpagina in de app, dan is de korting al toegepast zodra je Pro activeert. Dit geldt de komende 48 uur.

Gaat er nog iets mis, wat dan ook, antwoord dan op deze mail. Die komt rechtstreeks bij mij.

Daniel van Omnivaleur


==========================================


Hi,

I'm Daniel, the person behind Omnivaleur. I'm writing this myself, so forgive the directness.

Over the past weeks, activating a paid subscription simply did not work. Not for you, not for anyone. It looked like your phone, your bank or your card, it was none of those. It was my side, and it was broken from the very first day the button existed.

It's fixed. I traced it, repaired it, and paid for a subscription myself from start to finish to make sure. If your free trial has ended, you can activate Pro right now, on your phone or your computer, with iDEAL or a credit card. It works the way it always should have.

Thank you to everyone who took the time to tell me something was wrong. One message did more for this product than a week of my own testing. I'd rather hear an uncomfortable truth today than a polite silence for a month.

As an apology, your first month is 25 percent off: 14,99 euro instead of 19,99 euro, and 19,99 euro per month after that. You do not have to type a code. Open the Account page in the app and it is already applied when you activate Pro. It stands for the next 48 hours.

If anything still goes wrong, anything at all, reply to this email. It comes straight to me.

Daniel from Omnivaleur
"""


def parse_email_list(raw: str) -> list[str]:
    """Adressen uit een geplakte lijst halen: komma's, puntkomma's, spaties en
    regeleindes door elkaar, en dubbele adressen eruit. Alles zonder @ valt af,
    zodat een meegeplakte kolomkop of datum geen mailpoging wordt."""
    import re

    seen: set[str] = set()
    out: list[str] = []
    for part in re.split(r"[\s,;]+", raw):
        email = part.strip().strip('"\'<>()').lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            continue
        if email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def collect_recipients() -> list[str]:
    """Iedereen zonder betalend abonnement. Wie al betaalt heeft een
    stripe_subscription_id en hoort deze mail niet te krijgen: die leest dan een
    excuus voor een probleem dat hij niet meer heeft."""
    db = get_db()

    paying: set[str] = set()
    rows = db.table("subscriptions").select("user_id, stripe_subscription_id").execute().data or []
    for row in rows:
        if row.get("stripe_subscription_id"):
            paying.add(row["user_id"])

    emails: list[str] = []
    seen: set[str] = set()
    page = 1
    while True:
        users = get_admin_db().auth.admin.list_users(page=page, per_page=200)
        if not users:
            break
        for u in users:
            email = (getattr(u, "email", None) or "").strip().lower()
            if not email or email in seen or u.id in paying:
                continue
            seen.add(email)
            emails.append(email)
        if len(users) < 200:
            break
        page += 1
    return emails


# ── Omnivaleur Light (30-09-2026) ────────────────────────────────────────────
#
# Eén mail aan iedereen die nu geen lopend abonnement heeft. Platte tekst, zonder
# opmaaktekens en zonder streepjes als leesteken: hij gaat zo de deur uit.
# Geen euroteken of percentage in de onderwerpregel, dat is wat Gmail naar
# Promoties stuurt. Eén taal (Nederlands), zoals Daniel vroeg.

LIGHT_SUBJECT = "Een goedkoper abonnement voor wie minder verkoopt, van Daniel"

LIGHT_BODY = """Hoi,

Ik ben Daniel, de man achter Omnivaleur. Ik schrijf dit zelf.

Niet iedereen verkoopt de hele dag. Als je een paar tientjes artikelen tegelijk online hebt staan, is 19,99 euro per maand veel geld voor wat je er per maand mee verdient. Daar heb ik iets voor gebouwd.

Omnivaleur Light kost 9,99 euro per maand, inclusief btw. Je krijgt dezelfde werking als Pro: een artikel één keer invoeren en op Marktplaats, 2dehands, Vinted, eBay en Shopify zetten, automatisch weghalen als het ergens verkocht is, en automatisch herplaatsen. Het enige verschil is dat Light bedoeld is voor maximaal 20 actieve artikelen tegelijk. Verkoop je iets, dan komt er weer ruimte vrij. Wat al online staat blijft altijd gewoon werken.

Heb je meer artikelen, of verkoop je zakelijk? Dan blijft Pro er: 19,99 euro per maand exclusief btw, zonder limiet. Wisselen kan later altijd.

Zo kies je: ga naar https://omnivaleur.com/app.html, open Account en kies Light of Pro. Loopt je proefperiode nog, dan loopt die gewoon door en betaal je pas als hij afloopt. Is je proefperiode voorbij, dan staan je artikelen en koppelingen er nog en kun je meteen verder.

Past dit niet bij je, of mis je iets? Antwoord dan op deze mail. Die komt rechtstreeks bij mij, en ik lees hem ook echt.

Daniel van Omnivaleur
"""

LIGHT_MAIL_TYPE = "omnivaleur.light_mail"
_EIGEN_DOMEINEN = ("revaleur.com", "crosslisteu.com")


def _is_eigen_of_nep(email: str) -> bool:
    """Daniels eigen adressen (elk omnivaleur- of crosslist-domein) en testadressen
    als example.invalid. Gemeten 01-10-2026: zonder dit zaten beide in de lijst."""
    domein = email.rsplit("@", 1)[-1]
    return (domein in _EIGEN_DOMEINEN or "omnivaleur" in domein or "crosslist" in domein
            or domein.endswith((".invalid", ".test", ".example", "example.com", "example.org")))
_LOPENDE_STATUS = {"active", "trialing", "past_due", "unpaid", "incomplete", "payment_processing"}


def collect_light_recipients() -> list[str]:
    """Iedereen die nu GEEN lopend abonnement heeft.

    Anders dan collect_recipients: wie ooit een abonnement had maar opzegde of
    waarvan het stopte (status canceled) hoort er juist wel bij, dat is de groep
    voor wie 19,99 de drempel was. Eruit blijven: wie nu betaalt of een lopend
    abonnement heeft (ook tijdens de proefweek), gratis meegegeven accounts met
    een proef ver in de toekomst, de eigenaar en Daniels eigen adressen."""
    from datetime import datetime, timedelta, timezone

    from backend.config import settings

    db = get_db()
    nu = datetime.now(timezone.utc)
    uitgesloten: set[str] = set()
    for row in db.table("subscriptions").select(
            "user_id,status,stripe_subscription_id,trial_ends_at").execute().data or []:
        if row.get("stripe_subscription_id") and row.get("status") in _LOPENDE_STATUS:
            uitgesloten.add(row["user_id"])
            continue
        eind = row.get("trial_ends_at")
        try:
            eind_dt = datetime.fromisoformat(str(eind).replace("Z", "+00:00")) if eind else None
        except ValueError:
            eind_dt = None
        if row.get("status") == "trialing" and eind_dt and eind_dt > nu + timedelta(days=30):
            uitgesloten.add(row["user_id"])   # meegegeven account, geen klant om te mailen

    eigenaren = {e.strip().lower() for e in (settings.owner_email or "").split(",") if e.strip()}
    emails: list[str] = []
    gezien: set[str] = set()
    page = 1
    while True:
        users = get_admin_db().auth.admin.list_users(page=page, per_page=200)
        if not users:
            break
        for u in users:
            email = (getattr(u, "email", None) or "").strip().lower()
            if (not email or email in gezien or u.id in uitgesloten or email in eigenaren
                    or _is_eigen_of_nep(email)):
                continue
            gezien.add(email)
            emails.append(email)
        if len(users) < 200:
            break
        page += 1
    return emails


def al_verstuurd(emails: list[str]) -> set[str]:
    """Wie deze mail al kreeg. Staat vast in mail_events (bestaande tabel), zodat
    een tweede druk op de knop niemand dubbel mailt."""
    if not emails:
        return set()
    klaar: set[str] = set()
    db = get_admin_db()
    for i in range(0, len(emails), 100):
        rijen = (db.table("mail_events").select("ontvanger").eq("type", LIGHT_MAIL_TYPE)
                 .in_("ontvanger", emails[i:i + 100]).execute().data or [])
        klaar.update((r.get("ontvanger") or "").lower() for r in rijen)
    return klaar


def markeer_verstuurd(email: str, resend_id: str | None = None) -> bool:
    """Legt vast dat deze mail naar dit adres is gegaan. False als dat niet lukte."""
    from datetime import datetime, timezone
    try:
        get_admin_db().table("mail_events").upsert({
            "svix_id": f"light-mail-{email}",
            "email_id": resend_id,
            "type": LIGHT_MAIL_TYPE,
            "ontvanger": email,
            "onderwerp": LIGHT_SUBJECT,
            "gebeurd_op": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception:
        logger.exception("Kon niet vastleggen dat de Light-mail naar %s ging", email)
        return False
