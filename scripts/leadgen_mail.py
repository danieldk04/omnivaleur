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
from email.utils import parseaddr
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
RAMP = [(1, 5), (2, 15), (6, 25), (11, 40)]
FOLLOWUP_DAGEN = (5, 12)      # opvolgmail 1 en 2, in dagen na de vorige mail
PAUZE = (40, 110)             # seconden tussen twee mails, willekeurig
VENSTER = (8, 45), (20, 30)   # vroegste en laatste verzendtijd op een dag
MIN_GAT = 9                   # minuten die minimaal tussen twee tijdstippen zitten

AFMELD_WOORDEN = re.compile(
    r"\b(stop|afmelden|uitschrijven|unsubscribe|geen interesse|niet meer mailen)\b",
    re.I)
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
AUTO_TEKST = re.compile(
    r"(bedankt voor (je|jouw|uw) (e-?mail|bericht)"
    r"|in goede orde ontvangen"
    r"|we (hebben|nemen) .{0,40}(ontvangen|contact met je op) binnen"
    r"|reageren wij op dit moment"
    r"|binnen \d+ (werk)?dagen (beantwoord|contact)"
    r"|dit is een automatisch)", re.I)


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


def _state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save_state(state: dict) -> None:
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
    if st.get("beantwoord") or st.get("afgemeld") or st.get("bounce"):
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
    # waard dan een gesprek dat nog moet beginnen.
    rij = []
    for lead in _leads():
        beurt = _beurt(lead, state.get(lead["email"].lower()))
        if beurt:
            rij.append((lead, beurt[0], beurt[1]))
    rij.sort(key=lambda r: (r[1] == 0, -(r[0].get("ads") or 0)))
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

    def geantwoord(self, lead: dict) -> None:
        self._schrijf(lead, "heeft geantwoord op de mail",
                      {"Fase": ("select", "4. Gereageerd"),
                       "Status": ("status", "Interesse"),
                       "Volgende actie op": ("date", date.today().isoformat())})

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
            if not st.get("beantwoord"):
                st["beantwoord"] = datetime.now().isoformat(timespec="seconds")
                nieuw += 1
                if lead:
                    boek.geantwoord(lead)
                    _alarm(lead, kop, body)
            if AFMELD_WOORDEN.search(body[:400]) and not st.get("afgemeld"):
                st["afgemeld"] = True
                afgemeld += 1
                if lead:
                    boek.afgemeld(lead)

    _save_state(state)
    return nieuw, afgemeld, bounces


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
    except Exception as e:  # noqa: BLE001 — een mislukt seintje mag niets blokkeren
        print(f"  (seintje niet verstuurd: {e})")


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
    plan = json.loads(PLAN.read_text()) if PLAN.exists() else {}
    vandaag = date.today().isoformat()
    if plan.get("dag") != vandaag:
        # Wat er vandaag al met de hand is verstuurd telt mee voor het dagbudget.
        al_gedaan = sum(1 for st in state.values()
                        for v in st.get("verstuurd", []) if v["op"][:10] == vandaag)
        budget = max(0, _dagbudget(state, override) - al_gedaan)
        plan = {"dag": vandaag, "tijden": _tijdstippen(budget), "gedaan": 0,
                "al_met_de_hand": al_gedaan, "gecheckt": False}
        _save_plan(plan)
    return plan


def _save_plan(plan: dict) -> None:
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

    # Eén keer per dag de inbox nakijken, 's middags. Wie geantwoord heeft valt
    # daarmee uit de opvolging voordat de volgende mail wordt ingepland.
    if not plan.get("gecheckt") and nu >= "13:00" and state:
        try:
            nieuw, afgemeld, bounces = _check_inbox(state, boek, dagen=4)
            print(f"{datetime.now():%d-%m %H:%M} — inbox: {nieuw} antwoorden, "
                  f"{afgemeld} afmeldingen, {bounces} bounces")
        except Exception as e:  # noqa: BLE001 — een dichte inbox stopt het mailen niet
            print(f"  (inbox niet gelezen: {e})")
        plan["gecheckt"] = True
        _save_plan(plan)

    boek.afsluiten()


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

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
