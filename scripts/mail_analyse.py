#!/usr/bin/env python3
"""De klantenservicemedewerker houdt bij wat er in de post gebeurt.

WAAROM DIT BESTAAT (29-08-2026)
De rolverdeling ligt vast: Daniel is CEO, de mailagent is de klantenservice-
medewerker, Claude Code is de developer. Zie docs/team-notes.md. Daaruit volgt
dat Daniel geen mail meer hoort te lezen om te wéten wat er speelt, en dat de
mailagent en de developer onderling moeten kunnen praten in plaats van allebei
apart via hem.

Dit bestand doet daarvoor drie dingen, en niets anders:

  1. ELKE mail wordt gelezen en ingedeeld — in- én uitgaand. Wat ging erover,
     is het een klant of een lead, zit er een storing in, hoe boos is hij.
  2. Wat écht bij Daniel hoort komt op een korte lijst in het beheerdashboard:
     geld, een klant die dreigt te stoppen, een storing bij meerdere mensen, en
     alles wat de agent niet kan onderbouwen. Alleen bij spoed (geld, of iemand
     die weg dreigt te gaan) gaat er ook een mailtje uit. Zo door Daniel gekozen.
  3. Storingen worden gebundeld tot patronen met een vaste sleutel. Die lijst is
     het postvak van de developer: hij ziet welke bug hoe vaak terugkomt en wie
     hem meldde. Is hij gerepareerd, dan zet de developer dat erbij en gaat er
     bericht terug naar precies de mensen die het meldden.

GEEN NIEUWE TABEL NODIG
Alles staat in `leadgen_opslag`, dezelfde sleutel-waardetabel waar de rest van de
mailmachine al in staat. Een aparte tabel zou een handmatige migratie in Supabase
vragen, en Daniels tijd is nu juist wat dit moet besparen.

GEBRUIK
    python3 scripts/mail_analyse.py lezen          # nieuwe post indelen
    python3 scripts/mail_analyse.py escalaties     # wat er voor Daniel ligt
    python3 scripts/mail_analyse.py bugs           # het postvak van de developer
    python3 scripts/mail_analyse.py opgelost <sleutel> "wat er gerepareerd is"
"""
from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leadgen_mail as L  # noqa: E402

ANALYSE_SLEUTEL = "mail_analyse"
BUG_SLEUTEL = "bug_signalen"

# Hoeveel beoordeelde berichten we bewaren. Ver genoeg terug om een patroon te
# zien over een paar weken, krap genoeg om het document klein te houden — het
# gaat in één veld de database in.
BEWAAR_BERICHTEN = 600

# Hoeveel nieuwe berichten er per beurt beoordeeld worden. Een beurt draait elke
# tien minuten; meer dan dit is een achterstand die vanzelf inloopt, en het houdt
# de kosten en de duur van een beurt voorspelbaar.
PER_BEURT = 25

# Hoe ver terug er gekeken wordt naar nog niet beoordeelde post.
VENSTER_DAGEN = 14

# Vanaf hoeveel verschillende melders een storing een patroon heet. Eén iemand
# met een probleem is support; twee is een bug die de developer moet zien.
PATROON_VANAF = 2

# Waarvoor Daniel gestoord mag worden — door hemzelf gekozen op 29-08-2026.
# "geld" en "vertrek" zijn spoed en krijgen ook een mailtje; de rest staat
# gewoon op de lijst in het dashboard.
ESCALATIE_REDENEN = ("geld", "vertrek", "storing_bij_meerderen", "kan_niet_onderbouwen")
SPOED = ("geld", "vertrek")


# ---------------------------------------------------------------- opslag
def _lees(sleutel: str, standaard):
    try:
        return L._db_lees(sleutel, standaard)
    except Exception as e:  # noqa: BLE001
        print(f"  (kon {sleutel} niet lezen: {e})")
        return standaard


def _schrijf(sleutel: str, inhoud) -> bool:
    """Mislukt opslaan, dan zeggen we dat hard.

    Dit ging eerder stil mis met de publieke sleutel: het beoordelen lukte, de
    melding "25 berichten beoordeeld" verscheen, en er was niets opgeslagen. Dan
    lijkt het te werken terwijl de hele lijst leeg blijft.
    """
    try:
        if L._db_schrijf(sleutel, inhoud):
            return True
        print(f"  !! {sleutel} NIET opgeslagen — geen databaseverbinding")
    except Exception as e:  # noqa: BLE001
        print(f"  !! {sleutel} NIET opgeslagen: {e}")
    return False


def analyses() -> dict:
    return _lees(ANALYSE_SLEUTEL, {}) or {}


def bugs() -> dict:
    return _lees(BUG_SLEUTEL, {}) or {}


# ---------------------------------------------------------------- post ophalen
def _nieuwe_post(al_gezien: set[str]) -> list[dict]:
    """Alles uit de laatste twee weken dat nog niet beoordeeld is, in- én uitgaand.

    Uitgaande post telt mee omdat de vraag niet alleen is wat klanten schrijven,
    maar ook wat wij terugzeggen — daar zit de helft van het beeld.
    """
    host = os.environ.get("IMAP_HOST")
    gebruiker = os.environ.get("MAIL_USER")
    wachtwoord = os.environ.get("MAIL_PASS")
    if not (host and gebruiker and wachtwoord):
        return []
    sinds = L._sinds(VENSTER_DAGEN)
    uit: list[dict] = []
    try:
        with imaplib.IMAP4_SSL(host, 993) as imap:
            imap.login(gebruiker, wachtwoord)
            for map_, richting in (("INBOX", "in"), (L.MAP_BEANTWOORD, "in"),
                                    ("Verzonden", "uit")):
                if imap.select(f'"{map_}"', readonly=True)[0] != "OK":
                    continue
                _, d = imap.search(None, f"(SINCE {sinds})")
                nummers = (d[0] or b"").split()
                # Eerst alleen de koppen: daarmee weten we al wat we níet hoeven
                # op te halen, en dat is meestal het overgrote deel.
                koppen = L._koppen_in_bulk(imap, nummers)
                wil = []
                for num, kop in koppen.items():
                    mid = re.sub(r"\s+", " ", str(kop.get("Message-ID") or "")).strip()
                    if not mid or mid in al_gezien:
                        continue
                    veld = "From" if richting == "in" else "To"
                    adres = parseaddr(L._leesbaar(kop.get(veld, "")))[1].lower()
                    if not adres or L.SYSTEEM_AFZENDER.search(adres):
                        continue
                    # Onze eigen post in het postvak IN is geen klantbericht: dat
                    # zijn de seintjes die de machine aan zichzelf stuurt (het
                    # weekbericht, de trendmotor, de alarmen). Die als "binnengekomen"
                    # tellen vervuilt de thema's en de stemming meteen.
                    if richting == "in" and adres == gebruiker.lower():
                        continue
                    wil.append((num, mid, adres, kop))
                    if len(uit) + len(wil) >= PER_BEURT:
                        break
                for num, ruw in L._berichten_in_bulk(
                        imap, [n for n, *_ in wil]).items():
                    treffer = next((w for w in wil if w[0] == num), None)
                    if not treffer:
                        continue
                    _, mid, adres, kop = treffer
                    msg = email.message_from_bytes(ruw)
                    try:
                        wanneer = parsedate_to_datetime(kop.get("Date", "")).isoformat()
                    except Exception:  # noqa: BLE001
                        wanneer = datetime.now(timezone.utc).isoformat()
                    uit.append({
                        "message_id": mid,
                        "richting": richting,
                        "adres": adres,
                        "onderwerp": L._leesbaar(kop.get("Subject", "")),
                        "wanneer": wanneer,
                        "tekst": L._eigen_tekst(L._platte_tekst(msg))[:4000],
                    })
                if len(uit) >= PER_BEURT:
                    break
    except Exception as e:  # noqa: BLE001
        print(f"  (post niet gelezen: {e})")
    return uit[:PER_BEURT]


# ---------------------------------------------------------------- beoordelen
BEOORDEEL_REGELS = """Je bent de klantenservicemedewerker van Omnivaleur, een
crosslisting-app voor Marktplaats, 2dehands, Vinted, eBay en Shopify. Je leest
mail en deelt hem in. Je schrijft GEEN antwoord.

Geef per bericht exact dit terug, als één JSON-object per bericht in een lijst:

  "message_id": ongewijzigd overnemen
  "thema":      één of twee woorden, kleine letters, met streepjes. Gebruik een
                BESTAAND thema als het past; verzin er alleen een nieuw bij als
                het echt iets anders is. Bijvoorbeeld: prijs-vraag,
                publiceren-mislukt, foto-probleem, inloggen, factuur,
                afmelding, interesse, bedankje.
  "stemming":   "boos", "bezorgd", "neutraal" of "blij"
  "storing":    true als hij een probleem MELDT dat aan onze kant kan liggen
  "bug_sleutel": als storing true is, een korte vaste sleutel in kleine letters
                met streepjes die HETZELFDE is voor hetzelfde probleem, ook als
                twee mensen het anders opschrijven. Anders "".
  "escalatie":  "" als het niets voor de directeur is, anders precies één van:
                "geld"  — factuur, terugbetaling, opzegging, betaalprobleem
                "vertrek" — hij is ontevreden of dreigt te stoppen
                "kan_niet_onderbouwen" — hij vraagt iets waar wij geen antwoord
                op hebben zonder erbij te raden
  "samenvatting": één zin, hooguit 20 woorden, in gewone taal, zonder jargon.

Geef ALLEEN de JSON-lijst terug, niets eromheen."""


def _beoordeel(berichten: list[dict], bestaande_themas: list[str]) -> list[dict]:
    if not berichten:
        return []
    sleutel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not sleutel:
        print("  !! ANTHROPIC_API_KEY ontbreekt — post niet beoordeeld")
        return []
    import anthropic
    lading = [{"message_id": b["message_id"], "richting": b["richting"],
               "van_of_naar": b["adres"], "onderwerp": b["onderwerp"],
               "tekst": b["tekst"][:2000]} for b in berichten]
    prompt = (
        (f"Thema's die al bestaan, hergebruik ze waar het past:\n"
         f"{', '.join(bestaande_themas[:60])}\n\n" if bestaande_themas else "")
        + f"De berichten:\n{json.dumps(lading, ensure_ascii=False)}"
    )
    try:
        antwoord = L._claude(
            anthropic.Anthropic(api_key=sleutel),
            model=L.MODEL, max_tokens=16000,
            output_config={"effort": "low"},
            system=BEOORDEEL_REGELS,
            messages=[{"role": "user", "content": prompt}])
        tekst = "".join(b.text for b in antwoord.content
                        if getattr(b, "type", "") == "text").strip()
    except Exception as e:  # noqa: BLE001
        print(f"  !! beoordelen mislukt ({type(e).__name__}: {e})")
        return []
    # Het model zet er soms een codeblok omheen. Pak wat er tussen de eerste [
    # en de laatste ] staat; lukt dat niet, dan liever niets dan half.
    m = re.search(r"\[.*\]", tekst, re.S)
    if not m:
        print("  !! beoordeling niet te lezen — niets vastgelegd")
        return []
    try:
        rijen = json.loads(m.group(0))
    except Exception as e:  # noqa: BLE001
        print(f"  !! beoordeling niet te lezen ({e}) — niets vastgelegd")
        return []
    return [r for r in rijen if isinstance(r, dict) and r.get("message_id")]


# ---------------------------------------------------------------- bijhouden
def _verwerk(berichten: list[dict], oordelen: list[dict]) -> tuple[int, list[dict]]:
    """Oordelen wegschrijven, bugs bundelen, escalaties bepalen."""
    per_id = {b["message_id"]: b for b in berichten}
    alles = analyses()
    signalen = bugs()
    nieuw_escalaties: list[dict] = []

    for oordeel in oordelen:
        bron = per_id.get(oordeel["message_id"])
        if not bron:
            continue
        klant = L.is_klant(bron["adres"]) if bron["richting"] == "in" else False
        rij = {
            "richting": bron["richting"],
            "adres": bron["adres"],
            "onderwerp": bron["onderwerp"],
            "wanneer": bron["wanneer"],
            "klant": klant,
            "thema": str(oordeel.get("thema") or "overig")[:40],
            "stemming": str(oordeel.get("stemming") or "neutraal")[:12],
            "storing": bool(oordeel.get("storing")),
            "bug_sleutel": str(oordeel.get("bug_sleutel") or "")[:60],
            "escalatie": str(oordeel.get("escalatie") or "")[:40],
            "samenvatting": str(oordeel.get("samenvatting") or "")[:200],
        }
        alles[oordeel["message_id"]] = rij

        # Een storing van ONS uit is geen melding. Alleen wat binnenkomt telt.
        if rij["storing"] and rij["bug_sleutel"] and rij["richting"] == "in":
            s = signalen.setdefault(rij["bug_sleutel"], {
                "melders": [], "eerst": rij["wanneer"], "laatst": rij["wanneer"],
                "omschrijving": rij["samenvatting"], "status": "open",
                "gerepareerd_op": "", "uitleg": "", "bericht_verstuurd": []})
            # Was hij gerepareerd en meldt iemand hem opnieuw, dan is hij terug.
            if s.get("status") == "opgelost":
                s["status"] = "open"
                s["heropend_op"] = rij["wanneer"]
            if rij["adres"] not in s["melders"]:
                s["melders"].append(rij["adres"])
            # HET SEINTJE AAN DE DEVELOPER: dit moet met zekerheid gerepareerd,
            # niet "als het uitkomt". Drie aanleidingen, alle drie gemeten aan de
            # klant en niet aan een inschatting: hij is boos, hij dreigt te
            # stoppen, of het overkomt meer dan één iemand. De developer leest dit
            # bij het begin van elke sessie (zie CLAUDE.md).
            if (rij["stemming"] == "boos" or rij["escalatie"] == "vertrek"
                    or len(s["melders"]) >= PATROON_VANAF):
                s["moet_zeker"] = True
                redenen = set(s.get("waarom_zeker") or [])
                if rij["stemming"] == "boos":
                    redenen.add("een klant is hier boos over")
                if rij["escalatie"] == "vertrek":
                    redenen.add("een klant dreigt hierom te stoppen")
                if len(s["melders"]) >= PATROON_VANAF:
                    redenen.add(f"{len(s['melders'])} mensen melden hetzelfde")
                s["waarom_zeker"] = sorted(redenen)
            s["laatst"] = max(s.get("laatst", ""), rij["wanneer"])
            s["omschrijving"] = s.get("omschrijving") or rij["samenvatting"]

        if rij["escalatie"] in ESCALATIE_REDENEN and rij["richting"] == "in":
            nieuw_escalaties.append({**rij, "message_id": oordeel["message_id"]})

    # Een storing bij meerdere melders is geen supportvraag meer maar een bug,
    # en die hoort Daniel te weten ook als niemand erover klaagde.
    for sleutel, s in signalen.items():
        if s.get("status") != "open" or len(s.get("melders", [])) < PATROON_VANAF:
            continue
        if s.get("gemeld_als_patroon"):
            continue
        s["gemeld_als_patroon"] = datetime.now(timezone.utc).isoformat()
        nieuw_escalaties.append({
            "richting": "in", "adres": ", ".join(s["melders"][:5]),
            "onderwerp": sleutel, "wanneer": s.get("laatst", ""), "klant": True,
            "thema": sleutel, "stemming": "bezorgd", "storing": True,
            "bug_sleutel": sleutel, "escalatie": "storing_bij_meerderen",
            "samenvatting": f"{len(s['melders'])} mensen melden hetzelfde: "
                            f"{s.get('omschrijving', sleutel)}",
            "message_id": f"patroon:{sleutel}",
        })

    # Niet eindeloos laten groeien: dit gaat in één veld de database in.
    if len(alles) > BEWAAR_BERICHTEN:
        op_datum = sorted(alles.items(), key=lambda kv: kv[1].get("wanneer", ""))
        alles = dict(op_datum[-BEWAAR_BERICHTEN:])

    _schrijf(ANALYSE_SLEUTEL, alles)
    _schrijf(BUG_SLEUTEL, signalen)
    return len(oordelen), nieuw_escalaties


# ---------------------------------------------------------------- escalatie
def _spoedbericht(escalaties: list[dict]) -> None:
    """Alleen bij geld of iemand die dreigt te vertrekken. De rest staat in het
    dashboard; Daniel wil daar geen mailtje voor — zo gekozen op 29-08-2026."""
    spoed = [e for e in escalaties if e.get("escalatie") in SPOED]
    if not spoed:
        return
    host, van = os.environ.get("MAIL_HOST"), os.environ.get("MAIL_USER")
    # Op de server gaat de post via Resend en is MAIL_HOST leeg — Railway laat
    # geen SMTP door. Stond die eis hier hard, dan viel het spoedbericht juist
    # dáár stil, en precies daar draait deze machine. En als er echt niets kan,
    # zeggen we dat: een gemist seintje over geld mag nooit in stilte verdwijnen.
    if not (van and L.ALARM_NAAR) or not (host or L._resend_actief()):
        print(f"  !! {len(spoed)} spoedgeval(len) NIET gemeld — geen verzendweg "
              f"(MAIL_HOST leeg en geen RESEND_API_KEY)")
        return
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = f"Klantenservice <{van}>"
    msg["To"] = ", ".join(L.ALARM_NAAR)
    msg["Subject"] = (f"{len(spoed)} bericht(en) waar jij naar moet kijken"
                      if len(spoed) > 1 else "Eén bericht waar jij naar moet kijken")
    regels = []
    for e in spoed:
        waarom = "gaat over geld" if e["escalatie"] == "geld" else "dreigt te stoppen"
        regels.append(f"{e['adres']} ({waarom})\n  {e['samenvatting']}\n"
                      f"  Onderwerp: {e['onderwerp']}\n")
    msg.set_content(
        "Dit kon ik niet zelf afhandelen:\n\n" + "\n".join(regels)
        + "\nDe rest staat in het dashboard onder Marketing → Klantenservice.\n")
    try:
        with L._postbode(van, host) as stuur:
            stuur(msg)
        print(f"  ↳ spoedbericht gestuurd over {len(spoed)} zaak/zaken")
    except Exception as e:  # noqa: BLE001 — een gemist seintje mag niets blokkeren
        print(f"  (spoedbericht niet verstuurd: {e})")


def _bewaar_escalaties(nieuw: list[dict]) -> None:
    lijst = _lees("mail_escalaties", []) or []
    bestaand = {e.get("message_id") for e in lijst}
    for e in nieuw:
        if e.get("message_id") not in bestaand:
            lijst.append({**e, "afgehandeld": False,
                          "gezien_op": datetime.now(timezone.utc).isoformat()})
    # Afgehandelde zaken van meer dan een maand oud hoeven niet te blijven staan.
    grens = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    lijst = [e for e in lijst
             if not e.get("afgehandeld") or e.get("gezien_op", "") > grens]
    _schrijf("mail_escalaties", lijst)


# ---------------------------------------------------------------- commando's
def lezen(args) -> dict:
    """Eén ronde: nieuwe post beoordelen, bugs bundelen, escalaties bepalen."""
    al = analyses()
    berichten = _nieuwe_post(set(al))
    if not berichten:
        return {"gelezen": 0, "escalaties": 0}
    themas = sorted({r.get("thema", "") for r in al.values() if r.get("thema")})
    oordelen = _beoordeel(berichten, themas)
    aantal, nieuw = _verwerk(berichten, oordelen)
    if nieuw:
        _bewaar_escalaties(nieuw)
        _spoedbericht(nieuw)
    print(f"  {aantal} bericht(en) beoordeeld, {len(nieuw)} voor Daniel")
    return {"gelezen": aantal, "escalaties": len(nieuw)}


def escalaties(args) -> None:
    lijst = [e for e in (_lees("mail_escalaties", []) or []) if not e.get("afgehandeld")]
    if not lijst:
        print("Niets wat jouw aandacht nodig heeft.")
        return
    for e in lijst:
        print(f"[{e.get('escalatie')}] {e.get('adres')}\n    {e.get('samenvatting')}")


def bugs_tonen(args) -> None:
    """Het postvak van de developer: welke storing komt hoe vaak terug."""
    signalen = bugs()
    open_ = {k: v for k, v in signalen.items() if v.get("status") == "open"}
    if not open_:
        print("Geen openstaande storingen gemeld.")
        return
    for sleutel, s in sorted(open_.items(),
                             key=lambda kv: -len(kv[1].get("melders", []))):
        melders = s.get("melders", [])
        merk = "  ⚠ MOET ZEKER" if s.get("moet_zeker") else ""
        print(f"\n{sleutel}  ({len(melders)} melder(s), "
              f"laatst {s.get('laatst','')[:10]}){merk}")
        if s.get("waarom_zeker"):
            print(f"    waarom met voorrang: {', '.join(s['waarom_zeker'])}")
        print(f"    {s.get('omschrijving','')}")
        print(f"    gemeld door: {', '.join(melders[:8])}")


def vraag_voor_daniel(adres: str, vraag: str, aanleiding: str = "") -> bool:
    """De klantenservice komt er niet uit — leg de vraag bij Daniel neer.

    WAAROM DIT BESTAAT (29-08-2026). Jaap vroeg of zijn computer aan moet blijven
    staan bij het verversen. Het antwoord staat gewoon in de code, maar het
    concept zei "ik kijk het na". Zo'n zin is voor de klant hetzelfde als geen
    antwoord, en er komt niets van terecht: hij staat in een concept dat Daniel
    verstuurt en daarna nergens meer.

    Kan de agent een feitelijke vraag écht niet onderbouwen, dan hoort hij dus
    geen mail te schrijven maar de vraag hier neer te leggen — op de lijst die
    Daniel al leest. Geen mailtje: dit is geen spoed, het is werk.
    """
    vraag = (vraag or "").strip()
    if not vraag:
        return False
    rij = {
        "richting": "in", "adres": adres or "onbekend",
        "onderwerp": (aanleiding or vraag)[:120],
        "wanneer": datetime.now(timezone.utc).isoformat(), "klant": True,
        "thema": "vraag-voor-daniel", "stemming": "neutraal", "storing": False,
        "bug_sleutel": "", "escalatie": "kan_niet_onderbouwen",
        "samenvatting": vraag[:200],
        # Dezelfde vraag van dezelfde persoon is één keer genoeg. Zonder deze
        # sleutel komt hij bij elke ronde opnieuw op de lijst.
        "message_id": f"vraag:{adres}:{re.sub(r'[^a-z0-9]+', '-', vraag.lower())[:60]}",
    }
    _bewaar_escalaties([rij])
    return True


def afgewezen(args) -> None:
    """Deze storing gaan we niet repareren, en dat is een besluit.

    Zonder deze knop blijft een sleutel voor altijd op de lijst staan en blijft de
    automatische starter (scripts/dev_starter.py) hem als openstaand werk zien.
    """
    signalen = bugs()
    s = signalen.get(args.sleutel)
    if not s:
        print(f"Geen storing bekend onder '{args.sleutel}'. "
              f"Bekend: {', '.join(sorted(signalen)) or 'geen'}")
        return
    s["status"] = "afgewezen"
    s["afgewezen_op"] = datetime.now(timezone.utc).isoformat()
    s["reden"] = args.reden
    s.pop("gemeld_als_patroon", None)
    _schrijf(BUG_SLEUTEL, signalen)
    print(f"'{args.sleutel}' staat op afgewezen: {args.reden}")


def opgelost(args) -> None:
    """De developer meldt terug dat het gerepareerd is.

    Dit is de terugweg van de lijn developer → klantenservice: de mailagent weet
    daarna precies wie erover schreef, en kan die mensen bericht sturen.
    """
    signalen = bugs()
    s = signalen.get(args.sleutel)
    if not s:
        print(f"Geen storing bekend onder '{args.sleutel}'. "
              f"Bekend: {', '.join(sorted(signalen)) or 'geen'}")
        return
    s["status"] = "opgelost"
    s["gerepareerd_op"] = datetime.now(timezone.utc).isoformat()
    s["uitleg"] = args.uitleg
    s.pop("gemeld_als_patroon", None)
    _schrijf(BUG_SLEUTEL, signalen)
    print(f"'{args.sleutel}' staat op opgelost. "
          f"{len(s.get('melders', []))} melder(s) krijgen bericht: "
          f"{', '.join(s.get('melders', [])[:8])}")


# ------------------------------------------- wat de developer zegt, telt
def stand_van_de_storingen(tekst: str) -> str:
    """Wat de developer over dit onderwerp heeft laten weten, als vaste tekst
    voor het concept.

    DIT IS DE LIJN DEVELOPER -> KLANTENSERVICE -> KLANT.
    Zonder dit schrijft de klantenservice een antwoord op basis van de mail
    alleen, en dan zegt hij "ik kijk ernaar" terwijl de developer het gisteren
    heeft gerepareerd — of erger, hij belooft een reparatie die niemand aan het
    bouwen is. Wat hier staat is niet zijn inschatting maar wat er werkelijk is
    vastgelegd: open, in behandeling, of klaar met de uitleg erbij.
    """
    laag = (tekst or "").lower()
    if not laag:
        return ""
    regels = []
    for sleutel, s in (bugs() or {}).items():
        # Een sleutel als "publiceren-mislukt-vinted" herkennen we aan de losse
        # woorden; die staan in de mail zelden achter elkaar.
        woorden = [w for w in re.split(r"[-_]", sleutel) if len(w) >= 4]
        if not woorden or not all(w in laag for w in woorden[:2]):
            continue
        if s.get("status") == "opgelost" and s.get("uitleg"):
            regels.append(f"- '{sleutel}' IS GEREPAREERD. Wat er is aangepast: "
                          f"{s['uitleg']} Zeg dat het opgelost is en vraag of het "
                          f"bij hem ook echt weg is.")
        elif s.get("moet_zeker"):
            regels.append(f"- '{sleutel}' is bekend en staat bovenaan bij de "
                          f"ontwikkeling ({', '.join(s.get('waarom_zeker') or [])}). "
                          f"Zeg dat het bekend is en met voorrang wordt opgepakt. "
                          f"Beloof GEEN datum.")
        elif s.get("status") == "open":
            regels.append(f"- '{sleutel}' is bekend en gemeld door "
                          f"{len(s.get('melders') or [])} mens(en). Zeg dat het bekend "
                          f"is en dat ernaar gekeken wordt. Beloof GEEN datum.")
    if not regels:
        return ""
    return ("\n\nWAT DE ONTWIKKELING HIEROVER HEEFT VASTGELEGD — dit is de "
            "waarheid, ga hier niet vanaf en verzin er niets bij:\n"
            + "\n".join(regels[:3]))


# ---------------------------------------------------------------- terugweg
HERSTELBERICHT_REGELS = """Je bent Daniel de Koning van Omnivaleur en je schrijft
in de ik-vorm aan een klant die eerder een probleem meldde. Het is nu opgelost.

- Begin met erkennen wat hij meldde en dat hij de moeite nam het door te geven.
- Zeg in gewone taal wat er nu anders is, in gevolgen die hij merkt. Geen techniek.
- Beweer niets meer dan wat er hieronder staat als reparatie. Verzin geen extra's.
- Kort: vier tot zeven zinnen. Informeel Nederlands, "Hi <naam>," en aan het eind
  het meegegeven ondertekeningsblok, letterlijk.
- Vraag hem of het bij hem ook echt weg is.
Schrijf alleen de mailtekst."""


def bericht_over_reparaties() -> int:
    """Wie een storing meldde die nu gerepareerd is, hoort dat te weten.

    Dit is de terugweg developer -> klantenservice -> klant. Zonder dit blijft een
    reparatie onzichtbaar voor precies de mensen die de moeite namen hem te
    melden, en die melden de volgende keer niets meer.
    """
    signalen = bugs()
    gemaakt = 0
    for sleutel, s in signalen.items():
        if s.get("status") != "opgelost" or not s.get("uitleg"):
            continue
        verstuurd = set(s.get("bericht_verstuurd") or [])
        for adres in s.get("melders", []):
            if adres in verstuurd:
                continue
            tekst = _herstelbericht(adres, s)
            if not tekst:
                continue
            # Via de gewone weg, dus langs het slot: nooit een tweede concept
            # voor iemand die er al een heeft liggen.
            if L._zet_concept_klaar({"email": adres}, None, "", eigen_tekst=tekst):
                verstuurd.add(adres)
                gemaakt += 1
        s["bericht_verstuurd"] = sorted(verstuurd)
    if gemaakt:
        _schrijf(BUG_SLEUTEL, signalen)
    return gemaakt


def _herstelbericht(adres: str, signaal: dict) -> str:
    sleutel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not sleutel:
        return ""
    import anthropic
    try:
        antwoord = L._claude(
            anthropic.Anthropic(api_key=sleutel),
            model=L.MODEL, max_tokens=16000,
            output_config={"effort": "low"},
            system=HERSTELBERICHT_REGELS,
            messages=[{"role": "user", "content":
                       f"Wat hij meldde: {signaal.get('omschrijving','')}\n"
                       f"Wat er gerepareerd is: {signaal.get('uitleg','')}\n\n"
                       f"Sluit af met exact dit blok:\n{L._ondertekening()}"}])
        tekst = "".join(b.text for b in antwoord.content
                        if getattr(b, "type", "") == "text").strip()
    except Exception as e:  # noqa: BLE001
        print(f"  !! herstelbericht voor {adres} mislukt ({type(e).__name__}: {e})")
        return ""
    # Te kort is geen bericht; dan liever niets dan iets halfs in de map.
    return tekst if len(tekst.split()) >= 15 else ""


def _omgeving_uit_env_bestand() -> None:
    """Voor gebruik vanaf de opdrachtregel: de sleutels uit .env oppikken.

    Op de server staan ze al in de omgeving. Lokaal wil de developer gewoon
    `python3 scripts/mail_analyse.py bugs` kunnen typen zonder eerst zes
    variabelen te exporteren; anders wordt dit postvak niet gelezen, en dan is
    de hele lijn klantenservice -> developer een dode letter.
    """
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"):
        return
    pad = Path(__file__).resolve().parent.parent / ".env"
    if not pad.is_file():
        return
    for regel in pad.read_text(errors="replace").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        naam, waarde = regel.split("=", 1)
        os.environ.setdefault(naam.strip(), waarde.strip().strip('"').strip("'"))
    # De schrijfsleutel gaat vóór de publieke. Met de publieke sleutel lukt lezen
    # wel en schrijven niet, en dan is `opgelost` een dode knop die zegt dat het
    # gelukt is terwijl er niets is opgeslagen.
    for wissel in ("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        if os.environ.get(wissel):
            os.environ["SUPABASE_KEY"] = os.environ[wissel]
            break


def main() -> None:
    _omgeving_uit_env_bestand()
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lezen", help="nieuwe post beoordelen").set_defaults(func=lezen)
    sub.add_parser("escalaties", help="wat er voor Daniel ligt").set_defaults(func=escalaties)
    sub.add_parser("bugs", help="het postvak van de developer").set_defaults(func=bugs_tonen)
    sub.add_parser("terugkoppelen", help="melders bericht sturen over reparaties"
                   ).set_defaults(func=lambda a: print(f"{bericht_over_reparaties()} bericht(en) klaargezet"))
    o = sub.add_parser("opgelost", help="een storing als gerepareerd melden")
    o.add_argument("sleutel")
    o.add_argument("uitleg", help="één zin voor de klant, in gewone taal")
    o.set_defaults(func=opgelost)
    w = sub.add_parser("afgewezen", help="een storing bewust niet repareren")
    w.add_argument("sleutel")
    w.add_argument("reden", help="waarom niet, in één zin")
    w.set_defaults(func=afgewezen)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
