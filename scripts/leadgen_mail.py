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
# ---------------------------------------------------------------------------

# Opbouwschema: het aantal mails per dag, geteld vanaf je eerste verzenddag. Een
# nieuw domein dat op dag één honderd mails uitstuurt is een nieuw domein dat op
# dag twee op een zwarte lijst staat.
RAMP = [(1, 5), (4, 10), (8, 15), (12, 25)]
FOLLOWUP_DAGEN = (5, 12)      # opvolgmail 1 en 2, in dagen na de vorige mail
PAUZE = (40, 110)             # seconden tussen twee mails, willekeurig

AFMELD_WOORDEN = re.compile(
    r"\b(stop|afmelden|uitschrijven|unsubscribe|geen interesse|niet meer mailen)\b",
    re.I)
BOUNCE_AFZENDERS = re.compile(r"mailer-daemon|postmaster|no-?reply", re.I)


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


def _leads() -> list[dict]:
    """Marktplaats-leads eerst; die hebben een e-mailadres en de meeste voorraad."""
    alles = [l for l in _load(MP_LEADS) + _load(IG_LEADS) if l.get("email")]
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
    zet dat in `je_jullie`; alle voornaamwoorden in de mail komen hiervandaan,
    zodat er nooit "jullie ziet" of "je kunnen" uit rolt."""
    if (lead.get("je_jullie") or "Je") == "Je":
        return dict(jij="je", jij_nadruk="jij", jou="je", jouw="je",
                    jij_kunt="Je kunt", zit_je="zit je", jij_ziet="Je ziet",
                    jij_verkoopt="je verkoopt", jij_hebt="je hebt",
                    jij_verdubbelt="verdubbelt", ziet_jij="je ziet")
    return dict(jij="jullie", jij_nadruk="jullie", jou="jullie", jouw="jullie",
                jij_kunt="Jullie kunnen", zit_je="zitten jullie", jij_ziet="Jullie zien",
                jij_verkoopt="jullie verkopen", jij_hebt="jullie hebben",
                jij_verdubbelt="verdubbelen", ziet_jij="jullie zien")


def _rond(n: int) -> str:
    """"14.431 advertenties" leest als een uitdraai uit een database, en dat is het
    ook. Afronden leest als iemand die even gekeken heeft."""
    if n >= 10000:
        return f"ruim {n // 1000}.000"
    if n >= 1000:
        return f"ruim {n // 100 * 100:,}".replace(",", ".")
    return f"zo'n {n // 10 * 10}"


def _haakje(lead: dict) -> str:
    """De openingszin die deze mail over déze handelaar laat gaan. Zonder zoiets
    is het een rondzendbrief en dat ziet iedereen. We gebruiken wat we van hem
    weten: rubriek, aantal advertenties, eigen webshop en webshopsysteem."""
    v = _jij(lead)
    ads = lead.get("ads") or 0
    rubriek = (lead.get("verkoopt_vooral") or "").strip().lower()
    site = (lead.get("site") or "").replace("https://", "").replace(
        "http://", "").replace("www.", "").rstrip("/")
    shop = lead.get("shopsysteem")

    # De classificatie zet hier soms "Alles" of "Antieke vintage" neer. Alleen een
    # rubriek die als los zelfstandig naamwoord in een zin past mag erin; de rest
    # wordt "van alles", want een rare zin valt meer op dan een vage zin.
    wat = f"veel {rubriek}" if rubriek in RUBRIEKEN else "van alles"
    if ads >= 100:
        zin = (f"Zag dat {v['jij']} {wat} {v['jij_verkoopt'].split()[-1]} op "
               f"Marktplaats, {_rond(ads)} advertenties inmiddels. Nice.")
    else:
        zin = (f"Zag dat {v['jij']} {wat} "
               f"{v['jij_verkoopt'].split()[-1]} op Marktplaats, nice.")

    if site and shop:
        zin += f" En {v['jouw']} eigen shop op {site} draait op {shop}, zie ik."
    elif site:
        zin += f" En {v['jij']} {v['jij_hebt'].split()[-1]} daarnaast een eigen shop op {site}."
    return zin


MAIL1 = """{aanhef} {naam},

{haakje}

Ik help met {bedrijf} verkopers zoals {jij_nadruk} om {jouw} aanbod automatisch
door te plaatsen naar alle relevante marketplaces, zodat {jij} direct {jouw}
bereik {jij_verdubbelt} zonder extra werk. Zelf draai ik 700+ reviews met
Revaleur en help ik hier al 38 resellers mee.

{jij_kunt} het 7 dagen gratis uitproberen. Bespaart het {jou} niet meteen uren
werk per week, dan {zit_je} nergens aan vast.

Zal ik {jou} een video van 1 minuut sturen waarin {ziet_jij} hoe makkelijk het
werkt?

{ondertekening}"""

MAIL2 = """{aanhef} {naam},

Korte vraag naar aanleiding van mijn vorige mail: hoeveel tijd {zit_je} nu per
week kwijt aan het overzetten van advertenties naar andere platforms?

Is het antwoord "te veel", dan stuur ik {jou} alsnog graag die video van een
minuut. {jij_ziet} in één oogopslag wat {bedrijf} daarvan overneemt.

{jij_kunt} het daarna 7 dagen gratis proberen, zonder verplichtingen.

{ondertekening}"""

MAIL3 = """{aanhef} {naam},

Laatste bericht van mijn kant, ik laat het verder rusten.

Mocht het later toch gaan spelen dat {jouw} voorraad op meer plekken moet staan
zonder dat het dubbel werk wordt: {site}. Eén mailtje en ik denk mee.

Succes met de zaak.

{ondertekening}"""

ONDERTEKENING = """Groet,
{naam}
{bedrijf} · {site}

{bedrijf} · {adres} · KvK {kvk}
Liever geen mail meer? Antwoord met "stop" en ik haal {jou} uit de lijst."""

BEURTEN = [
    ("mail1", "Vraagje over je Marktplaats-aanbod", MAIL1),
    ("mail2", "Re: vraagje over je Marktplaats-aanbod", MAIL2),
    ("mail3", "Laatste bericht", MAIL3),
]


def _tekst(lead: dict, sjabloon: str) -> str:
    naam = _bedrijfsnaam(lead)
    return sjabloon.format(
        aanhef=_aanhef(lead),
        naam=naam.split()[0] if naam and len(naam.split()) == 1 else naam,
        haakje=_haakje(lead),
        bedrijf=BEDRIJF,
        site=SITE,
        **_jij(lead),
        ondertekening="\x00" + ONDERTEKENING.format(
            naam=AFZENDER_NAAM, bedrijf=BEDRIJF, site=SITE,
            adres=BEDRIJF_ADRES, kvk=BEDRIJF_KVK, jou=_jij(lead)["jou"]),
    )


def _netjes(tekst: str) -> str:
    """Alinea's op 78 tekens afbreken. De ondertekening (na \x00) blijft zoals hij
    is: daar zijn de regelafbrekingen betekenisvol."""
    body, _, staart = tekst.partition("\x00")
    alineas = [textwrap.fill(a.strip(), 78) for a in body.split("\n\n") if a.strip()]
    return "\n\n".join(alineas) + "\n\n" + staart


# --------------------------------------------------------------------- plan


def _dagnummer(state: dict) -> int:
    """De hoeveelste verzenddag dit is. Bepaalt hoeveel mails eruit mogen."""
    dagen = {v["laatste"][:10] for v in state.values() if v.get("laatste")}
    return len(dagen) + 1


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


def _bericht(lead: dict, n: int, van: str) -> EmailMessage:
    onderwerp, sjabloon = BEURTEN[n][1], BEURTEN[n][2]
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
        print(f"Voorbeeld — {BEURTEN[n][1]}\naan: {lead['email']}\n")
        print(_netjes(_tekst(lead, BEURTEN[n][2])))
        print("\n" + "-" * 60)
        for lead, n, waarom in rij:
            print(f"  {BEURTEN[n][0]}  {lead['email']:38s} {waarom}")
        return

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
            print(f"  → {BEURTEN[n][0]} {lead['email']}", flush=True)
            if i < len(rij) - 1:
                time.sleep(random.uniform(*PAUZE))

    print(f"\n{verstuurd} mails verstuurd. Morgen weer — draai 'check' voor antwoorden.")


# -------------------------------------------------------------------- check


def check(args) -> None:
    """Antwoorden, afmeldingen en bounces ophalen. Wie antwoordt krijgt geen
    opvolgmail meer; dat is het verschil tussen opvolgen en zeuren."""
    host, gebruiker = _need("IMAP_HOST"), _need("MAIL_USER")
    state = _state()
    if not state:
        sys.exit("Nog niets verstuurd.")

    sinds = (date.today() - timedelta(days=args.dagen)).strftime("%d-%b-%Y")
    nieuw = afgemeld = bounces = 0
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
                continue

            st = state.get(afzender)
            if not st:
                continue
            if not st.get("beantwoord"):
                st["beantwoord"] = datetime.now().isoformat(timespec="seconds")
                nieuw += 1
            if AFMELD_WOORDEN.search(body[:400]) and not st.get("afgemeld"):
                st["afgemeld"] = True
                afgemeld += 1

    _save_state(state)
    print(f"{nieuw} nieuwe antwoorden, {afgemeld} afmeldingen, {bounces} bounces.")
    if nieuw:
        print("\nWie heeft geantwoord:")
        for adres, st in state.items():
            if st.get("beantwoord", "").startswith(date.today().isoformat()):
                print(f"  {st.get('bedrijf') or adres} — {adres}")


def _platte_tekst(msg) -> str:
    if not msg.is_multipart():
        return msg.get_payload(decode=True).decode(errors="ignore")
    for deel in msg.walk():
        if deel.get_content_type() == "text/plain":
            return deel.get_payload(decode=True).decode(errors="ignore")
    return ""


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

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
