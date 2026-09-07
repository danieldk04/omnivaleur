"""
Eenmalige terughaalcampagne: oud-klanten die zijn afgehaakt of nooit begonnen,
opnieuw uitnodigen nu de grootste storingen weg zijn.

Bewust een apart bestand met de teksten erin, net als bij announcement.py: de mail
gaat naar echte mensen in Daniels naam, dus hij moet leesbaar in de code staan en
niet in elkaar gezet worden uit losse regels.

Drie groepen (besluit 2, docs/team-notes.md 06-09-2026):
  A  probeerde het serieus, liep vast, vertrok      -> persoonlijk, eigen cijfer, excuus
  B  op dag een ging alles mis, nooit teruggekomen  -> "55 procent naar 7 procent"-verhaal
  C  meldde zich aan, deed nul opdrachten           -> lichte vraag, geen excuus

De campagne richt zich eerst op sieraden + antiek zilver (bewijscategorie); dat is
een keuze over WIE op de lijst komt, niet iets wat deze code afdwingt. De lijst
wordt met de hand aangeleverd.

Proefverlenging kan niet vanuit deze code: de server draait op de publieke
Supabase-sleutel en mag geen klantrijen schrijven. Elke mail belooft een verlengde
proef, dus Daniel zet die met de hand in het Supabase-dashboard (of per persoon via
/admin/comp-account) voordat hij op echt verstuurt. De proefronde herinnert daaraan.
"""
import logging

logger = logging.getLogger(__name__)

# Geen kortingspercentage, euroteken of uitroepteken in de onderwerpregel: daar
# sorteert Gmail op, en dan belandt de mail in Promoties in plaats van de inbox.
SUBJECT_A = "Het lag aan ons, van Daniel"
SUBJECT_B = "Omnivaleur werkt nu wel, van Daniel"
SUBJECT_C = "Zal ik even met je meekijken? Van Daniel"

# In groep A komt de zin over wat er bij die persoon misging op {detail}. Lever je
# geen eigen zin aan, dan valt hij terug op deze neutrale formulering.
DETAIL_FALLBACK = (
    "een deel van je publicaties liep vast op een valse melding \"je bent niet "
    "ingelogd bij Marktplaats\", en er is weinig tot niets geplaatst"
)

BODY_A = """Hi,

Daniel hier, van Omnivaleur.

Toen jij het probeerde, werkte het niet. Bij jou specifiek: {detail}. Dat was geen instelling aan jouw kant, dat lag aan ons.

Die valse inlogmelding is opgespoord en gerepareerd. Het mislukkingspercentage over alle klanten is deze week 7 procent, van 55 procent een maand terug. Ik verkoop zelf kleding en sieraden en loop er zelden meer tegenaan.

Ik wil je vragen het nog een keer te proberen, met een verlengde proefperiode zodat het je niks kost. Antwoord op deze mail als je wilt dat ik meekijk terwijl je je eerste tien advertenties doet.

Daniel van Omnivaleur
"""

BODY_B = """Hi,

Daniel hier, van Omnivaleur.

Jij hebt het product nooit een keer zien werken. Op de dag dat je je aanmeldde ging vrijwel elke publicatie mis, en daarna heb je het niet meer geopend. Logisch.

Sindsdien is er veel gerepareerd: de gekoppelde verwijdering, lege velden, de valse melding dat je niet was ingelogd. Deze week mislukt 7 procent van de opdrachten, tegen 55 procent toen jij het probeerde.

Je proefperiode staat weer open, verlengd, zodat je rustig opnieuw kunt kijken. Werkt iets niet, antwoord dan op deze mail, die komt bij mij.

Daniel van Omnivaleur
"""

BODY_C = """Hi,

Daniel hier, van Omnivaleur.

Je hebt een account aangemaakt maar bent nooit begonnen. Geen verwijt, het eerste zetje is het lastigste, zeker met een grote voorraad.

Heb je behoefte om even hier samen naar te kijken? Daarna weet je of het bij jou past. Je proefperiode is verlengd zodat je de tijd hebt.

Antwoord op deze mail met een dag en tijd die je schikt.

Daniel van Omnivaleur
"""

GROEPEN = {
    "A": {"subject": SUBJECT_A, "body": BODY_A, "heeft_detail": True},
    "B": {"subject": SUBJECT_B, "body": BODY_B, "heeft_detail": False},
    "C": {"subject": SUBJECT_C, "body": BODY_C, "heeft_detail": False},
}


def parse_ontvangers(raw: str) -> list[dict]:
    """Adressen uit een geplakte lijst halen. Per regel een adres; voor groep A mag
    er een eigen zin achter met een liggend streepje ervoor:

        henk@voorbeeld.nl | 14 van je 18 publicaties liepen vast, niets geplaatst
        anna@voorbeeld.be

    Regels zonder @ vallen af (kolomkop, datum). Dubbele adressen eruit, eerste
    wint. Retour: [{"email": ..., "detail": ... of None}, ...].
    """
    import re

    seen: set[str] = set()
    out: list[dict] = []
    for regel in raw.splitlines():
        for stuk in re.split(r"[,;]+", regel):
            deel = stuk.strip()
            if not deel:
                continue
            detail = None
            if "|" in deel:
                adres, _, rest = deel.partition("|")
                detail = rest.strip() or None
                deel = adres.strip()
            email = deel.strip().strip('"\'<>()').lower()
            if "@" not in email or "." not in email.split("@")[-1]:
                continue
            if email in seen:
                continue
            seen.add(email)
            out.append({"email": email, "detail": detail})
    return out


def render(groep: str, ontvanger: dict) -> tuple[str, str]:
    """(onderwerp, tekst) voor een ontvanger. Groep A vult de eigen zin in."""
    g = GROEPEN[groep]
    body = g["body"]
    if g["heeft_detail"]:
        body = body.replace("{detail}", ontvanger.get("detail") or DETAIL_FALLBACK)
    return g["subject"], body
