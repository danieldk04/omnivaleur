#!/usr/bin/env python3
"""
Koude mail versturen naar de leads uit de trechter, met opvolging.

WAAROM DIT IN HET SCRIPT ZIT EN NIET IN EEN TOOL
Alles wat een mailtool bijhoudt — wie is gemaild, wie heeft geantwoord, wie krijgt
de volgende opvolger — hangt aan de lead, en die staat hier al. In Make of Instantly
moet je dat allemaal naast je leadbestand nabouwen en synchroon houden. Dit kost
niets extra's en kan niet uit de pas lopen.

NOOIT VANAF HET PRODUCTDOMEIN
Verstuur dit niet vanaf omnivaleur.com. Daar draait de app op, daar komen de
eBay-webhooks binnen en daarvandaan gaan de wachtwoord- en factuurmails via Resend.
Resend verbiedt koude acquisitie bovendien met zoveel woorden en sluit accounts
zonder waarschuwing — dan ligt het product plat. Gebruik een apart domein met een
eigen postbus (Zoho Mail Lite, ~€11 per jaar).

WAT DIT WEL EN NIET DOET
  wel   opbouwen in tempo, per lead personaliseren, twee opvolgmails, stoppen zodra
        iemand antwoordt of zich afmeldt, bounces herkennen, alles bijhouden
  niet  opwarmen met kunstmatig verkeer. Dat doen die netwerken onderling en het
        voorspelt niets over hoe Gmail jouw mail aan een vreemde behandelt. Het
        tempo hieronder ís de opwarming.

Gebruik:
    export MAIL_HOST=smtp.zoho.eu MAIL_USER=daniel@... MAIL_PASS=...
    export IMAP_HOST=imap.zoho.eu

    python3 scripts/leadgen_mail.py plan                  # wie is vandaag aan de beurt
    python3 scripts/leadgen_mail.py send --dry-run        # tonen, niet versturen
    python3 scripts/leadgen_mail.py send                  # echt versturen
    python3 scripts/leadgen_mail.py check                 # antwoorden en bounces ophalen
    python3 scripts/leadgen_mail.py status                # hoe staat het ervoor
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import random
import re
import smtplib
import ssl
import sys
import textwrap
import time
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr, parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent / "output" / "leads"
MP_LEADS = OUT / "mp_leads.json"
IG_LEADS = OUT / "leads.json"
STATE = OUT / "mail_state.json"
PLAN = OUT / "mail_plan.json"

# ---------------------------------------------------------------------------
# VUL DIT IN VOORDAT JE VERSTUURT.
# Zakelijke mail zonder herleidbare afzender en zonder afmeldmogelijkheid mag niet,
# en filters straffen het bovendien af. Het script weigert te versturen zolang hier
# nog een placeholder staat.
AFZENDER_NAAM = "Daniel de Koning"
BEDRIJF = "Omnivaleur"
BEDRIJF_ADRES = "Kleine Melanen 5, 4614RG, Bergen op Zoom"
BEDRIJF_KVK = "86792423"
SITE = "https://omnivaleur.com"
# Waar Daniel een seintje krijgt zodra iemand écht antwoordt. Automatische
# ontvangstbevestigingen tellen niet mee, anders is het geen seintje meer maar ruis.
ALARM_NAAR = ["danieldekoning66@gmail.com", "info@revaleur.com"]
# De demo van één minuut. Staat hier één keer, zodat er nooit een oude link in
# een concept belandt.
VIDEO = "https://youtube.com/shorts/ymDeS37aBW4"
PRIJS = "€19,99 per maand"
PLATFORMS = "Marktplaats, 2dehands, Vinted, eBay en Shopify. Etsy komt eraan"
# Waar een klaargezet antwoord terechtkomt. Zoho noemt zijn conceptenmap zo.
CONCEPTMAP = "Concept"
# Van elk seintje komt ook een kopie in deze Zoho-map. Daniels postvak IN moet
# alleen échte reacties van handelaren bevatten; berichten van de machine zelf
# horen daar niet tussen te staan.
ALARM_MAP = "Reactie-Notificaties"
# Indeling van het postvak. Bewust maar drie mappen: alles wat in POSTVAK IN
# blijft staan is een echte reactie waar Daniel nog iets mee moet. Meer mappen
# betekent meer plekken om iets over het hoofd te zien.
MAP_AUTOMATISCH = "Automatisch"   # ontvangstbevestigingen, bounces, systeemmail
MAP_BEANTWOORD = "Beantwoord"     # reacties waar Daniel al op heeft geantwoord
SYSTEEM_AFZENDER = re.compile(
    r"@(zoho\.(eu|com)|google\.com)$|dmarc|mailer-daemon|postmaster|no-?reply", re.I)
# ---------------------------------------------------------------------------

# Opbouwschema: het aantal mails per dag, geteld vanaf je eerste verzenddag. Een
# nieuw domein dat op dag één honderd mails uitstuurt is een nieuw domein dat op
# dag twee op een zwarte lijst staat. Daniel wil vanaf dag twee 15 per dag en
# daarna verder opbouwen: 25 vanaf dag 6, 40 vanaf dag 11. Hoger heeft geen zin
# zolang de lijst ~320 adressen telt; die is dan in twee weken op.
#
# VENSTER en SPREIDING horen bij de autonome stand (`tick`): de mails van een dag
# krijgen willekeurige tijdstippen binnen kantoortijd, in plaats van vijftien
# stuks achter elkaar om negen uur 's ochtends.
RAMP = [(1, 5), (2, 15), (6, 25), (11, 30)]
# Hoeveel van het dagbudget gereserveerd blijft voor NIEUWE eerste mails.
# Opvolgmails gaan voor, en met het ritme van 2 en 4 dagen komen die in golven —
# op 15-08 waren 12 van de 15 mails opvolging en werd er die dag vrijwel niemand
# nieuw aangeschreven. Zonder deze reservering staat het aanboren van nieuwe
# leads stil zodra er een golf loopt.
NIEUW_AANDEEL = 0.4
FOLLOWUP_DAGEN = (2, 4)       # opvolgmail 1 en 2, in dagen na de vorige mail
# Hoeveel dagen na de laatste opvolgmail een lead als doodgelopen geldt. Daarna
# schuift hij in Notion naar de eindfase, zodat de lijst laat zien wie er nog
# leeft in plaats van alleen wie ooit gemaild is.
STIL_NA_DAGEN = 10
# De fase voor "crosslist al, maar met een concurrent". Moet exact zo in de
# Leadlist bestaan, anders wordt de kolom stil overgeslagen.
FASE_CONCURRENT = "Gebruikt concurrent"
# De twee fases die samen Daniels werkvoorraad vormen. Alles wat hierbuiten
# valt is administratie; deze twee zijn de enige lijsten die hij hoeft te openen.
FASE_AAN_ZET = "⚡ Jij bent aan zet"
FASE_BAL_BIJ_HEN = "⏳ Bal bij hen"
PAUZE = (40, 110)             # seconden tussen twee mails, willekeurig
VENSTER = (8, 45), (20, 30)   # vroegste en laatste verzendtijd op een dag
MIN_GAT = 9                   # minuten die minimaal tussen twee tijdstippen zitten

# Alleen een écht verzoek om van de lijst af te gaan. "Geen interesse" stond hier
# ook in, en dat brak de indeling: iemand die schreef "wij gebruiken al Channable,
# dus geen interesse" werd geboekt als afmelding, waardoor het belangrijkste deel
# van dat antwoord — dát ze al crosslisten — verloren ging. Een nee is nu een nee
# (zie AFWIJZING) en een afmelding is een afmelding. Beide stoppen het mailen,
# dus dit kan niemand extra post opleveren.
# ── Afsluitmailtjes ────────────────────────────────────────────────────────
# Iemand die de moeite neemt om te antwoorden verdient een antwoord terug, ook —
# júist — als het een nee is. Twee zinnen, geen verkooppoging, deur open laten.
# Dat is gewoon fatsoen, en het is bovendien het enige moment waarop je iemand
# een goed gevoel kunt geven over een mail die hij niet gevraagd had.
#
# VIER REGELS, en alle vier hebben een reden:
#  1. NOOIT naar iemand die zich afmeldt. Die vroeg om stilte; nog een mailtje is
#     precies wat hij níét wilde, en wettelijk het enige dat echt niet mag.
#  2. NOOIT naar een automatisch antwoord. Dan mail je met een robot.
#  3. Hooguit één keer per bedrijf, ooit.
#  4. NIET meteen. Binnen tien seconden terugschrijven is het duidelijkste teken
#     dat er geen mens meezit. Twintig tot negentig minuten leest als "ik zag je
#     mailtje en heb er even op gereageerd".
#
# Meerdere varianten, willekeurig gekozen: twee handelaren die elkaar spreken
# horen niet exact dezelfde zin te hebben gekregen.
# UIT op Daniels verzoek (17-08-2026): hij ziet elke reactie zelf al op zijn
# telefoon en wil niet dat er per ongeluk twee bedankjes uitgaan — het zijne en
# dat van de machine. De teksten blijven staan; op False gaat het weer aan.
AFSLUIT_UIT = True

AFSLUIT_VERTRAGING = (20, 90)          # minuten

AFSLUIT_CONCURRENT = [
    """Bedankt voor de snelle reactie! Helder dat het doorzetten naar Marktplaats
al goed geregeld is.

Mocht {je} in de toekomst willen uitbreiden naar Vinted of eBay, dan weet {je} me
te vinden. Succes met de verkoop!""",
    """Dank voor het laten weten, en fijn dat het al draait.

Als er ooit een platform bijkomt waar {je} nog niet op zit, hoor ik het graag.
Verder veel succes met de winkel!""",
    """Helder, dank {je} wel. Dan laat ik {je} met rust.

Loopt {je} ooit tegen een platform aan waar het overzetten wél handwerk is, stuur
dan gerust een berichtje. Succes!""",
]

AFSLUIT_AFWIJZING = [
    """Bedankt voor het eerlijke antwoord, daar heb ik meer aan dan aan stilte.

Ik laat {je} verder met rust. Mocht het ooit veranderen, dan weet {je} me te
vinden. Succes met de verkoop!""",
    """Duidelijk, dank {je} wel voor de moeite van het reageren.

Dan haal ik {je} van mijn lijstje. Veel succes met de winkel!""",
    """Helder, en bedankt voor je reactie.

Ik val {je} niet verder lastig. Verandert het ooit, dan hoor ik het graag —
succes ondertussen!""",
]


AFMELD_WOORDEN = re.compile(
    r"\b(stop|afmelden|uitschrijven|unsubscribe|opt.?out"
    # "niet meer mailen" ving "niet meer TE mailen" niet, en zo schreef iemand het
    # nu juist. Een gemiste afmelding is de duurste fout die hier bestaat.
    r"|niet meer (te )?(mail|benader|schrijf|contacteer|lastigval)\w*"
    r"|verwijder(en)? (mij|me|ons)|haal (mij|me|ons) van)\b", re.I)
# Een nette afwijzing is geen afmelding. "Wij gebruiken al iets" of "hier doen we
# niets mee" is een antwoord, en zonder dit onderscheid landde zo iemand in Notion
# op Interesse — precies naast de mensen die wél wilden. Alleen op de eerste
# regels toegepast, want verderop in een citaat staat onze eigen mail.
AFWIJZING = re.compile(
    r"(geen (interesse|behoefte|belangstelling)"
    r"|niet ge(i|ï)nteresseerd"
    r"|(hier|daar) doen we (niets|niks) mee"
    r"|(is|lijkt) (het |ons )?niet(s)? (voor ons|wat wij zoeken|interessant)"
    r"|no,? thank(s| you)|not interested|we're all set)", re.I)

# "We gebruiken al Channable" is géén nee. Het is de beste soort nee die er is:
# deze handelaar crosslist al, ziet er de waarde van in en betaalt er al voor.
# Hij zit alleen vast aan iemand anders. Zet je hem bij "geen interesse", dan
# verdwijnt precies de groep die het makkelijkst klant wordt zodra die tool te
# duur of te omslachtig wordt. Daarom een eigen fase, apart te filteren.
#
# De namen hieronder zijn de tools die deze doelgroep echt gebruikt; de losse
# zinnen vangen de rest. Blijft het bij een vage "we hebben al iets", dan telt
# dat ook hier — dat is nog steeds "bezet", niet "niet geïnteresseerd".
CONCURRENT = re.compile(
    # Namen van de tools die deze doelgroep echt gebruikt.
    r"\b(channable|channabel|lengow|channelengine|effectconnect|productflow"
    r"|shoppingfeed|shopping ?feed|goedgepickt|itsperfect|picqer|storekeeper"
    r"|admarkt|mijnwebwinkel|lightspeed|ccvshop)\b"
    r"|we (gebruiken|hebben|werken met) al (een|iets|zo'?n|de|het)"
    r"|(gebruiken|hebben) hier al een (tool|systeem|programma|koppeling)"
    r"|(zit|zitten) al bij (een|een andere)"
    r"|we (already )?(use|have) (a|another)|already using"
    # ── En dit is hoe verkopers het in de praktijk opschrijven ──────────────
    # Vrijwel niemand noemt zijn tool bij naam; ze zeggen "het gaat al vanzelf".
    # Deze drie echte antwoorden werden gemist en belandden als "warm" in de
    # lijst: "Alles wordt al automatisch op marktplaats geplaats" (let op de
    # typefout), "heb een programma dat al mijn advertenties automatisch
    # doorplaatst" en "al onze artikelen gaan al automatisch naar mp toe".
    r"|\bautomatisch\b.{0,60}\b(geplaats|doorplaats|doorgeplaats|gezet|verstuur|naar)"
    r"|\b(gaat|gaan|wordt|worden|loopt|lopen)\b.{0,30}\bal (automatisch|vanzelf)"
    r"|\bal (automatisch|vanzelf|geautomatiseerd)\b"
    r"|\b(heb|hebben|via|met) (een|mijn|onze|ons) (eigen )?(programma|feed|koppeling|script|systeem)"
    r"|\beigen (feed|koppeling|systeem|programma)\b"
    r"|\bfeed\b.{0,30}\b(naar|richting)\b", re.I)
BOUNCE_AFZENDERS = re.compile(r"mailer-daemon|postmaster|no-?reply", re.I)
# Een automatisch antwoord is geen antwoord. Zou je het wel zo tellen, dan valt
# iemand die "ik ben op vakantie" terugstuurt uit de opvolging en hoor je nooit
# meer iets van hem.
AUTO_ONDERWERP = re.compile(
    r"^(automatisch antwoord|auto(matic)? reply|out of office|afwezig"
    r"|ontvangstbevestiging|bedankt voor je (bericht|mail))", re.I)
# Niet elke ontvangstbevestiging verraadt zich in de onderwerpregel: BoekenBalie
# stuurde er een terug onder ons eigen onderwerp. Deze zinnen in de aanhef zijn
# het tweede vangnet.
# Let op: "bedankt voor je e-mail" staat hier BEWUST NIET in. Alfons van CD Dealer
# begon zijn echte antwoord met "Bedankt voor je berichtje" en vroeg vervolgens om
# de video en de prijzen — die werd zo als automaat weggezet en is een dag blijven
# liggen. Een automaat verraadt zich aan wat hij bélooft (een termijn, "in goede
# orde ontvangen"), niet aan een bedankje. Liever een automaat te veel doorlaten
# dan één warme reactie missen.
AUTO_TEKST = re.compile(
    r"(in goede orde ontvangen"
    r"|we (hebben|nemen) .{0,40}(ontvangen|contact met je op) binnen"
    r"|reageren wij op dit moment"
    r"|binnen \d+ (werk)?dagen (beantwoord|contact|reactie)"
    r"|dit is een automatisch"
    r"|\bout of office\b|\bafwezigheidsmelding\b)", re.I)


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


# ---------------------------------------------------------------- opslag
# De machine moet ook draaien als Daniels Mac uit staat. Dan draait hij in de
# cloud (GitHub Actions) en is er geen schijf die iets onthoudt tussen twee
# beurten. Staan SUPABASE_URL en SUPABASE_KEY in de omgeving, dan gaan de
# leadlijst, de administratie en het dagrooster naar Supabase in plaats van naar
# bestanden. Zonder die twee blijft alles precies werken zoals het lokaal deed.
#
# De leadlijst hoort NIET in de git-repo: die is publiek, en het zijn de
# e-mailadressen van 300 bedrijven.
TABEL = "leadgen_opslag"


def _supabase() -> tuple[str, str] | None:
    url, sleutel = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    return (url.rstrip("/"), sleutel) if url and sleutel else None


def _db_lees(naam: str, standaard):
    verbinding = _supabase()
    if not verbinding:
        return None
    import httpx
    url, sleutel = verbinding
    r = httpx.get(f"{url}/rest/v1/{TABEL}", params={"naam": f"eq.{naam}",
                                                    "select": "inhoud"},
                  headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}"},
                  timeout=30.0)
    r.raise_for_status()
    rijen = r.json()
    return rijen[0]["inhoud"] if rijen else standaard


def _db_schrijf(naam: str, inhoud) -> bool:
    verbinding = _supabase()
    if not verbinding:
        return False
    import httpx
    url, sleutel = verbinding
    r = httpx.post(f"{url}/rest/v1/{TABEL}",
                   params={"on_conflict": "naam"},
                   headers={"apikey": sleutel, "Authorization": f"Bearer {sleutel}",
                            "Content-Type": "application/json",
                            "Prefer": "resolution=merge-duplicates"},
                   json={"naam": naam, "inhoud": inhoud}, timeout=30.0)
    r.raise_for_status()
    return True


def _load(path: Path) -> list[dict]:
    if _supabase():
        return _db_lees(path.stem, []) or []
    return json.loads(path.read_text()) if path.exists() else []


def _state() -> dict:
    if _supabase():
        return _db_lees("mail_state", {}) or {}
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save_state(state: dict) -> None:
    if _db_schrijf("mail_state", state):
        return
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


ONZIN_ADRES = re.compile(r"^[^@]{0,1}@|^[-._+]+@")


def _bruikbaar(adres: str) -> bool:
    """Uit een webshop komt af en toe een adres als "-@mail.nl" mee. Dat is geen
    ontvanger maar een bounce, en bounces zijn precies wat een jong domein de das
    omdoet. Eén tekentje voor de apenstaart is nooit een echt adres."""
    return bool(adres) and "@" in adres and not ONZIN_ADRES.match(adres)


def _leads() -> list[dict]:
    """Marktplaats-leads eerst; die hebben een e-mailadres en de meeste voorraad."""
    alles = [l for l in _load(MP_LEADS) + _load(IG_LEADS)
             if _bruikbaar(l.get("email") or "")]
    uniek: dict[str, dict] = {}
    for lead in alles:
        uniek.setdefault(lead["email"].lower(), lead)
    return sorted(uniek.values(), key=lambda l: -(l.get("ads") or 0))


# ------------------------------------------------------------------ teksten


def _bedrijfsnaam(lead: dict) -> str:
    """De handelsnaam uit het KvK-veld is het netst, maar niet iedereen vult die in;
    de verkopersnaam op Marktplaats is dan het volgende beste. Nooit het e-mailadres
    in een aanhef gebruiken — "Hoi info@" leest als een rondzendbrief."""
    for sleutel in ("handelsnaam", "full_name", "name"):
        if lead.get(sleutel):
            return str(lead[sleutel])
    return lead["email"].split("@")[-1].split(".")[0].title()


def _aanhef(lead: dict) -> str:
    return "Hi"


def _jij(lead: dict) -> dict[str, str]:
    """Eenmansbedrijf tutoyeren, een team met meer mensen niet. De classificatie
    zet dat in `je_jullie`; alle voornaamwoorden en werkwoordsvormen in de mail
    komen hiervandaan, zodat er nooit "jullie ziet" of "je kunnen" uit rolt."""
    if (lead.get("je_jullie") or "Je") == "Je":
        return dict(jij="je", jij_nadruk="jij", jou="je", jouw="je",
                    ziet_jij="je ziet", zie_jij="zie je", ben_je="ben je",
                    zet_werkwoord="zet", jij_stopt="stop je", jij_wil="je wil",
                    weet_jij="weet je", mocht_jij="Mocht je", zou_jij="zou je")
    return dict(jij="jullie", jij_nadruk="jullie", jou="jullie", jouw="jullie",
                ziet_jij="jullie zien", zie_jij="zien jullie", ben_je="zijn jullie",
                zet_werkwoord="zetten", jij_stopt="stoppen jullie",
                jij_wil="jullie willen", weet_jij="weten jullie",
                mocht_jij="Mochten jullie", zou_jij="zouden jullie")


def _rond(n: int) -> str:
    """"14.431 advertenties" leest als een uitdraai uit een database, en dat is het
    ook. Afronden leest als iemand die even gekeken heeft."""
    if n >= 10000:
        return f"ruim {n // 1000}.000"
    if n >= 1000:
        return f"ruim {n // 100 * 100:,}".replace(",", ".")
    return f"zo'n {n // 10 * 10}"


RUBRIEKEN = {
    "kleding", "sieraden", "elektronica", "games", "boeken", "speelgoed",
    "muziekinstrumenten", "schoenen", "tassen", "meubels", "gereedschap",
    "vintage kleding", "kinderkleding", "sportartikelen", "knutselmaterialen",
}


def _haakje(lead: dict) -> str:
    """De openingszin die deze mail over deze handelaar laat gaan. Zonder zoiets
    is het een rondzendbrief en dat ziet iedereen. We gebruiken wat we van hem
    weten: rubriek, aantal advertenties, eigen webshop en webshopsysteem.

    De toon is met opzet terloops. "Zag je advertenties voorbijkomen" leest als
    iemand die toevallig keek; "Ik constateerde dat u 5.005 advertenties heeft"
    leest als software, en dat is precies wat het is."""
    v = _jij(lead)
    ads = lead.get("ads") or 0
    rubriek = (lead.get("verkoopt_vooral") or "").strip().lower()
    site = (lead.get("site") or "").replace("https://", "").replace(
        "http://", "").replace("www.", "").rstrip("/")
    shop = lead.get("shopsysteem")

    # De classificatie zet hier soms "Alles" of "Antieke vintage" neer. Alleen een
    # rubriek die als los zelfstandig naamwoord in een zin past mag erin; de rest
    # wordt weggelaten, want een rare zin valt meer op dan een vage zin.
    zin = f"Zag {v['jouw']} advertenties op Marktplaats voorbijkomen"
    if ads >= 100 and rubriek in RUBRIEKEN:
        zin += f", {_rond(ads)} stuks in {rubriek}."
    elif ads >= 100:
        zin += f", {_rond(ads)} stuks inmiddels."
    else:
        zin += "."

    if site and shop:
        zin += f" En dan ook nog een eigen shop op {site}, op {shop}. Netjes."
    elif site:
        zin += f" En dan ook nog een eigen shop op {site}. Netjes."
    else:
        zin += " Netjes."
    return zin


# Geen adresblok en geen afmeldregel onder de mails: Daniel wil dat ze lezen als
# een berichtje van een mens, niet als een mailing. Zijn beslissing, en hij weet
# dat het wettelijk anders hoort. De afmeldweg zit nu alleen nog in de
# List-Unsubscribe-header van elke mail — onzichtbaar voor de ontvanger, maar
# mailprogramma's tonen er hun eigen "afmelden"-knop mee.
MAIL1 = """{aanhef} {naam},

{haakje}

Even kort: ik heb {bedrijf} gebouwd, waarmee {jij} alles in een keer op
alle marketplaces {zet_werkwoord} in plaats van het handmatig over te tikken.
Zelf verkoop ik ook tweedehands, 700+ reviews met Revaleur, dus ik weet precies
hoeveel tijd dat kost. Inmiddels gebruiken 38 andere resellers het.

De eerste 7 dagen zijn gratis, en als het {jou} geen tijd bespaart {jij_stopt}
gewoon weer.

Zal ik {jou} een filmpje van een minuutje sturen? Dan {zie_jij} zo of het wat
voor {jou} is.

{ondertekening}"""

MAIL2 = """{aanhef} {naam},

Nog even over mijn mailtje van vorige week, geen idee of het bij {jou} langs is
gekomen.

Waar ik eigenlijk benieuwd naar ben: hoeveel tijd {ben_je} per week kwijt aan het
overzetten van {jouw} spullen naar andere platforms? Bij de meeste verkopers die
ik spreek is dat een avond of twee.

Als {jij_wil} stuur ik dat filmpje van een minuut, dan {zie_jij} zelf of het wat
scheelt. Geen verplichtingen, gewoon even kijken.

{ondertekening}"""

MAIL3 = """{aanhef} {naam},

Ik ga {jou} niet langer lastigvallen, dit is mijn laatste mailtje.

{mocht_jij} ooit denken "ik ben te veel tijd kwijt aan het overzetten van mijn
advertenties", dan {weet_jij} me te vinden: {site}. Stuur gerust een berichtje,
ook als het alleen is om even te sparren over waar {jouw} spullen nog meer
zouden kunnen staan.

Succes met de zaak, en veel verkoop!

{ondertekening}"""

ONDERTEKENING = """Groetjes,
Daniel"""



BEURTEN = [
    ("mail1", "Vraagje over {jouw} Marktplaats-aanbod", MAIL1),
    ("mail2", "Re: vraagje over {jouw} Marktplaats-aanbod", MAIL2),
    ("mail3", "Laatste bericht", MAIL3),
]


def _tekst(lead: dict, sjabloon: str) -> str:
    naam = _bedrijfsnaam(lead)
    return sjabloon.format(
        aanhef=_aanhef(lead),
        naam=naam.split()[0] if naam and len(naam.split()) == 1 else naam,
        haakje=_haakje(lead),
        bedrijf=BEDRIJF,
        site=SITE.replace("https://", ""),
        **_jij(lead),
        ondertekening="\x00" + ONDERTEKENING,
    )


def _onderwerp(lead: dict, n: int) -> str:
    """Ook de onderwerpregel volgt je/jullie — anders staat er "je aanbod" boven
    een mail die verder de hele tijd "jullie" zegt."""
    return BEURTEN[n][1].format(**_jij(lead))


def _netjes(tekst: str) -> str:
    """Alinea's op 78 tekens afbreken. De ondertekening (na \x00) blijft zoals hij
    is: daar zijn de regelafbrekingen betekenisvol."""
    body, _, staart = tekst.partition("\x00")
    alineas = [textwrap.fill(a.strip(), 78) for a in body.split("\n\n") if a.strip()]
    return "\n\n".join(alineas) + "\n\n" + staart


# --------------------------------------------------------------------- plan


def _dagnummer(state: dict) -> int:
    """De hoeveelste verzenddag dit is. Bepaalt hoeveel mails eruit mogen.

    Is er vandaag al gemaild, dan is vandaag die dag zelf en niet de volgende —
    anders klimt het budget binnen één dag mee met het opbouwschema en gaan er
    meer mails uit dan de bedoeling was."""
    dagen = {v["op"][:10] for st in state.values()
             for v in st.get("verstuurd", [])}
    vandaag = date.today().isoformat()
    return len(dagen) if vandaag in dagen else len(dagen) + 1


def _dagbudget(state: dict, override: int) -> int:
    if override:
        return override
    dag = _dagnummer(state)
    return max(n for vanaf, n in RAMP if dag >= vanaf)


def _beurt(lead: dict, st: dict | None) -> tuple[int, str] | None:
    """Welke mail is deze lead toe? None = niets doen."""
    if not st:
        return 0, "eerste mail"
    # Wie zelf met de hand is gemaild krijgt nooit een sjabloonmail erachteraan:
    # dat gesprek is van Daniel, niet van de machine.
    if (st.get("beantwoord") or st.get("afgemeld") or st.get("bounce")
            or st.get("afgewezen") or st.get("met_de_hand")):
        return None
    verstuurd = len(st.get("verstuurd", []))
    if verstuurd >= len(BEURTEN):
        return None
    laatste = datetime.fromisoformat(st["laatste"])
    wacht = FOLLOWUP_DAGEN[verstuurd - 1]
    if datetime.now() - laatste < timedelta(days=wacht):
        return None
    return verstuurd, f"opvolgmail {verstuurd} (na {wacht} dagen)"


def _wachtrij(state: dict, budget: int) -> list[tuple[dict, int, str]]:
    # Opvolgmails gaan vóór nieuwe eerste mails: een gesprek dat loopt is meer
    # waard dan een gesprek dat nog moet beginnen. Maar niet ten koste van álles
    # — zie NIEUW_AANDEEL: er blijft altijd ruimte voor nieuwe leads, anders
    # droogt de bovenkant van de trechter op zodra er een opvolggolf loopt.
    opvolg, nieuw = [], []
    for lead in _leads():
        beurt = _beurt(lead, state.get(lead["email"].lower()))
        if not beurt:
            continue
        (nieuw if beurt[0] == 0 else opvolg).append((lead, beurt[0], beurt[1]))

    # Grootste handelaren eerst: die hebben het meeste aan crosslisten.
    for lijst in (opvolg, nieuw):
        lijst.sort(key=lambda r: -(r[0].get("ads") or 0))

    gereserveerd = min(len(nieuw), int(budget * NIEUW_AANDEEL + 0.5))
    rij = opvolg[:budget - gereserveerd] + nieuw[:budget - len(opvolg[:budget - gereserveerd])]
    return rij[:budget]


def plan(args) -> None:
    state = _state()
    budget = _dagbudget(state, args.per_dag)
    rij = _wachtrij(state, budget)
    print(f"Verzenddag {_dagnummer(state)}, budget {budget} mails vandaag.\n")
    for lead, n, waarom in rij:
        print(f"  {BEURTEN[n][0]}  {_bedrijfsnaam(lead)[:32]:34s} "
              f"{lead.get('ads') or 0:>7} adv  {waarom}")
    print(f"\n{len(rij)} mails klaar om te versturen.")


# --------------------------------------------------------------------- send


def _controleer_afzender(met_verbinding: bool = True) -> str:
    if "VUL IN" in BEDRIJF_ADRES or "VUL IN" in BEDRIJF_KVK:
        sys.exit("Vul eerst BEDRIJF_ADRES en BEDRIJF_KVK in bovenaan dit bestand.\n"
                 "Zakelijke mail moet herleidbaar zijn naar een echt bedrijf; zonder\n"
                 "die gegevens mag het niet en gaat het bovendien de spam in.")
    if "omnivaleur.com" in os.environ.get("MAIL_USER", ""):
        sys.exit("MAIL_USER staat op omnivaleur.com. Dat is je productdomein — daar\n"
                 "gaan je klant- en factuurmails vandaan. Gebruik het aparte domein.")
    return _need("MAIL_HOST") if met_verbinding else ""


# ------------------------------------------------------------------- Notion


class Notion:
    """Houdt in de Leadlist bij wat er is verstuurd en wat er terugkwam.

    Twee lagen, omdat Notion een hele update weigert zodra er één kolomnaam of
    keuze in staat die niet bestaat:
      1. een regel onder aan de leadpagina, met datum. Blokken hebben geen
         kolomnamen en kunnen dus nooit breken. Dit is de echte administratie.
      2. de kolommen Fase, Status, Eerste contact, Volgende actie op en
         Follow-ups verstuurd, voor zover die aantoonbaar bestaan.

    De keuzes hieronder zijn overgenomen uit de LIVE database (2026-08-11). Zonder
    NOTION_TOKEN doet dit niets en gaat het verzenden gewoon door: mail versturen
    mag nooit stukgaan omdat een administratie niet bereikbaar is.
    """

    # per beurt: (fase, status, aantal follow-ups verstuurd)
    NA_MAIL = {
        0: ("2. Benaderd", "Reached Out", 0),
        1: ("T2. Tekst follow-up 1", "Reached Out", 1),
        2: ("T3. Tekst follow-up 2 (laatste)", "Reached Out", 2),
    }

    def __init__(self) -> None:
        self.token = os.environ.get("NOTION_TOKEN", "")
        self.paginas: dict[str, str] = {}
        self.props: dict = {}
        self.gemist: set[str] = set()
        self.zonder_pagina = 0
        self.klaar = False

    def _start(self) -> bool:
        if self.klaar:
            return bool(self.token)
        self.klaar = True
        if not self.token:
            print("  (geen NOTION_TOKEN — niets bijgehouden in Notion)")
            return False
        try:
            import leadgen_notion as notion
            self.paginas = notion.existing_pages(self.token)
            self.props = notion.schema(self.token)
        except Exception as e:  # noqa: BLE001
            print(f"  (Notion niet bereikbaar: {e})")
            self.token = ""
            return False
        return True

    def _schrijf(self, lead: dict, regel: str, wensen: dict) -> None:
        if not self._start():
            return
        pagina = self.paginas.get((lead.get("ig_url") or "").rstrip("/").lower())
        if not pagina:
            self.zonder_pagina += 1
            return
        import leadgen_notion as notion
        try:
            notion.append_log(pagina, self.token,
                              f"{datetime.now().strftime('%d-%m-%Y %H:%M')} — {regel}")
            self.gemist |= set(notion.set_props(pagina, self.token, wensen, self.props))
        except Exception as e:  # noqa: BLE001
            print(f"  (Notion: {lead.get('email')} niet bijgewerkt: {e})")

    def verstuurd(self, lead: dict, n: int, onderwerp: str) -> None:
        fase, status, gedaan = self.NA_MAIL[n]
        wensen = {"Fase": ("select", fase), "Status": ("status", status),
                  "Follow-ups verstuurd": ("number", gedaan)}
        if n == 0:
            wensen["Eerste contact"] = ("date", date.today().isoformat())
        if n < len(FOLLOWUP_DAGEN):
            volgende = date.today() + timedelta(days=FOLLOWUP_DAGEN[n])
            wensen["Volgende actie op"] = ("date", volgende.isoformat())
        self._schrijf(lead, f"mail {n + 1} verstuurd naar {lead['email']} — "
                            f"onderwerp: {onderwerp}", wensen)

    def geantwoord(self, lead: dict, soort: str = "onbekend") -> None:
        """Iemand heeft geantwoord. Dat is een FEIT en gaat altijd naar Fase
        '4. Gereageerd'. Of het ook interesse is, is een OORDEEL — en dat mag je
        niet automatisch aannemen: "we gebruiken al Channable" is een antwoord
        maar geen interesse, en die landde eerder gewoon tussen de warme leads.
        Status Interesse zetten we daarom alleen als er niets op tegenspreekt."""
        wensen = {"Fase": ("select", "4. Gereageerd"),
                  "Volgende actie op": ("date", date.today().isoformat())}
        if soort == "warm":
            wensen["Status"] = ("status", "Interesse")
        self._schrijf(lead, "heeft geantwoord op de mail", wensen)

    def wacht_op_daniel(self, lead: dict) -> None:
        """Warme reactie: de bal ligt bij Daniel. Dit is de enige lijst die hij
        elke dag hoeft te openen, dus die moet kloppen."""
        self._schrijf(lead, "warme reactie — concept klaargezet in je postbus",
                      {"Fase": ("select", FASE_AAN_ZET),
                       "Status": ("status", "Interesse"),
                       "Volgende actie op": ("date", date.today().isoformat())})

    def bal_bij_hen(self, lead: dict, dagen: int = 4) -> None:
        """Daniel heeft geantwoord; nu is het aan hen. Zonder deze stap bleef een
        lead op 'jij bent aan zet' staan nadat hij allang gereageerd had."""
        self._schrijf(lead, "jij hebt geantwoord — bal ligt bij hen",
                      {"Fase": ("select", FASE_BAL_BIJ_HEN),
                       "Volgende actie op": ("date",
                                             (date.today() + timedelta(days=dagen)).isoformat())})

    def afgesloten_bericht(self, lead: dict, soort: str) -> None:
        """Vastleggen dat er een afsluitend berichtje uit is. Zonder deze regel
        lijkt het in Notion alsof er nooit op hun antwoord gereageerd is, en dan
        gaat Daniel het alsnog met de hand doen — dubbelop."""
        wat = "gebruikt al iets" if soort == "concurrent" else "geen interesse"
        self._schrijf(lead, f"afsluitend bedankje gestuurd ({wat}) — niets meer te doen", {})

    def gebruikt_concurrent(self, lead: dict) -> None:
        """Crosslist al, maar met iemand anders. Bewaren als eigen groep: dit is
        geen nee maar een bezet ja, en de meest kansrijke lijst die je hebt zodra
        die andere tool tegenvalt."""
        self._schrijf(lead, "gebruikt al een andere tool — bezet, geen nee",
                      {"Fase": ("select", FASE_CONCURRENT),
                       "Afgesloten reden": ("select", "Gebruikt al een tool"),
                       "Volgende actie op": ("date", None)})

    def afgewezen(self, lead: dict) -> None:
        """Een nee. Wel gereageerd, dus geen doodgelopen spoor — maar ook geen
        interesse, en dat moet je in de lijst kunnen zien zonder elke mail te
        openen. Status blijft met opzet ongemoeid: er is geen 'nee'-status in de
        database, en een verkeerde is erger dan geen."""
        self._schrijf(lead, "heeft geantwoord: geen interesse",
                      {"Fase": ("select", "Geen interesse"),
                       "Afgesloten reden": ("select", "Niet geinteresseerd"),
                       "Volgende actie op": ("date", None)})

    def doodgelopen(self, lead: dict) -> None:
        """Alle mails eruit, nooit iets teruggehoord. Dit is het eindpunt van de
        automatische kant; wat hier belandt is klaar voor de machine."""
        self._schrijf(lead, f"geen reactie na alle opvolgmails "
                            f"({STIL_NA_DAGEN} dagen stil) — afgesloten",
                      {"Fase": ("select", "Doodgelopen"),
                       "Afgesloten reden": ("select", "Geen reactie na follow-ups"),
                       "Volgende actie op": ("date", None)})

    def met_de_hand(self, lead: dict, datum: str) -> None:
        """Al gemaild vanaf dit adres, maar niet volgens de administratie: Daniel
        deed het zelf, of het was een oudere ronde waarvan de administratie weg is.
        Beide gevallen betekenen hetzelfde — deze persoon is al benaderd en krijgt
        geen tweede koude mail."""
        self._schrijf(lead, f"al benaderd op {datum} buiten de machine om — "
                            f"geen automatische mail meer",
                      {"Fase": ("select", "2. Benaderd"),
                       "Status": ("status", "Reached Out"),
                       "Eerste contact": ("date", datum)})

    def afgemeld(self, lead: dict) -> None:
        self._schrijf(lead, "heeft zich afgemeld — niet meer mailen",
                      {"Fase": ("select", "Geen interesse"),
                       "Afgesloten reden": ("select", "Niet geinteresseerd")})

    def gebounced(self, lead: dict) -> None:
        self._schrijf(lead, "mail kwam niet aan (bounce) — adres klopt niet",
                      {"Fase": ("select", "Doodgelopen")})

    def afsluiten(self) -> None:
        if self.zonder_pagina:
            print(f"  ({self.zonder_pagina} leads staan nog niet in de Leadlist — "
                  f"draai leadgen_marktplaats.py push)")
        if self.gemist:
            print("\nNotion: deze kolommen of keuzes bestaan niet in de Leadlist en\n"
                  "zijn overgeslagen — " + ", ".join(sorted(self.gemist)) + ".\n"
                  "De regels onder aan elke leadpagina zijn wel gewoon geschreven.")


def _bericht(lead: dict, n: int, van: str) -> EmailMessage:
    onderwerp, sjabloon = _onderwerp(lead, n), BEURTEN[n][2]
    msg = EmailMessage()
    msg["From"] = f"{AFZENDER_NAAM} <{van}>"
    msg["To"] = lead["email"]
    msg["Subject"] = onderwerp
    # Zonder deze kop ziet een mailprogramma geen nette afmeldweg en telt het
    # eerder als spam. Met een mailto hoef je er geen webpagina voor te bouwen.
    msg["List-Unsubscribe"] = f"<mailto:{van}?subject=stop>"
    msg.set_content(_netjes(_tekst(lead, sjabloon)))
    return msg


def send(args) -> None:
    host = _controleer_afzender(met_verbinding=not args.dry_run)
    gebruiker = (os.environ.get("MAIL_USER") or "jij@omnivaleur.nl") if args.dry_run \
        else _need("MAIL_USER")
    state = _state()
    budget = _dagbudget(state, args.per_dag)
    rij = _wachtrij(state, budget)
    if not rij:
        print("Niemand is vandaag aan de beurt.")
        return

    print(f"Verzenddag {_dagnummer(state)}, {len(rij)} mails"
          f"{' (dry-run)' if args.dry_run else ''}.\n")
    if args.dry_run:
        lead, n, _ = rij[0]
        print(f"Voorbeeld — {_onderwerp(lead, n)}\naan: {lead['email']}\n")
        print(_netjes(_tekst(lead, BEURTEN[n][2])))
        print("\n" + "-" * 60)
        for lead, n, waarom in rij:
            print(f"  {BEURTEN[n][0]}  {lead['email']:38s} {waarom}")
        return

    boek = Notion()
    verstuurd = _verstuur(rij, gebruiker, host, state, boek)
    boek.afsluiten()
    print(f"\n{verstuurd} mails verstuurd. Morgen weer — draai 'check' voor antwoorden.")


def _verstuur(rij: list, gebruiker: str, host: str, state: dict,
              boek: "Notion") -> int:
    """Het eigenlijke verzenden. Zowel `send` als de autonome `tick` lopen hier
    doorheen, zodat er maar één plek is waar de administratie wordt bijgewerkt."""
    verstuurd = 0
    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as smtp:
        smtp.login(gebruiker, _need("MAIL_PASS"))
        for i, (lead, n, _) in enumerate(rij):
            sleutel = lead["email"].lower()
            try:
                smtp.send_message(_bericht(lead, n, gebruiker))
            except Exception as e:  # noqa: BLE001 — één weigering stopt de rest niet
                print(f"  ! {lead['email']}: {e}")
                continue
            st = state.setdefault(sleutel, {"verstuurd": [],
                                            "bedrijf": lead.get("handelsnaam")})
            st["verstuurd"].append({"beurt": BEURTEN[n][0],
                                    "op": datetime.now().isoformat(timespec="seconds")})
            st["laatste"] = datetime.now().isoformat(timespec="seconds")
            _save_state(state)          # na elke mail, zodat een crash niets dubbel doet
            verstuurd += 1
            boek.verstuurd(lead, n, _onderwerp(lead, n))
            print(f"  → {BEURTEN[n][0]} {lead['email']}", flush=True)
            if i < len(rij) - 1:
                time.sleep(random.uniform(*PAUZE))
    return verstuurd


# -------------------------------------------------------------------- check


def check(args) -> None:
    state = _state()
    if not state:
        sys.exit("Nog niets verstuurd.")
    boek = Notion()
    nieuw, afgemeld, bounces = _check_inbox(state, boek, args.dagen)
    boek.afsluiten()
    print(f"{nieuw} nieuwe antwoorden, {afgemeld} afmeldingen, {bounces} bounces.")
    if nieuw:
        print("\nWie heeft geantwoord:")
        for adres, st in state.items():
            if st.get("beantwoord", "").startswith(date.today().isoformat()):
                print(f"  {st.get('bedrijf') or adres} — {adres}")


def _zelfde_bedrijf(afzender: str, state: dict) -> str | None:
    """Het adres uit de administratie dat bij deze afzender hoort, op domein.

    Alleen bij precies één treffer. Twee mensen bij hetzelfde bedrijf die allebei
    zijn aangeschreven mag je niet op de gok aan elkaar knopen: dan zou het
    antwoord van de een de opvolging van de ander stilzetten."""
    domein = afzender.split("@")[-1].lower()
    if not domein or "." not in domein:
        return None

    def stam(d: str) -> str:
        # Alleen de naam zelf: geen subdomein, geen extensie, geen streepjes.
        # "info@mail.afstandsbediening-online.nl" → "afstandsbedieningonline".
        kern = ".".join(d.split(".")[-2:]).rsplit(".", 1)[0]
        return re.sub(r"[^a-z0-9]", "", kern)

    mij = stam(domein)
    if len(mij) < 8:                 # "shop", "abc" — te kort om iets te bewijzen
        return None

    kandidaten = []
    for adres in state:
        ander = stam(adres.split("@")[-1].lower())
        if len(ander) < 8:
            continue
        # Gelijk, of de een is het begin van de ander: afstandsbediening ↔
        # afstandsbedieningonline. Verderop in de naam laten we los, want dan
        # gaat het al snel over toevallige woorddelen.
        if mij == ander or mij.startswith(ander) or ander.startswith(mij):
            kandidaten.append(adres)
    return kandidaten[0] if len(kandidaten) == 1 else None


def _check_inbox(state: dict, boek: "Notion", dagen: int) -> tuple[int, int, int]:
    """Antwoorden, afmeldingen en bounces ophalen. Wie antwoordt krijgt geen
    opvolgmail meer; dat is het verschil tussen opvolgen en zeuren."""
    host, gebruiker = _need("IMAP_HOST"), _need("MAIL_USER")
    sinds = (date.today() - timedelta(days=dagen)).strftime("%d-%b-%Y")
    nieuw = afgemeld = bounces = 0
    per_adres = {l["email"].lower(): l for l in _leads()}
    with imaplib.IMAP4_SSL(host, 993) as imap:
        imap.login(gebruiker, _need("MAIL_PASS"))
        imap.select("INBOX")
        _, data = imap.search(None, f'(SINCE {sinds})')
        for num in data[0].split():
            _, ruw = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(ruw[0][1])
            afzender = parseaddr(msg.get("From", ""))[1].lower()
            body = _platte_tekst(msg)

            if BOUNCE_AFZENDERS.search(afzender):
                for adres in re.findall(r"[\w.+-]+@[\w.-]+\.\w{2,}", body):
                    st = state.get(adres.lower())
                    if st and not st.get("bounce"):
                        st["bounce"] = True
                        bounces += 1
                        if per_adres.get(adres.lower()):
                            boek.gebounced(per_adres[adres.lower()])
                continue

            st = state.get(afzender)
            if not st:
                # Antwoorden komen lang niet altijd terug van het adres waar wij
                # naartoe schreven. A. Dinkelaar kreeg mail op
                # info@afstandsbediening-online.nl en antwoordde vanaf
                # info@afstandsbediening.nl — voor de machine een wildvreemde, dus
                # zijn "nee dank je, het is al geautomatiseerd" werd niet gezien
                # én de opvolgmails liepen gewoon door. Zelfde huis, ander adres:
                # koppel op domein zodra dat maar één kandidaat oplevert.
                afzender = _zelfde_bedrijf(afzender, state) or afzender
                st = state.get(afzender)
            if not st:
                continue
            kop = str(msg.get("Subject", ""))
            automatisch = (AUTO_ONDERWERP.match(kop.replace("Re:", "").strip())
                           or msg.get("Auto-Submitted", "").lower().startswith("auto")
                           or msg.get("X-Autoreply") or msg.get("X-Autorespond")
                           or AUTO_TEKST.search(body[:400]))
            if automatisch:
                st["auto_antwoord"] = True
                continue

            lead = per_adres.get(afzender)
            # Wat voor antwoord is dit? De vololgorde is niet willekeurig: een
            # afmelding is het zwaarst, daarna "we gebruiken al iets" (dat vaak
            # óók een afwijzende zin bevat, en dan is de tool het echte nieuws),
            # dan een gewone nee. Blijft er niets over, dan is het warm.
            # Indelen op wat ZIJ schreef, niet op het citaat van onze eigen mail
            # eronder — zie _eigen_tekst.
            kort = _eigen_tekst(body)[:600] or body[:400]
            if AFMELD_WOORDEN.search(kort):
                soort = "afmelding"
            elif CONCURRENT.search(kort):
                soort = "concurrent"
            elif AFWIJZING.search(kort):
                soort = "afwijzing"
            else:
                soort = "warm"

            if not st.get("beantwoord"):
                st["beantwoord"] = datetime.now().isoformat(timespec="seconds")
                st["soort"] = soort
                nieuw += 1
                if lead:
                    boek.geantwoord(lead, soort)
                # Bij een warm antwoord: geen alarmmail meer, maar een CONCEPT in
                # zijn eigen postbus. Daniel ziet de reactie toch al op zijn
                # telefoon; een seintje erbovenop is ruis die hem juist opjaagt.
                # Wat hem rust geeft is dat het antwoord al klaarstaat.
                if lead and soort in ("warm", "onbekend"):
                    if _zet_concept_klaar(lead, msg, body):
                        st["concept_klaar"] = datetime.now().isoformat(timespec="seconds")
                    boek.wacht_op_daniel(lead)
                # Ook bij een nee: een afsluitend bedankje staat klaar, maar gaat
                # alleen weg als Daniel er zelf op drukt. Zo kan er nooit een
                # tweede bedankje uit naast het zijne.
                elif lead and soort in ("concurrent", "afwijzing"):
                    if _zet_concept_klaar(lead, msg, body, soort):
                        st["concept_klaar"] = datetime.now().isoformat(timespec="seconds")

            # Een afsluitmailtje inplannen — niet nu versturen. Zie
            # AFSLUIT_* hierboven voor waarom er tijd tussen moet zitten.
            if (soort in ("concurrent", "afwijzing") and not AFSLUIT_UIT
                    and not st.get("afsluit_gepland") and not st.get("afgemeld")
                    and not st.get("auto_antwoord")):
                wacht = random.randint(*AFSLUIT_VERTRAGING)
                st["afsluit_gepland"] = soort
                st["afsluit_na"] = (datetime.now()
                                    + timedelta(minutes=wacht)).isoformat(timespec="seconds")

            if soort == "afmelding" and not st.get("afgemeld"):
                st["afgemeld"] = True
                afgemeld += 1
                if lead:
                    boek.afgemeld(lead)
            elif soort == "concurrent" and not st.get("concurrent"):
                st["concurrent"] = True
                if lead:
                    boek.gebruikt_concurrent(lead)
            elif soort == "afwijzing" and not st.get("afgewezen"):
                # Wel netjes geantwoord, maar het is nee. Geen afmelding — hij mag
                # over een half jaar best weer benaderd worden — maar in de lijst
                # hoort dit niet naast de warme reacties te staan.
                st["afgewezen"] = True
                if lead:
                    boek.afgewezen(lead)

    _save_state(state)
    return nieuw, afgemeld, bounces


def _jouw_antwoorden_verwerken(state: dict, boek: "Notion") -> int:
    """Leest wat Daniel zélf heeft teruggeschreven en zet die leads op 'bal bij hen'.

    Zonder dit blijft een lead op "jij bent aan zet" staan nadat hij allang
    geantwoord heeft, en dan klopt precies de lijst niet die hij elke dag opent —
    waarmee de hele indeling waardeloos wordt. Hij antwoordt vaak vanaf zijn
    telefoon, buiten de machine om, dus de postbus is hier de enige waarheid."""
    host, gebruiker = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return 0
    per_adres = {l["email"].lower(): l for l in _leads()}
    bijgewerkt = 0
    with imaplib.IMAP4_SSL(host, 993) as imap:
        imap.login(gebruiker, wachtwoord)
        beantwoord_na = _antwoorden_van_daniel(imap, gebruiker)
    for adres, datum in beantwoord_na.items():
        st = state.get(adres)
        if not st:
            # Ook hier: hij kan vanaf een ander adres geantwoord hebben.
            adres2 = _zelfde_bedrijf(adres, state)
            if not adres2:
                continue
            adres, st = adres2, state[adres2]
        if not st.get("beantwoord"):
            continue                       # geen gesprek, dus niets om bij te werken
        # Een beleefd bedankje aan iemand die net "wij gebruiken al Channable"
        # schreef, betekent niet dat we op hem wachten. Zonder deze regel zette
        # deze stap vijf afgesloten leads terug op "bal bij hen" en was de lijst
        # meteen weer onbetrouwbaar — precies wat hij moest oplossen.
        if st.get("concurrent") or st.get("afgewezen") or st.get("afgemeld"):
            st["daniel_antwoordde"] = datum      # wel vastleggen, niets omzetten
            continue
        if st.get("daniel_antwoordde") == datum:
            continue                       # al verwerkt
        st["daniel_antwoordde"] = datum
        bijgewerkt += 1
        # Wat stuurde hij écht? Naast mijn voorstel leggen, zodat het verschil
        # zichtbaar wordt in plaats van te verdampen.
        try:
            with imaplib.IMAP4_SSL(host, 993) as im2:
                im2.login(gebruiker, wachtwoord)
                echt = _verzonden_tekst(im2, adres)
            if echt and _leer_van_verzonden(adres, echt):
                print(f"  ✎ je hebt mijn concept voor {adres} aangepast — vastgelegd")
        except Exception as e:  # noqa: BLE001
            print(f"  (leren mislukt voor {adres}: {e})")
        if per_adres.get(adres):
            boek.bal_bij_hen(per_adres[adres])
    if bijgewerkt:
        _save_state(state)
    return bijgewerkt


def _afsluiten_stille_leads(state: dict, boek: "Notion") -> int:
    """Wie alle mails heeft gehad en daarna STIL_NA_DAGEN niets liet horen, gaat
    naar de eindfase. Zonder dit blijft iedereen eeuwig op 'Benaderd' staan en
    zegt de lijst niets meer over wie er nog leeft."""
    per_adres = {l["email"].lower(): l for l in _leads()}
    gesloten = 0
    for adres, st in state.items():
        if st.get("afgesloten") or st.get("beantwoord") or st.get("afgemeld") \
                or st.get("bounce") or st.get("afgewezen"):
            continue
        if len(st.get("verstuurd", [])) < len(BEURTEN):
            continue
        stil = datetime.now() - datetime.fromisoformat(st["laatste"])
        if stil < timedelta(days=STIL_NA_DAGEN):
            continue
        st["afgesloten"] = datetime.now().isoformat(timespec="seconds")
        gesloten += 1
        if per_adres.get(adres):
            boek.doodgelopen(per_adres[adres])
    if gesloten:
        _save_state(state)
    return gesloten


def _eigen_mail_meenemen(state: dict, boek: "Notion") -> int:
    """Wat Daniel zelf verstuurt telt mee.

    Hij mailt leads ook buiten de machine om. Wist de machine dat niet, dan kon
    diezelfde persoon er later alsnog een koude mail achteraan krijgen — met een
    aanhef alsof ze elkaar nog nooit gesproken hadden. Daarom leest deze de map
    Verzonden en zet elk adres uit de leadlijst dat hij zelf heeft aangeschreven
    in de administratie, als 'met de hand'.

    Alleen nieuwe mails tellen (geen 'Re:'): een antwoord op een lopend gesprek
    zegt niets over wie er koud benaderd is, en de mails van de machine zelf staan
    al in de administratie."""
    host, gebruiker = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return 0
    per_adres = {l["email"].lower(): l for l in _leads()}
    nieuw = 0
    with imaplib.IMAP4_SSL(host, 993) as imap:
        imap.login(gebruiker, wachtwoord)
        imap.select('"Verzonden"')
        _, data = imap.search(None, "ALL")
        for num in (data[0] or b"").split():
            _, ruw = imap.fetch(num, "(BODY.PEEK[HEADER])")
            if not ruw or not ruw[0]:
                continue
            msg = email.message_from_bytes(ruw[0][1])
            ontvanger = parseaddr(msg.get("To", ""))[1].lower()
            onderwerp = str(msg.get("Subject", ""))
            if not ontvanger or onderwerp.lower().startswith("re:"):
                continue
            if ontvanger in state or ontvanger not in per_adres:
                continue
            # Een van onze eigen sjabloononderwerpen betekent dat de machine dit
            # verstuurde en de administratie kwijt is, niet dat Daniel het typte.
            # Ook dan geldt: niet nog eens mailen.
            try:
                wanneer = parsedate_to_datetime(msg.get("Date", ""))
                op = wanneer.replace(tzinfo=None).isoformat(timespec="seconds")
            except Exception:  # noqa: BLE001 — een rare datum mag dit niet stoppen
                op = datetime.now().isoformat(timespec="seconds")
            state[ontvanger] = {
                "verstuurd": [{"beurt": "met de hand", "op": op}],
                "bedrijf": per_adres[ontvanger].get("bedrijf"),
                "laatste": op,
                "met_de_hand": True,
            }
            nieuw += 1
            boek.met_de_hand(per_adres[ontvanger], op[:10])
    if nieuw:
        _save_state(state)
    return nieuw


def _afsluitmails(state: dict, boek: "Notion") -> int:
    """Verstuurt de ingeplande afsluitmailtjes waarvan de tijd om is.

    Aparte stap, en niet direct bij het lezen van de inbox: dan zou het antwoord
    binnen seconden terugkomen en dat leest als een automaat. Hier gaat het langs
    zodra de wachttijd voorbij is — meestal een uurtje later."""
    if AFSLUIT_UIT:
        return 0
    nu = datetime.now()
    klaar = [(a, st) for a, st in state.items()
             if st.get("afsluit_na") and not st.get("afsluit_verstuurd")
             and not st.get("afgemeld")
             and datetime.fromisoformat(st["afsluit_na"]) <= nu]
    if not klaar:
        return 0

    host, gebruiker = os.environ.get("MAIL_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return 0

    per_adres = {l["email"].lower(): l for l in _leads()}
    verstuurd = 0
    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as smtp:
        smtp.login(gebruiker, wachtwoord)
        for adres, st in klaar:
            lead = per_adres.get(adres) or {"email": adres, "je_jullie": "Je"}
            soort = st.get("afsluit_gepland")
            teksten = AFSLUIT_CONCURRENT if soort == "concurrent" else AFSLUIT_AFWIJZING
            je = "jullie" if str(lead.get("je_jullie", "")).lower().startswith("jul") else "je"
            body = random.choice(teksten).format(je=je)

            msg = EmailMessage()
            msg["From"] = f"{AFZENDER_NAAM} <{gebruiker}>"
            msg["To"] = adres
            # In dezelfde draad blijven: een los onderwerp zou een nieuw gesprek
            # beginnen terwijl dit juist een afsluiting is.
            msg["Subject"] = "Re: " + _onderwerp(lead, 0)
            msg.set_content(f"{body}\n\n{ONDERTEKENING}\n")
            try:
                smtp.send_message(msg)
            except Exception as e:  # noqa: BLE001 — één weigering stopt de rest niet
                print(f"  ! afsluitmail {adres}: {e}")
                continue
            st["afsluit_verstuurd"] = nu.isoformat(timespec="seconds")
            verstuurd += 1
            print(f"  ↩ afsluitmail ({soort}) naar {adres}", flush=True)
            if per_adres.get(adres):
                boek.afgesloten_bericht(per_adres[adres], soort)
            _save_state(state)
            time.sleep(random.uniform(*PAUZE))
    return verstuurd


# ── Klaargezet antwoord op een warme reactie ──────────────────────────────
# Daniel schiet in de startblokken zodra er "interesse" binnenkomt en wordt daar
# onrustig van: hij denkt dat hij nú moet reageren. Dat hoeft niet — bij koude
# mail wint niemand een klant met vijf minuten sneller zijn. Wat wél helpt is dat
# het antwoord al klaarstaat, zodat reageren dertig seconden kost in plaats van
# een half uur nadenken. Daarom zet de machine een CONCEPT klaar in zijn eigen
# postbus, in zijn eigen toon, met de video erin. Hij leest het, past aan wat hij
# wil, en drukt op verzenden.
#
# Bewust een concept en geen verzonden mail: dit is zijn gesprek, niet dat van de
# machine. Een verkeerd geraden antwoord dat al de deur uit is, kun je niet meer
# terughalen.

def _eigen_tekst(body: str) -> str:
    """Alleen wat DEZE persoon zelf schreef, zonder het citaat eronder.

    Dit is geen nettigheid maar een noodzaak. BoekenSchaap antwoordde onder het
    citaat: "geen interesse, je denkt toch niet dat ik dagelijks 1400 boeken
    handmatig op MP zet?" — maar de eerste 400 tekens van haar mail waren ONZE
    eigen verkooptekst, netjes ingesprongen met ">". Daarop indelen leverde
    "warm" op en er ging een concept met de video naar iemand die net nee had
    gezegd. Wat er in een citaat staat is per definitie niet wat zij vindt.

    Ook bottom-posting moet werken: haar zin stond ONDER het citaat, dus je kunt
    niet simpelweg alles na de scheidingsregel weggooien."""
    regels = []
    for r in (body or "").splitlines():
        kaal = r.strip()
        if kaal.startswith(">"):
            continue
        # De inleidende regel van een citaat ("X schreef op ...:", "Van: ...").
        if re.match(r"^\s*(Van|From|Verzonden|Sent|Aan|To|Onderwerp|Subject|Datum|Date)\s*:", r):
            continue
        if re.match(r"^\s*-{2,}\s*(Oorspronkelijk|Original)", r, re.I):
            continue
        if re.search(r"schreef (op .{0,30})?:$|wrote:$", kaal, re.I):
            continue
        regels.append(r)
    return "\n".join(regels).strip()


def _wat_vraagt_hij(body: str) -> set[str]:
    """Welke van de drie standaardvragen zitten in dit antwoord?"""
    t = body.lower()
    uit = set()
    if re.search(r"\b(video|filmpje|demo|laten zien|zien wat)\b", t):
        uit.add("video")
    if re.search(r"\b(prijs|prijzen|kost|kosten|tarief|per maand|abonnement)\b", t):
        uit.add("prijs")
    # \b(platform)\b vond "platformen" en "marketplaces" niet — de meervouden die
    # mensen juist schrijven. Vandaar \w* achter de stam.
    if re.search(r"\b(platform\w*|marketplace\w*|kanal\w*|welke sites|waar allemaal"
                 r"|welke marktplaatsen|ondersteun\w*)", t):
        uit.add("platforms")
    return uit


def _concept_tekst(lead: dict, body: str, soort: str = "warm") -> str:
    """Het voorstel-antwoord. Kort, in Daniels toon: geen verkooppraat, concreet,
    en altijd eindigen met een lage drempel.

    Ook bij een NEE staat er een concept klaar. Niets gaat vanzelf de deur uit —
    dat was juist de wens — maar als Daniel iemand netjes wil afsluiten, moet dat
    één tik zijn en geen schrijfklus. Hij beslist zelf of hij hem verstuurt."""
    if soort in ("concurrent", "afwijzing"):
        jij = "jullie" if str(lead.get("je_jullie", "")).lower().startswith("jul") else "je"
        teksten = AFSLUIT_CONCURRENT if soort == "concurrent" else AFSLUIT_AFWIJZING
        return "\n".join(["Hi,", "",
                          random.choice(teksten).format(je=jij), "", ONDERTEKENING])

    vraagt = _wat_vraagt_hij(body)
    jij = "jullie" if str(lead.get("je_jullie", "")).lower().startswith("jul") else "je"
    regels = ["Hi,", "", "Dank voor je reactie!"]

    if "video" in vraagt or not vraagt:
        regels += ["", f"Bij deze de video van een minuutje: {VIDEO}"]

    if "platforms" in vraagt:
        regels += ["", f"Qua platformen: {PLATFORMS}. Je zet een item één keer klaar "
                       "en kiest per stuk waar het heen gaat."]
    if "prijs" in vraagt:
        regels += ["", f"De kosten zijn {PRIJS}, en de eerste 7 dagen zijn gratis. "
                       f"Geen opzegtermijn — bespaart het {jij} geen tijd, dan stop "
                       f"je gewoon weer."]

    ads = lead.get("ads")
    if isinstance(ads, int) and ads > 300:
        regels += ["", f"Met {ads:,}".replace(",", ".") + " advertenties is de importfunctie "
                       "waarschijnlijk het startpunt: die leest je bestaande "
                       "Marktplaats-aanbod in, zodat je niets hoeft over te tikken."]

    regels += ["", "Laat maar weten wat je ervan vindt, of als je ergens tegenaan loopt.",
               "", ONDERTEKENING]
    return "\n".join(regels)


# ── Leren van wat Daniel er zelf van maakt ────────────────────────────────
# De sjablonen hierboven zijn mijn beste gok. Wat er écht de deur uit gaat is wat
# Daniel ervan maakt, en dáár zit de kennis. Deze twee functies leggen het
# verschil vast: het voorstel, en wat hij uiteindelijk verstuurde. Niemand
# verandert daar automatisch een sjabloon op — dat zou stilletjes de verkeerde
# les kunnen leren — maar het staat klaar om na te lezen en bewust te verwerken.
_LEERLOG_MAX = 30


def _onthoud_concept(adres: str, tekst: str) -> None:
    log = _db_lees("leerlog", None)
    if log is None:
        log = _lees_leerlog_lokaal()
    log = [x for x in log if x.get("adres") != adres][-_LEERLOG_MAX:]
    log.append({"adres": adres, "op": datetime.now().isoformat(timespec="seconds"),
                "voorstel": tekst[:4000], "verstuurd": None})
    _schrijf_leerlog(log)


def _leer_van_verzonden(adres: str, verstuurd: str) -> bool:
    """Legt naast het voorstel wat er werkelijk is verstuurd."""
    log = _db_lees("leerlog", None)
    if log is None:
        log = _lees_leerlog_lokaal()
    for x in log:
        if x.get("adres") == adres and not x.get("verstuurd"):
            x["verstuurd"] = verstuurd[:4000]
            x["aangepast"] = _kern(x.get("voorstel", "")) != _kern(verstuurd)
            _schrijf_leerlog(log)
            return bool(x["aangepast"])
    return False


def _kern(t: str) -> str:
    """Alleen de eigen tekst, zonder citaat en zonder witruimteverschillen —
    anders telt elke ingesprongen regel al als een aanpassing."""
    t = re.split(r"\n\s*(?:Op .{0,60}schreef|Van:|-----Oorspronkelijk)", t)[0]
    return re.sub(r"\s+", " ", t).strip().lower()


LEERLOG = OUT / "leerlog.json"


def _lees_leerlog_lokaal() -> list:
    try:
        return json.loads(LEERLOG.read_text()) if LEERLOG.exists() else []
    except Exception:  # noqa: BLE001
        return []


def _schrijf_leerlog(log: list) -> None:
    if _db_schrijf("leerlog", log):
        return
    try:
        LEERLOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 — leren mag nooit het mailen stoppen
        print(f"  (leerlog niet bewaard: {e})")


def _citaat(inkomend, body: str) -> str:
    """Het bericht waarop geantwoord wordt, als citaat eronder."""
    if not body:
        return ""
    wie = ""
    datum = ""
    if inkomend is not None:
        wie = parseaddr(inkomend.get("From", ""))[1]
        try:
            datum = parsedate_to_datetime(inkomend.get("Date", "")).strftime("%d-%m-%Y om %H:%M")
        except Exception:  # noqa: BLE001 — een rare datum mag het citaat niet slopen
            datum = ""
    kop = f"Op {datum} schreef {wie}:" if datum and wie else f"{wie or 'Zij'} schreef:"
    # Alleen het nieuwe deel citeren; de rest is onze eigen mail die er al onder
    # hing en dat wordt anders een sneeuwbal van citaten in citaten.
    schoon = re.split(r"\n\s*(?:Van:|-----Oorspronkelijk|Op .{0,60}schreef)", body)[0]
    regels = [r for r in schoon.strip().splitlines()][:25]
    return "\n\n" + kop + "\n" + "\n".join("> " + r for r in regels) + "\n"


def _zet_concept_klaar(lead: dict, inkomend, body: str, soort: str = "warm") -> bool:
    """Legt het voorstel als concept in Daniels postbus, in dezelfde draad."""
    host, van = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and van and wachtwoord):
        return False
    msg = EmailMessage()
    msg["From"] = f"{AFZENDER_NAAM} <{van}>"
    msg["To"] = lead["email"]
    onderwerp = str(inkomend.get("Subject", "")) if inkomend is not None else ""
    if not onderwerp.lower().startswith("re:"):
        onderwerp = "Re: " + (onderwerp or _onderwerp(lead, 0))
    msg["Subject"] = onderwerp
    # In dezelfde draad blijven, zodat het antwoord in zijn mailprogramma onder
    # het bericht hangt waar het bij hoort.
    if inkomend is not None and inkomend.get("Message-ID"):
        msg["In-Reply-To"] = inkomend["Message-ID"]
        msg["References"] = inkomend.get("References", "") + " " + inkomend["Message-ID"]
    # Het oorspronkelijke bericht eronder citeren. Zonder dit ziet een concept
    # eruit als een losse nieuwe mail: je leest je eigen antwoord zonder te zien
    # waar het op slaat, en je moet de draad erbij zoeken om te kunnen beoordelen
    # of het klopt. Precies zoals elk mailprogramma het zelf doet.
    # Datum en eigen kenmerk horen erbij. Zonder Date-kop is het bericht formeel
    # onvolledig; Zoho weet dan niet goed raad met het concept en laat hem na het
    # verzenden gewoon staan. Zeven blijven hangen op 17-08-2026 waren hierdoor.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(os.environ.get("MAIL_USER", "@x").split("@")[-1]))
    msg.set_content(_concept_tekst(lead, body, soort) + _citaat(inkomend, body))
    try:
        with imaplib.IMAP4_SSL(host, 993) as im:
            im.login(van, wachtwoord)
            bestaand = {r.decode().split(' "/" ')[-1].strip('"')
                        for r in (im.list()[1] or [])}
            map_ = CONCEPTMAP if CONCEPTMAP in bestaand else "Drafts"
            im.append(f'"{map_}"', "\\Draft", None, msg.as_bytes())
        print(f"  ✎ concept klaargezet voor {lead['email']}")
        # De voorgestelde tekst bewaren. Zonder dit valt later niet te zien wát
        # Daniel eraan veranderd heeft, en dan leert dit systeem nooit iets.
        _onthoud_concept(lead["email"].lower(), msg.get_content())
        return True
    except Exception as e:  # noqa: BLE001 — geen concept is vervelend, niet fataal
        print(f"  (concept niet klaargezet: {e})")
        return False


def _alarm(lead: dict, onderwerp: str, body: str) -> None:
    """Een seintje naar Daniel zelf. De machine draait onbewaakt; zonder dit zou
    hij elke dag in de postbus moeten kijken of er toevallig iemand geantwoord
    heeft, en dat is precies wat hij niet wil."""
    host, van = os.environ.get("MAIL_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and van and wachtwoord and ALARM_NAAR):
        return
    naam = _bedrijfsnaam(lead)
    msg = EmailMessage()
    msg["From"] = f"Leadmachine <{van}>"
    msg["To"] = ", ".join(ALARM_NAAR)
    msg["Subject"] = f"Reactie van {naam}"
    msg.set_content(
        f"{naam} heeft geantwoord op je koude mail.\n\n"
        f"Van:       {lead['email']}\n"
        f"Onderwerp: {onderwerp}\n"
        f"Bedrijf:   {lead.get('ads') or '?'} advertenties"
        f"{', webshop ' + lead['site'] if lead.get('site') else ''}\n"
        f"Notion:    {lead.get('ig_url')}\n\n"
        f"--- begin van het bericht ---\n{body[:1200].strip()}\n"
        f"--- einde ---\n\n"
        f"Antwoord vanuit {van}. Deze lead krijgt geen opvolgmails meer.\n")
    try:
        with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as smtp:
            smtp.login(van, wachtwoord)
            smtp.send_message(msg)
        print(f"  ↳ seintje gestuurd naar {', '.join(ALARM_NAAR)}")
        _archiveer(msg)
    except Exception as e:  # noqa: BLE001 — een mislukt seintje mag niets blokkeren
        print(f"  (seintje niet verstuurd: {e})")


def _archiveer(msg: EmailMessage) -> None:
    """Kopie in de Zoho-map leggen, gelezen gemarkeerd. Dit gebeurt via IMAP en
    niet met een Zoho-filterregel, zodat het meeverhuist met het script en niet
    stilletjes kapot kan gaan als iemand in de instellingen iets omzet."""
    host, gebruiker = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return
    try:
        with imaplib.IMAP4_SSL(host, 993) as imap:
            imap.login(gebruiker, wachtwoord)
            imap.append(f'"{ALARM_MAP}"', "\\Seen", None, msg.as_bytes())
    except Exception as e:  # noqa: BLE001 — archiveren mag nooit iets blokkeren
        print(f"  (kopie niet in {ALARM_MAP} gezet: {e})")


def _ruim_concepten_op() -> int:
    """Weggooien wat niet meer nodig is.

    Twee dingen gingen hier mis, allebei zichtbaar op 17-08-2026:
      1. Een concept dat via IMAP is neergelegd hoort niet bij Zoho's eigen
         conceptenadministratie. Druk je op verzenden, dan gaat de mail wél weg
         maar blijft het concept staan.
      2. Erger: er werden concepten neergelegd voor gesprekken die allang
         beantwoord waren, waardoor het leek alsof er werk lag dat er niet was.

    De regel is daarom niet "is het concept ouder dan de laatste mail", maar het
    enige dat echt telt: is er NA het klaarzetten een mail naar dat adres gegaan?
    Zo ja, dan is dit voorstel verstuurd of ingehaald en mag het weg."""
    host, gebruiker = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return 0
    weg = 0
    try:
        with imaplib.IMAP4_SSL(host, 993) as imap:
            imap.login(gebruiker, wachtwoord)
            bestaand = {r.decode().split(' "/" ')[-1].strip('"')
                        for r in (imap.list()[1] or [])}
            map_ = CONCEPTMAP if CONCEPTMAP in bestaand else "Drafts"

            def _tijden(mappen, veld):
                """Laatste tijdstip per adres, in seconden sinds 1970 — koppen
                dragen een tijdzone, dus nooit naïef vergelijken."""
                uit: dict[str, float] = {}
                for m_ in mappen:
                    if imap.select(f'"{m_}"', readonly=True)[0] != "OK":
                        continue
                    _, d = imap.search(None, "ALL")
                    for num in (d[0] or b"").split():
                        _, ruw = imap.fetch(num, "(BODY.PEEK[HEADER])")
                        if not ruw or not ruw[0]:
                            continue
                        msg = email.message_from_bytes(ruw[0][1])
                        adres = parseaddr(msg.get(veld, ""))[1].lower()
                        try:
                            ts = parsedate_to_datetime(msg.get("Date", "")).timestamp()
                        except Exception:  # noqa: BLE001
                            continue
                        if adres and (adres not in uit or ts > uit[adres]):
                            uit[adres] = ts
                return uit

            verstuurd = _tijden(["Verzonden"], "To")

            imap.select(f'"{map_}"')
            _, d = imap.uid("search", None, "ALL")
            uids = (d[0] or b"").split()
            # Per adres hoort er hooguit één concept te liggen. Bij het opnieuw
            # klaarzetten kon er een tweede bijkomen, en twee voorstellen voor
            # dezelfde persoon is geen keuze maar verwarring.
            gezien: dict[str, bytes] = {}
            dubbel: set[bytes] = set()
            for uid in uids:
                _, r = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
                if not r or not r[0]:
                    continue
                a = parseaddr(email.message_from_bytes(r[0][1]).get("To", ""))[1].lower()
                if not a:
                    continue
                if a in gezien:
                    dubbel.add(gezien[a])       # de oudere gaat weg
                gezien[a] = uid

            for uid in uids:
                _, ruw = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
                if not ruw or not ruw[0]:
                    continue
                msg = email.message_from_bytes(ruw[0][1])
                adres = parseaddr(msg.get("To", "")) [1].lower()
                if not adres:
                    continue
                # Wanneer is dit concept neergelegd? Eigen Date-kop als die er is,
                # anders wat de server noteerde. Alles in seconden sinds 1970:
                # koppen dragen een tijdzone, INTERNALDATE komt lokaal terug, en
                # die twee naïef vergelijken gaf eerder een verschil van twee uur.
                gemaakt = None
                try:
                    gemaakt = parsedate_to_datetime(msg.get("Date", "")).timestamp()
                except Exception:  # noqa: BLE001
                    pass
                if gemaakt is None:
                    _, meta = imap.uid("fetch", uid, "(INTERNALDATE)")
                    intern = imaplib.Internaldate2tuple(meta[0] if meta and meta[0] else b"")
                    gemaakt = time.mktime(intern) if intern else None
                if gemaakt is None:
                    continue
                if uid in dubbel:
                    imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    weg += 1
                    continue
                # ALLEEN weggooien als er ná het concept een mail is uitgegaan.
                #
                # Eerst stond hier "hebben wij na hun laatste bericht geantwoord",
                # en dat was fout: een concept dat ik bewust later klaarzet als
                # vervolg op een gesprek dat allang beantwoord is, werd dan binnen
                # een half uur opgeruimd. Dat gebeurde ook — een vervolgmail
                # verdween terwijl Daniel hem zat te lezen.
                #
                # Wat telt is niet of het gesprek "open" staat, maar of dit
                # voorstel nog ergens toe dient. Is er na het klaarzetten iets
                # naar dat adres gegaan, dan is het verstuurd of ingehaald.
                ons = verstuurd.get(adres)
                if ons is not None and ons > gemaakt:
                    # Zoho wil de vlag tussen haakjes; zonder geeft hij BAD.
                    imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
                    weg += 1
            if weg:
                imap.expunge()
    except Exception as e:  # noqa: BLE001 — opruimen mag nooit het mailen stoppen
        print(f"  (concepten niet opgeruimd: {e})")
    return weg


def _opruimen(state: dict) -> None:
    """Het postvak op orde houden, elke beurt opnieuw.

    De regel is simpel: in POSTVAK IN blijft alleen staan wat nog een antwoord van
    Daniel nodig heeft. Ontvangstbevestigingen, bounces en systeemmail gaan naar
    Automatisch; wie hij al beantwoord heeft gaat naar Beantwoord. Er wordt nooit
    iets weggegooid, alleen verplaatst."""
    host, gebruiker = os.environ.get("IMAP_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return
    verplaatst = {MAP_AUTOMATISCH: 0, MAP_BEANTWOORD: 0}
    try:
        with imaplib.IMAP4_SSL(host, 993) as imap:
            imap.login(gebruiker, wachtwoord)
            bestaand = {r.decode().split(' "/" ')[-1].strip('"')
                        for r in (imap.list()[1] or [])}
            for map_ in (MAP_AUTOMATISCH, MAP_BEANTWOORD, ALARM_MAP):
                if map_ not in bestaand:
                    try:
                        imap.create(f'"{map_}"')
                    except imaplib.IMAP4.error:
                        pass          # bestond toch al

            beantwoord_na = _antwoorden_van_daniel(imap, gebruiker)

            # Op UID werken, niet op volgnummer: zodra je een bericht als
            # verwijderd markeert schuiven de volgnummers op en wijst het
            # volgende nummer naar niets meer.
            imap.select("INBOX")
            _, data = imap.uid("search", None, "ALL")
            for uid in (data[0] or b"").split():
                _, ruw = imap.uid("fetch", uid, "(RFC822)")
                if not ruw or not ruw[0]:
                    continue
                msg = email.message_from_bytes(ruw[0][1])
                afzender = parseaddr(msg.get("From", ""))[1].lower()
                doel = _waar_hoort_dit(msg, afzender, state, beantwoord_na)
                if not doel:
                    continue
                imap.uid("copy", uid, f'"{doel}"')
                imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
                verplaatst[doel] += 1
            imap.expunge()
    except Exception as e:  # noqa: BLE001 — opruimen mag nooit het mailen stoppen
        print(f"  (postvak niet opgeruimd: {e})")
        return
    if any(verplaatst.values()):
        print(f"  postvak opgeruimd: {verplaatst[MAP_AUTOMATISCH]} naar "
              f"{MAP_AUTOMATISCH}, {verplaatst[MAP_BEANTWOORD]} naar {MAP_BEANTWOORD}")


def _verzonden_tekst(imap, adres: str) -> str | None:
    """De laatste mail die Daniel zelf naar dit adres stuurde, als platte tekst."""
    try:
        imap.select('"Verzonden"', readonly=True)
        _, d = imap.search(None, f'(TO "{adres}")')
        nums = (d[0] or b"").split()
        if not nums:
            return None
        _, ruw = imap.fetch(nums[-1], "(RFC822)")
        if not ruw or not ruw[0]:
            return None
        msg = email.message_from_bytes(ruw[0][1])
        return _platte_tekst(msg)
    except Exception:  # noqa: BLE001 — leren mag nooit iets breken
        return None


def _antwoorden_van_daniel(imap, gebruiker: str) -> dict[str, str]:
    """Per adres de datum van Daniels laatste bericht eraan. Alleen berichten die
    hij zelf heeft getypt tellen: de koude mails komen uit dit script en die staan
    in de administratie, dus daaraan mag je niet zien dat er 'geantwoord' is."""
    laatste: dict[str, str] = {}
    imap.select('"Verzonden"')
    _, data = imap.search(None, "ALL")
    for num in data[0].split():
        _, ruw = imap.fetch(num, "(BODY.PEEK[HEADER])")
        msg = email.message_from_bytes(ruw[0][1])
        ontvanger = parseaddr(msg.get("To", ""))[1].lower()
        onderwerp = str(msg.get("Subject", ""))
        # Alleen echte reacties: die beginnen met Re:. De koude mails niet.
        if ontvanger and onderwerp.lower().startswith("re:"):
            datum = msg.get("Date", "")
            if datum > laatste.get(ontvanger, ""):
                laatste[ontvanger] = datum
    return laatste


def _waar_hoort_dit(msg, afzender: str, state: dict,
                    beantwoord_na: dict[str, str]) -> str | None:
    onderwerp = str(msg.get("Subject", ""))
    if SYSTEEM_AFZENDER.search(afzender) or BOUNCE_AFZENDERS.search(afzender):
        return MAP_AUTOMATISCH
    st = state.get(afzender)
    if st and st.get("auto_antwoord") and not st.get("beantwoord"):
        return MAP_AUTOMATISCH
    if AUTO_ONDERWERP.match(onderwerp.replace("Re:", "").strip()):
        return MAP_AUTOMATISCH
    if afzender in beantwoord_na:
        return MAP_BEANTWOORD
    return None            # echte reactie, nog niet beantwoord: laat staan


def _platte_tekst(msg) -> str:
    if not msg.is_multipart():
        return msg.get_payload(decode=True).decode(errors="ignore")
    for deel in msg.walk():
        if deel.get_content_type() == "text/plain":
            return deel.get_payload(decode=True).decode(errors="ignore")
    return ""


# --------------------------------------------------------------------- tick


def _tijdstippen(n: int) -> list[str]:
    """n willekeurige verzendmomenten binnen kantoortijd, met minstens MIN_GAT
    minuten ertussen. Vijftien mails achter elkaar om negen uur 's ochtends is
    het patroon van een mailing; verspreid over de dag is het patroon van iemand
    die tussen het werk door mailt."""
    (h1, m1), (h2, m2) = VENSTER
    vroeg, laat = h1 * 60 + m1, h2 * 60 + m2
    gekozen: list[int] = []
    for _ in range(4000):
        if len(gekozen) >= n:
            break
        kandidaat = random.randint(vroeg, laat)
        if all(abs(kandidaat - t) >= MIN_GAT for t in gekozen):
            gekozen.append(kandidaat)
    return [f"{t // 60:02d}:{t % 60:02d}" for t in sorted(gekozen)]


def _dagplan(state: dict, override: int) -> dict:
    """Het rooster van vandaag. Wordt één keer per dag gemaakt en daarna alleen
    nog afgevinkt, zodat een herstart niet ineens alles opnieuw inplant."""
    plan = (_db_lees("mail_plan", {}) if _supabase()
            else (json.loads(PLAN.read_text()) if PLAN.exists() else {})) or {}
    vandaag = date.today().isoformat()
    if plan.get("dag") != vandaag:
        # Wat er vandaag al met de hand is verstuurd telt mee voor het dagbudget.
        al_gedaan = sum(1 for st in state.values()
                        for v in st.get("verstuurd", []) if v["op"][:10] == vandaag)
        budget = max(0, _dagbudget(state, override) - al_gedaan)
        # Stond de machine een hele dag stil, dan is dat hier te zien: het vorige
        # rooster is dan ouder dan gisteren. Dat gat gaat mee in het dagbericht,
        # want een stille storing merk je anders pas als je het je afvraagt.
        gemist = _gemiste_dagen(plan.get("dag"))
        plan = {"dag": vandaag, "tijden": _tijdstippen(budget), "gedaan": 0,
                "al_met_de_hand": al_gedaan, "gecheckt": False,
                "gerapporteerd": False, "gemist": gemist, "fouten": []}
        _save_plan(plan)
    return plan


def _gemiste_dagen(vorige: str | None) -> list[str]:
    if not vorige:
        return []
    dag = date.fromisoformat(vorige) + timedelta(days=1)
    gaten = []
    while dag < date.today():
        gaten.append(dag.isoformat())
        dag += timedelta(days=1)
    return gaten


def _save_plan(plan: dict) -> None:
    if _db_schrijf("mail_plan", plan):
        return
    OUT.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False))


def tick(args) -> None:
    """Eén beurt van de autonome stand. Bedoeld om elke tien minuten te draaien;
    hij bepaalt zelf of er nu iets moet en zwijgt als er niets te doen is.

    Alle beslissingen staan op schijf, niet in het geheugen: valt de Mac uit of
    slaapt hij een uur, dan pakt de volgende beurt het rooster gewoon weer op en
    gaat er niets dubbel de deur uit."""
    host = _controleer_afzender()
    gebruiker = _need("MAIL_USER")
    state = _state()
    plan = _dagplan(state, args.per_dag)
    nu = datetime.now().strftime("%H:%M")

    verlopen = sum(1 for t in plan["tijden"] if t <= nu)
    te_doen = min(verlopen - plan["gedaan"], args.max_per_beurt)
    boek = Notion()

    # Eerst kijken wat Daniel zelf heeft verstuurd, pas daarna mailen. Andersom
    # zou de machine iemand koud kunnen aanschrijven die hij een uur eerder al
    # persoonlijk had gemaild.
    if te_doen > 0:
        try:
            eigen = _eigen_mail_meenemen(state, boek)
            if eigen:
                print(f"{datetime.now():%d-%m %H:%M} — {eigen} lead(s) die je zelf "
                      f"al gemaild hebt overgenomen; die krijgen niets van de machine")
        except Exception as e:  # noqa: BLE001 — dichte inbox stopt het mailen niet
            print(f"  (verzonden map niet gelezen: {e})")
            plan.setdefault("fouten", []).append(f"verzonden map niet gelezen: {e}")

    if te_doen > 0:
        rij = _wachtrij(state, te_doen)
        if rij:
            print(f"{datetime.now():%d-%m %H:%M} — {len(rij)} mail(s) aan de beurt "
                  f"(rooster vandaag: {len(plan['tijden'])} stuks)")
            gedaan = _verstuur(rij, gebruiker, host, state, boek)
            plan["gedaan"] += gedaan
            _save_plan(plan)
        else:
            plan["gedaan"] = verlopen      # niemand beschikbaar: slot laten vervallen
            _save_plan(plan)

    # Elke beurt de inbox nakijken. Dit stond eerst op één keer per dag om 13:00,
    # maar dan blijft een reactie van 's avonds een etmaal liggen — en juist bij
    # een warme reactie telt elk uur. Zo valt iemand die antwoordt ook meteen uit
    # de opvolging in plaats van pas de volgende dag.
    if state:
        try:
            # Veertien dagen terugkijken, niet vier. Elk antwoord wordt maar één keer
            # verwerkt (de administratie onthoudt dat), dus verder terugkijken kost
            # niets en vangt wél de antwoorden op die binnenkwamen terwijl de machine
            # stilstond of terwijl er nog geen indeling in nee/concurrent bestond.
            nieuw, afgemeld, bounces = _check_inbox(state, boek, dagen=14)
            print(f"{datetime.now():%d-%m %H:%M} — inbox: {nieuw} antwoorden, "
                  f"{afgemeld} afmeldingen, {bounces} bounces")
        except Exception as e:  # noqa: BLE001 — een dichte inbox stopt het mailen niet
            print(f"  (inbox niet gelezen: {e})")
            plan.setdefault("fouten", []).append(f"inbox niet gelezen: {e}")
        if not plan.get("gecheckt"):
            plan["gecheckt"] = True
            _save_plan(plan)
        try:
            afsluit = _afsluitmails(state, boek)
            if afsluit:
                print(f"{datetime.now():%d-%m %H:%M} — {afsluit} afsluitmail(s) verstuurd")
        except Exception as e:  # noqa: BLE001 — dit mag de ronde niet stoppen
            print(f"  (afsluitmail niet verstuurd: {e})")
            plan.setdefault("fouten", []).append(f"afsluitmail: {e}")

        try:
            eigen = _jouw_antwoorden_verwerken(state, boek)
            if eigen:
                print(f"{datetime.now():%d-%m %H:%M} — {eigen} lead(s) waar jij op "
                      f"hebt geantwoord → bal bij hen")
        except Exception as e:  # noqa: BLE001 — mag de ronde niet stoppen
            print(f"  (jouw antwoorden niet gelezen: {e})")

        opgeruimd = _ruim_concepten_op()
        if opgeruimd:
            print(f"{datetime.now():%d-%m %H:%M} — {opgeruimd} verstuurd concept opgeruimd")

        gesloten = _afsluiten_stille_leads(state, boek)
        if gesloten:
            print(f"{datetime.now():%d-%m %H:%M} — {gesloten} lead(s) afgesloten: "
                  f"geen reactie na alle opvolgmails")
        _opruimen(state)

    # Aan het eind van de dag één berichtje: wat er is gebeurd, of er iets mis
    # ging, en of de machine tussendoor stil heeft gestaan. Zolang dit elke avond
    # binnenkomt weet Daniel dat de machine leeft; blijft het uit, dan is dát het
    # signaal. Volledig sluitend is het niet — staat de Mac uit, dan draait er
    # niets en komt er ook geen bericht. Het gat wordt dan de volgende dag gemeld.
    if not plan.get("gerapporteerd") and nu >= "20:45":
        _dagbericht(state, plan)
        plan["gerapporteerd"] = True
        _save_plan(plan)

    boek.afsluiten()


def toon_leerlog() -> None:
    """`python3 leadgen_mail.py leren` — wat heeft Daniel aan mijn voorstellen
    veranderd? Dit is het materiaal om de sjablonen bewust bij te stellen."""
    log = _db_lees("leerlog", None)
    if log is None:
        log = _lees_leerlog_lokaal()
    aangepast = [x for x in log if x.get("aangepast")]
    print(f"{len(log)} voorstellen bewaard, {len(aangepast)} daarvan aangepast\n")
    for x in aangepast[-10:]:
        print("═" * 72)
        print(f"{x['adres']}   {x['op'][:16]}")
        print("--- mijn voorstel " + "-" * 54)
        print(_kern(x.get("voorstel", ""))[:900])
        print("--- wat jij stuurde " + "-" * 52)
        print(_kern(x.get("verstuurd", ""))[:900])
    if not aangepast:
        print("Nog niets aangepast — of er is nog geen concept verstuurd.")


def _dagbericht(state: dict, plan: dict) -> None:
    """Het avondbericht aan Daniel."""
    vandaag = date.today().isoformat()
    vandaag_uit = sum(1 for st in state.values()
                      for v in st.get("verstuurd", []) if v["op"][:10] == vandaag)
    gepland = len(plan.get("tijden", [])) + plan.get("al_met_de_hand", 0)
    totaal = sum(len(st.get("verstuurd", [])) for st in state.values())
    benaderd = len(state)
    antwoorden = sum(1 for st in state.values() if st.get("beantwoord"))
    auto = sum(1 for st in state.values() if st.get("auto_antwoord"))
    afgemeld = sum(1 for st in state.values() if st.get("afgemeld"))
    bounces = sum(1 for st in state.values() if st.get("bounce"))
    afgewezen = sum(1 for st in state.values() if st.get("afgewezen"))
    afgesloten = sum(1 for st in state.values() if st.get("afgesloten"))
    handmatig = sum(1 for st in state.values() if st.get("met_de_hand"))
    resterend = len([l for l in _leads() if l["email"].lower() not in state])

    goed = vandaag_uit >= gepland and not plan.get("gemist") and not plan.get("fouten")
    kop = "Leadmachine: alles goed" if goed else "Leadmachine: LET OP"

    regels = [
        f"Vandaag verstuurd:   {vandaag_uit} van {gepland} gepland",
        f"Totaal verstuurd:    {totaal} mails naar {benaderd} bedrijven",
        f"Echte reacties:      {antwoorden}",
        f"Automatische reacties: {auto}",
        f"Warme reacties:      {sum(1 for st in state.values() if st.get('soort') == 'warm')}",
        f"Gebruikt concurrent: {sum(1 for st in state.values() if st.get('concurrent'))}",
        f"Geen interesse:      {afgewezen}",
        f"Afmeldingen:         {afgemeld}",
        f"Bounces:             {bounces}",
        f"Doodgelopen:         {afgesloten} (alles verstuurd, nooit iets gehoord)",
        f"Zelf gemaild:        {handmatig} (door jou, buiten de machine om)",
        f"Nog in de wachtrij:  {resterend} leads",
    ]
    if plan.get("gemist"):
        regels += ["", "LET OP — de machine heeft stilgestaan op: "
                       + ", ".join(plan["gemist"])]
    if plan.get("fouten"):
        regels += ["", "Fouten vandaag:"] + [f"  {f}" for f in plan["fouten"][:10]]
    if vandaag_uit < gepland:
        regels += ["", f"Er zijn {gepland - vandaag_uit} mails niet verstuurd. "
                       "Meestal betekent dat dat de Mac uit stond of sliep."]
    if bounces > max(3, totaal // 10):
        regels += ["", "Veel bounces. Dat is slecht voor je domein — laat de lijst "
                       "nakijken voordat je verder mailt."]

    host, van = os.environ.get("MAIL_HOST"), os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and van and wachtwoord and ALARM_NAAR):
        return
    msg = EmailMessage()
    msg["From"] = f"Leadmachine <{van}>"
    msg["To"] = ", ".join(ALARM_NAAR)
    msg["Subject"] = f"{kop} — {date.today().strftime('%d-%m-%Y')}"
    msg.set_content("\n".join(regels) + "\n")
    try:
        with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as smtp:
            smtp.login(van, wachtwoord)
            smtp.send_message(msg)
        print(f"{datetime.now():%d-%m %H:%M} — dagbericht verstuurd")
        _archiveer(msg)
    except Exception as e:  # noqa: BLE001
        print(f"  (dagbericht niet verstuurd: {e})")


def overzetten(args) -> None:
    """Alles wat nu op de Mac staat naar Supabase tillen, zodat de machine ook
    zonder die Mac verder kan. Draai dit één keer bij de overstap, en opnieuw
    zodra er nieuwe leads bij komen."""
    if not _supabase():
        sys.exit("Zet SUPABASE_URL en SUPABASE_KEY in je omgeving.")
    for pad, naam in ((MP_LEADS, "mp_leads"), (IG_LEADS, "leads"),
                      (STATE, "mail_state"), (PLAN, "mail_plan")):
        if not pad.exists():
            print(f"  {naam}: niets te doen")
            continue
        inhoud = json.loads(pad.read_text())
        _db_schrijf(naam, inhoud)
        aantal = len(inhoud) if isinstance(inhoud, (list, dict)) else 1
        print(f"  {naam}: {aantal} regels overgezet")
    print("Klaar. De machine kan nu ook zonder je Mac draaien.")


# ------------------------------------------------------------------- status


def status(args) -> None:
    state, leads = _state(), _leads()
    verstuurd = sum(len(v.get("verstuurd", [])) for v in state.values())
    benaderd = len(state)
    antwoord = sum(1 for v in state.values() if v.get("beantwoord"))
    print(f"{len(leads)} leads met e-mailadres in de lijst")
    print(f"{benaderd} benaderd, {verstuurd} mails verstuurd")
    print(f"{antwoord} antwoorden "
          f"({100 * antwoord / benaderd:.0f}%)" if benaderd else "")
    print(f"{sum(1 for v in state.values() if v.get('afgemeld'))} afgemeld, "
          f"{sum(1 for v in state.values() if v.get('bounce'))} bounces")
    wacht = len(_wachtrij(state, 10 ** 6))
    print(f"{wacht} staan er nog in de wachtrij")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for naam, functie, hulp in (
            ("plan", plan, "wie is vandaag aan de beurt"),
            ("send", send, "de mails van vandaag versturen"),
            ("status", status, "hoe staat het ervoor")):
        p = sub.add_parser(naam, help=hulp)
        if naam in ("plan", "send"):
            p.add_argument("--per-dag", type=int, default=0,
                           help="afwijken van het opbouwschema")
        if naam == "send":
            p.add_argument("--dry-run", action="store_true")
        p.set_defaults(func=functie)

    c = sub.add_parser("check", help="antwoorden, afmeldingen en bounces ophalen")
    c.add_argument("--dagen", type=int, default=30)
    c.set_defaults(func=check)

    t = sub.add_parser("tick", help="autonome beurt; elke tien minuten draaien")
    t.add_argument("--per-dag", type=int, default=0,
                   help="afwijken van het opbouwschema")
    t.add_argument("--max-per-beurt", type=int, default=3,
                   help="hoeveel mails er in één beurt maximaal uit mogen")
    t.set_defaults(func=tick)

    u = sub.add_parser("overzetten",
                       help="leadlijst en administratie naar Supabase zetten")
    u.set_defaults(func=overzetten)

    r = sub.add_parser("dagbericht", help="het avondbericht nu versturen (test)")
    r.set_defaults(func=lambda a: _dagbericht(_state(), _dagplan(_state(), 0)))

    ll = sub.add_parser("leren",
                        help="wat heb jij aan mijn conceptantwoorden veranderd?")
    ll.set_defaults(func=lambda a: toon_leerlog())

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
