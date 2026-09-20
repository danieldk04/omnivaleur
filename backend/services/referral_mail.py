"""De mails rond het aanbrengen van klanten.

Twee momenten, allebei persoonlijk en allebei van Daniel zelf: er is iemand
binnengekomen via jouw link, en je maand is toegekend. Best-effort: een mail die
niet weggaat mag nooit een beloning tegenhouden.
"""
from __future__ import annotations

import logging

from backend.database import get_admin_db
from backend.services.referral_codes import link_voor

logger = logging.getLogger(__name__)


# ── Mails naar de aanbrenger ─────────────────────────────────────────────────

def email_van(user_id: str) -> str | None:
    """Het adres van een gebruiker. Lukt alleen met de service_role-sleutel; met
    de anon-sleutel geeft Supabase hier "User not allowed" en blijft elke mail
    stil liggen. Zie /health -> supabase_key_role."""
    try:
        gebruiker = get_admin_db().auth.admin.get_user_by_id(user_id)
        return gebruiker.user.email if gebruiker and gebruiker.user else None
    except Exception as e:
        logger.error("Adres van %s niet op te vragen (%s). Draait de server op de "
                     "service_role-sleutel?", user_id, e)
        return None


def maskeer(email: str | None) -> str:
    """Genoeg om te herkennen wie het is, niet genoeg om het adres door te geven.
    Het blijft het adres van iemand anders."""
    if not email or "@" not in email:
        return "someone"
    naam, domein = email.split("@", 1)
    return f"{naam[:1]}{'*' * max(3, len(naam) - 1)}@{domein}"


def mail_aanmelding(referrer_user_id: str, vriend_email: str | None, code: str) -> bool:
    adres = email_van(referrer_user_id)
    if not adres:
        return False
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    onderwerp = "Someone just signed up with your link"
    tekst = f"""Hi there,

Daniel here, founder of Omnivaleur.

Someone just started a free trial through your invite link ({maskeer(vriend_email)}).

Your free month is not in yet. It lands the moment they become a paying
customer, and you will get an email from me when that happens. There is nothing
you need to do in the meantime.

Want to invite more people? This is your personal link:

  {link_voor(code)}

Every friend who subscribes gives you another month free, and they pay half
price for their first month.

Thanks for spreading the word,
Daniel
Omnivaleur
{CONTACT_EMAIL}
"""
    return bool(send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL))


def mail_beloning(referrer_user_id: str, manier: str, uitleg: str) -> bool:
    adres = email_van(referrer_user_id)
    if not adres:
        return False
    from backend.services.billing import CONTACT_EMAIL
    from backend.services.email import send_email

    if manier == "tegoed":
        wat = ("We put one month of credit on your account. Stripe takes it off your\n"
               "next invoice automatically, so your next payment is zero. You do not\n"
               "have to enter anything.")
    elif manier in ("stripe_proef", "proef_verlengd"):
        wat = (f"We added a month to your account. {uitleg}, so your next payment moves\n"
               "back by a month.")
    else:
        wat = "We added a month to your account."

    onderwerp = "Your free month is in"
    tekst = f"""Hi there,

Daniel here.

Someone you invited just became a paying Omnivaleur customer. That means you
earned a month free.

{wat}

Thank you. Word of mouth from people who actually use this is worth more to me
than any advertisement, and I would rather pay it back to you than to Google.

There is no limit: every friend who subscribes is another month free.

Daniel
Omnivaleur
{CONTACT_EMAIL}
"""
    return bool(send_email(subject=onderwerp, body=tekst, to=adres, reply_to=CONTACT_EMAIL))


def mail_beloning_mislukt(aanbrenger: str, aangebrachte: str, reden: str) -> bool:
    """Alarm naar Daniel zelf. Niet naar de klant: die hoort pas iets als zijn
    maand er echt is, niet dat er iets kapot is aan onze kant."""
    from backend.config import settings
    from backend.services.email import send_email

    onderwerp = "Verwijzing: een gratis maand is niet toegekend"
    tekst = f"""Een klant heeft iemand aangebracht die is gaan betalen, maar de gratis
maand is na meerdere pogingen niet toegekend.

Aanbrenger:   {aanbrenger} ({email_van(aanbrenger) or 'adres onbekend'})
Aangebrachte: {aangebrachte}
Laatste fout: {reden}

Wat er nu NIET gebeurt: de herstelronde probeert het niet meer. De rij staat in
referral_rewards op 'failed'. Zet hem op 'pending' met attempts op 0 zodra de
oorzaak weg is, dan pakt de ronde van het volgende uur hem alsnog op.

Deze mail komt één keer per beloning.
"""
    adres = settings.owner_email
    return bool(send_email(subject=onderwerp, body=tekst, to=adres))
