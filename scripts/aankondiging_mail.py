"""Aankondigingsmails 20-11-2026 aan klanten en mensen in proef (opdracht Daniel).

Eenmalig. Vanaf daniel@omnivaleur.nl via Zoho (dezelfde route als zijn eigen mail,
SPF en DKIM kloppen), platte tekst, een mail per adres, rustig tempo.
  PY scripts/aankondiging_mail.py lijst                 wie krijgt wat (verstuurt niets)
  PY scripts/aankondiging_mail.py test                  alle varianten naar daniel@omnivaleur.nl
  PY scripts/aankondiging_mail.py stuur --echt          echt versturen, nooit dubbel (mail_events)
Ontvangers: betalende klanten, gratis meegegeven accounts, mensen in proef en nieuwe
aanmelders zonder abonnementsrij. NIET: verlopen proeven, opgezegden, eigen adressen.
De vier grote accounts krijgen mail A en een persoonlijke mail in plaats van mail B.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import onboarding_mail as O  # noqa: E402
from backend.config import settings  # noqa: E402
from backend.database import get_admin_db, get_db  # noqa: E402
from backend.services.announcement import _is_eigen_of_nep  # noqa: E402

EIGEN = {"dkresellacademy@gmail.com", "aertssen.pleun@gmail.com", "daniel@omnivaleur.nl",
         "danieldekoning04@gmail.com"}
GROOT = {"info@papas-plectrums.nl": "5.700", "info@goudlief.nl": "4.200",
         "info@zilverwebsite.nl": "2.900", "jannekeheijne1988@hotmail.com": "3.500"}
# Wie ooit zei geen mail meer te willen (mailbox nagelopen 20-11: zoekwoorden stop, afmelden,
# unsubscribe, geen mail, uitschrijven, geen interesse; en alle antwoorden van de ontvangers zelf).
# Voeg hier elk nieuw adres aan toe. Daarnaast blokkeert de code wie bij Resend of Zoho
# een bounce of spamklacht gaf (mail_events).
GEEN_MAIL = {"info@frankvannuus.nl", "studioriccamente@gmail.com"}
STATUS_OK = {"active", "trialing", "complimentary", "payment_processing", "past_due", None}

A_ONDERWERP = "Een vriend uitnodigen levert je nu geld op"
A = """Hoi,

Daniel hier. Tot 1 januari geef ik meer terug aan wie een andere verkoper meeneemt.

Elke vriend die een betaald abonnement neemt (vanaf Pro) haalt €10 per maand van je eigen rekening, zolang hij betaalt. Elke vriend levert je daarnaast 2 maanden gratis op. Bij 3 vrienden krijg je het AI-pakket, elke AI-functie zodra die live gaat. Bij 5 vrienden heb je Ultra: alle functies, Etsy zodra die er is, de nieuwste functies eerst en voorrang bij support.

Je vriend start met 14 dagen proef, betaalt de eerste maand de helft, en ik lees zijn voorraad in en loop de eerste artikelen met hem na tot ze online staan.

Je persoonlijke link staat in je dashboard onder Vrienden uitnodigen. Wie voor 1 januari begint houdt de €10 ook daarna.

Groetjes,

Daniel"""

B_ONDERWERP = "Wat er per 1 januari verandert in je abonnement"
B = """Hoi,

Daniel hier. Per 1 januari rekent Omnivaleur niet meer op alles of niets, maar op het aantal actieve artikelen per factuur.

Light: tot 20 artikelen, €9,99 per maand incl. btw. Pro: tot 250, €19,99. Plus: tot 1.500, €29,99. Ultra: onbeperkt, €49, met Etsy zodra die er is, de nieuwste functies eerst, het AI-pakket en voorrang bij support. Kies je jaarlijks, dan betaal je 10 maanden in plaats van 12.

Zo werkt het in de praktijk. We tellen je actieve artikelen en je zit in het plan dat daarbij past. Heb je bijvoorbeeld 180 actieve artikelen, dan blijf je op Pro voor €19,99 en verandert er niets. Heb je 600, dan is Plus het plan voor €29,99. Heb je er meer dan 1.500, dan is Ultra het plan voor €49. Zit je nu al zo hoog, dan mail ik je apart over een rustige overgang. Heb je maximaal 20 artikelen, dan kun je overstappen naar Light voor €9,99.

Zit je een keer boven je grens, dan kun je gewoon doorwerken met wat er staat. Alleen nieuwe artikelen worden dan pas geblokkeerd, en de grenzen van Pro en Plus gaan pas op 15 januari gelden, zodat je rustig kunt kiezen. Bij upgraden betaal je alleen het verschil.

Nodig je daarnaast vrienden uit, dan kan je plan goedkoper worden of zelfs gratis: elke betalende vriend haalt tot 1 januari €10 per maand van je factuur, en met 5 vrienden heb je Ultra. Je link staat in je dashboard onder Vrienden uitnodigen.

Vragen? Reageer gewoon op deze mail.

Groetjes,

Daniel"""

G_ONDERWERP = "Je plan per 1 januari"
G = """Hoi,

Daniel hier. Per 1 januari rekent Omnivaleur op het aantal actieve artikelen per factuur. Je hebt er nu ongeveer {n} actief, dus Ultra is het plan voor jou: onbeperkt artikelen, Etsy zodra die er is, de nieuwste functies eerst, het AI-pakket en voorrang bij support. Ultra kost normaal €49 per maand.

Je betaalt nu €19,99, dus ik maak het stap voor stap: €29,99 per maand van 1 januari tot en met maart, €39 van april tot en met juni, en daarna €49. Kies je jaarlijks, dan krijg je 2 maanden gratis.

Daarnaast haalt elke betalende vriend die je uitnodigt tot 1 januari €10 per maand van je factuur, en met 5 vrienden heb je Ultra. Je link staat in je dashboard onder Vrienden uitnodigen.

Vragen? Reageer gewoon op deze mail.

Groetjes,

Daniel"""

# Engelse versies voor wie geen Nederlands leest (opdracht Daniel 20-11). Regel: .nl of .be,
# of verkoop op Marktplaats of 2dehands, of een bekende Nederlandse klant = Nederlands.
# De rest hierboven niet herkend = Engels. Taal staat nergens op de server, dus de lijst is handwerk.
ENGELS = {"info@janinanoetzel.com", "momme@nordsonne.net", "theholsiticface@gmail.com", "hbm789@icloud.com"}

A_ONDERWERP_EN = "Inviting a friend now earns you money"
A_EN = """Hi,

Daniel here. Until 1 January I give more back to anyone who brings another seller along.

Every friend who takes a paid subscription (Pro or higher) takes €10 per month off your own invoice, for as long as they keep paying. Every friend also gives you 2 free months. With 3 friends you get the AI package, every AI function as soon as it goes live. With 5 friends you have Ultra: all features, Etsy as soon as it is available, the newest features first and priority support.

Your friend starts with a 14 day trial and pays half for the first month. I import their stock and walk through the first items with them until they are online.

Your personal link is in your dashboard under Invite friends. Anyone who joins before 1 January keeps the €10 afterwards.

Best,

Daniel"""

B_ONDERWERP_EN = "What changes in your subscription on 1 January"
B_EN = """Hi,

Daniel here. From 1 January, Omnivaleur no longer charges all or nothing, but by the number of active items per invoice.

Light: up to 20 items, €9.99 per month incl. VAT. Pro: up to 250, €19.99. Plus: up to 1,500, €29.99. Ultra: unlimited, €49, with Etsy as soon as it is available, the newest features first, the AI package and priority support. Pay yearly and you pay 10 months instead of 12.

In practice it works like this. We count your active items and you are in the plan that fits. If you have 180 active items, you stay on Pro for €19.99 and nothing changes. With 600, Plus is the plan for €29.99. With more than 1,500, Ultra is the plan for €49. If you are already that high, I will email you separately about a gentle transition. With 20 items or fewer you can switch to Light for €9.99.

If you go over your limit, you can keep working with what is online. Only new items are blocked, and the limits of Pro and Plus only apply from 15 January, so you have time to choose. When you upgrade you only pay the difference.

If you also invite friends, your plan can get cheaper or even free: until 1 January every paying friend takes €10 per month off your invoice, and with 5 friends you have Ultra. Your link is in your dashboard under Invite friends.

Questions? Just reply to this email.

Best,

Daniel"""


def ontvangers():
    eig = {e.strip().lower() for e in (settings.owner_email or "").split(",") if e.strip()} | EIGEN
    subs = {r["user_id"]: r.get("status") for r in
            get_db().table("subscriptions").select("user_id,status").execute().data or []}
    uit, page = [], 1
    while True:
        us = get_admin_db().auth.admin.list_users(page=page, per_page=200)
        if not us:
            break
        for u in us:
            e = (u.email or "").strip().lower()
            if e and e not in eig and e not in GEEN_MAIL and not _is_eigen_of_nep(e) and subs.get(u.id) in STATUS_OK:
                uit.append(e)
        if len(us) < 200:
            break
        page += 1
    return sorted(set(uit))


def plan(adres):
    if adres in GROOT:
        return [("a", A_ONDERWERP, A), ("groot", G_ONDERWERP, G.format(n=GROOT[adres]))]
    if adres in ENGELS:
        return [("a", A_ONDERWERP_EN, A_EN), ("b", B_ONDERWERP_EN, B_EN)]
    return [("a", A_ONDERWERP, A), ("b", B_ONDERWERP, B)]


def geblokkeerd(adres):
    """Bounce of spamklacht eerder gelogd: dan niet nog eens mailen."""
    r = get_admin_db().table("mail_events").select("type").eq("ontvanger", adres).in_(
        "type", ["email.bounced", "email.complained", "email.suppressed"]).execute().data
    return bool(r)


def al(adres, soort):
    r = get_admin_db().table("mail_events").select("svix_id").eq("svix_id", f"aankondiging-{soort}-{adres}").execute().data
    return bool(r)


def noteer(adres, soort, onderwerp):
    get_admin_db().table("mail_events").upsert({
        "svix_id": f"aankondiging-{soort}-{adres}", "type": f"omnivaleur.aankondiging_{soort}",
        "ontvanger": adres, "onderwerp": onderwerp,
        "gebeurd_op": datetime.now(timezone.utc).isoformat()}).execute()


def main(a):
    cmd = a[0] if a else "lijst"
    lijst = ontvangers()
    if cmd == "lijst":
        for e in lijst:
            print(e, [s for s, _, _ in plan(e)])
        print(len(lijst), "ontvangers")
        return
    if cmd == "test":
        for soort, onderwerp, tekst in (plan("info@goudlief.nl") + plan("x@y.nl")[1:]):
            O._verstuur(O.bericht("daniel@omnivaleur.nl", "[TEST] " + onderwerp, tekst, "test-" + soort))
            print("test", soort)
        return
    if cmd == "stuur" and "--echt" in a:
        for e in lijst:
            for soort, onderwerp, tekst in plan(e):
                if geblokkeerd(e):
                    print("GEBLOKKEERD (bounce of klacht)", e)
                    break
                if al(e, soort):
                    print("al gehad", e, soort)
                    continue
                O._verstuur(O.bericht(e, onderwerp, tekst, "aankondiging-" + soort))
                noteer(e, soort, onderwerp)
                print("verstuurd", e, soort, flush=True)
                time.sleep(25)
        return
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
