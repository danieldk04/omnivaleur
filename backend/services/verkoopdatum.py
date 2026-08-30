"""
De ECHTE verkoopdatum uitlezen uit wat een platform ons toont.

WAAROM DIT BESTAAT (30-08-2026)
Tot nu toe kreeg elke verkoop de datum waarop wij hem ONTDEKTEN, niet de datum
waarop hij plaatsvond. Bij Vinted ontdekken we verkopen door elke tien minuten
de eigen bestellingenpagina van de verkoper te lezen. Die pagina is een
GESCHIEDENIS: er staan ook bestellingen van weken geleden op. Zolang elke ronde
netjes draait valt dat niet op, maar zodra er een ronde overslaat — de extensie
lag stil, de verkoper was net begonnen, of een verbetering herkende ineens oude
bestellingen die we eerder niet konden koppelen — worden ze in één keer allemaal
geboekt met de klok van dat moment.

Gemeten geval 30-08-2026: twaalf verkopen van Daniel kregen alle twaalf een
tijdstempel tussen 07:36:54 en 07:37:06. Artikelen die in mei en juni waren
geplaatst stonden ineens als "vandaag verkocht" in de omzetgrafiek. De omzet van
weken werd op één dag gestapeld en elke trend werd onbruikbaar.

DE REGEL HIER
Een gegokte datum is erger dan geen datum — dezelfde regel als in
`mp_datums.py`. Herkennen we de datum niet met zekerheid, dan geven we None
terug en verandert er niets. Wat we wél herkennen: het `datetime`-attribuut dat
Vinted in de pagina zet, "vandaag/gisteren", "3 dagen geleden", "17 aug" en de
Engelse varianten daarvan.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

# Hoe ver terug een verkoopdatum nog geloofwaardig is. Alles daarbuiten is geen
# datum maar een leesfout (een artikelnummer dat op een jaartal lijkt, een
# garantietermijn), en die mag nooit als verkoop de boeken in.
MAX_JAREN_TERUG = 5

_MAANDEN = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "mar": 3, "apr": 4, "mei": 5,
    "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "oct": 10,
    "nov": 11, "dec": 12,
}

# Eenheden voor "3 dagen geleden" / "3 days ago", in seconden.
_EENHEDEN = {
    "seconde": 1, "seconden": 1, "sec": 1, "second": 1, "seconds": 1,
    "minuut": 60, "minuten": 60, "min": 60, "minute": 60, "minutes": 60,
    "uur": 3600, "uren": 3600, "hour": 3600, "hours": 3600, "h": 3600,
    "dag": 86400, "dagen": 86400, "day": 86400, "days": 86400,
    "week": 604800, "weken": 604800, "weeks": 604800,
    "maand": 2592000, "maanden": 2592000, "month": 2592000, "months": 2592000,
}


def als_datum(waarde) -> datetime:
    """Een opgeslagen sold_at terug naar een datetime, altijd met tijdzone.

    Onleesbaar geeft "nu" terug: dat is de veiligste kant op. De vergelijkingen
    hieronder zetten een datum alleen terug in de tijd, dus een onleesbare
    bestaande waarde leidt hooguit tot een correctie, nooit tot een sprong
    vooruit.
    """
    if isinstance(waarde, datetime):
        d = waarde
    else:
        rauw = str(waarde or "").replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(rauw)
        except ValueError:
            return datetime.now(timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _nu(nu: datetime | None) -> datetime:
    return (nu or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _van_datum(d: date, nu: datetime) -> datetime | None:
    """Een kale datum wordt middaguv. Nooit in de toekomst, nooit te oud.

    Middag en niet middernacht, zodat een tijdzoneverschil de verkoop niet naar
    de dag ervoor of erna schuift — de grafiek telt per dag.
    """
    if d > nu.date() or d < (nu - timedelta(days=365 * MAX_JAREN_TERUG)).date():
        # Een verkoop in de toekomst bestaat niet, en iets van jaren terug is
        # geen datum maar een leesfout.
        return None
    stempel = datetime.combine(d, time(12, 0), tzinfo=timezone.utc)
    # "Vandaag" om 09:00 mag geen tijdstempel van 12:00 krijgen.
    return min(stempel, nu)


def lees_verkoopdatum(tekst, nu: datetime | None = None) -> datetime | None:
    """De verkoopdatum uit een stukje pagina-tekst of een datum-attribuut.

    Geeft een UTC-datetime terug, of None als er niets met zekerheid in staat.
    None betekent hier altijd: laat de bestaande datum met rust.
    """
    if tekst is None:
        return None
    if isinstance(tekst, datetime):
        d = tekst if tekst.tzinfo else tekst.replace(tzinfo=timezone.utc)
        d = d.astimezone(timezone.utc)
        nu_ = _nu(nu)
        if d > nu_ or d < nu_ - timedelta(days=365 * MAX_JAREN_TERUG):
            return None
        return d
    t = str(tekst).strip()
    if not t:
        return None
    nu_ = _nu(nu)

    # 1. Het datetime-attribuut van een <time>-element: exact, dus als eerste.
    iso = re.search(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?", t)
    if iso:
        rauw = iso.group(0).replace(" ", "T")
        if rauw.endswith("Z"):
            rauw = rauw[:-1] + "+00:00"
        try:
            d = datetime.fromisoformat(rauw)
        except ValueError:
            d = None
        if d is not None:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            d = d.astimezone(timezone.utc)
            if len(iso.group(0)) == 10:  # kale datum → middag
                return _van_datum(d.date(), nu_)
            if d > nu_ or d < nu_ - timedelta(days=365 * MAX_JAREN_TERUG):
                return None
            return d

    laag = t.lower()

    # 2. "vandaag" / "gisteren" / "eergisteren" en de Engelse varianten.
    if re.search(r"\b(vandaag|today)\b", laag):
        return _van_datum(nu_.date(), nu_)
    if re.search(r"\beergisteren\b", laag):
        return _van_datum(nu_.date() - timedelta(days=2), nu_)
    if re.search(r"\b(gisteren|yesterday)\b", laag):
        return _van_datum(nu_.date() - timedelta(days=1), nu_)

    # 3. "3 dagen geleden" / "3 days ago" / "een uur geleden".
    m = re.search(r"\b(\d{1,3}|een|an|a)\s+([a-z]+)\s+(geleden|ago)\b", laag)
    if m:
        aantal = 1 if m.group(1) in ("een", "an", "a") else int(m.group(1))
        stap = _EENHEDEN.get(m.group(2))
        if stap:
            d = nu_ - timedelta(seconds=aantal * stap)
            if d >= nu_ - timedelta(days=365 * MAX_JAREN_TERUG):
                return d
        return None

    # 4. "17 aug", "17 augustus 2026" en de Engelse volgorde "Aug 17, 2026".
    #    Allebei proberen: een eerste treffer die geen maandnaam blijkt te zijn
    #    (bijvoorbeeld "40 - Zeer Goed") mag de andere vorm niet in de weg zitten.
    for patroon, volgorde in (
        (r"\b(\d{1,2})[\s.-]+([a-z]{3,9})\.?(?:[\s,.-]+(\d{2,4}))?\b", "dag-maand"),
        (r"\b([a-z]{3,9})\.?\s+(\d{1,2})(?:[\s,]+(\d{2,4}))?\b", "maand-dag"),
    ):
        for m in re.finditer(patroon, laag):
            dag, naam = (m.group(1), m.group(2)) if volgorde == "dag-maand" else (m.group(2), m.group(1))
            maand = _MAANDEN.get(naam[:3])
            if maand:
                gevonden = _uit_delen(int(dag), maand, m.group(3), nu_)
                if gevonden:
                    return gevonden

    # 5. "17-08-2026" / "17/08/2026" — dag eerst, want dit zijn EU-platforms.
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", laag)
    if m:
        return _uit_delen(int(m.group(1)), int(m.group(2)), m.group(3), nu_)

    return None


def _uit_delen(dag: int, maand: int, jaar: str | None, nu_: datetime) -> datetime | None:
    if not 1 <= maand <= 12:
        return None
    if jaar:
        j = int(jaar)
        j += 2000 if j < 100 else 0
    else:
        # Geen jaartal betekent "dit jaar" — tenzij die datum nog moet komen,
        # dan was het vorig jaar.
        j = nu_.year
    try:
        d = date(j, maand, dag)
    except ValueError:
        return None
    if not jaar and d > nu_.date():
        try:
            d = d.replace(year=j - 1)
        except ValueError:
            return None
    return _van_datum(d, nu_)
