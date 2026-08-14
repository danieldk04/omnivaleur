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
