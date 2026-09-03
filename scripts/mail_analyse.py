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
import base64
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

# Hoeveel schermafbeeldingen er per bericht meegaan naar het model, en hoe groot
# ze dan nog zijn. Twee is genoeg: de derde foto is bijna altijd hetzelfde scherm
# vanuit een andere hoek, en elke foto kost geld en tijd in elke ronde.
MAX_AFBEELDINGEN = 2
AFBEELDING_MAX_PX = 1400

# Woorden die niets zeggen over wélke storing het is. Ze staan in bijna elke
# sleutel die het model bedenkt en maken twee sleutels voor hetzelfde probleem
# kunstmatig verschillend ("admarkt-import-fout" naast "admarkt-import-mislukt").
SLEUTELRUIS = frozenset({
    "mislukt", "mislukte", "fout", "fouten", "foutmelding", "foutmeldingen",
    "probleem", "problemen", "niet", "geen", "werkt", "gaat", "bij", "van",
    "de", "het", "een", "met", "op", "in", "is", "wordt", "worden", "klopt",
})

# Vanaf hoeveel overlap twee sleutels dezelfde storing heten. 0,6 is bewust hoog:
# liever twee sleutels voor één storing dan één sleutel voor twee storingen — dat
# laatste stuurt de developer op pad voor een probleem dat niemand meldde.
SLEUTEL_GELIJKENIS = 0.6

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


def _bereikbaar() -> str:
    """Lege string als de opslag werkt, anders waaróm niet.

    WAAROM DIT ER IS (31-08-2026). `_lees` hierboven geeft bij een storing de
    lege standaard terug, en dat is voor tonen precies goed — maar voor
    beoordelen levensgevaarlijk. "Welke post is al beoordeeld?" wordt dan
    namelijk óók leeg beantwoord, waarna de ronde ALLE post van veertien dagen
    opnieuw langs het model haalt, opnieuw escalatiemails verstuurt over
    berichten van vorige week, en het resultaat vervolgens niet kan opslaan.
    Elke tien minuten opnieuw. Dat is precies de dubbele meldingen waar Daniel
    op 31-08 over klaagde, en het kost bij elke ronde geld.
    """
    try:
        L._db_lees(ANALYSE_SLEUTEL, {})
    except Exception as e:  # noqa: BLE001
        return str(e)
    return ""


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
def _verklein(ruw: bytes) -> bytes | None:
    """Een meegestuurde foto terugbrengen tot iets wat door de leiding past.

    De API weigert een afbeelding boven de 5 MB, en een telefoonfoto zit daar zo
    overheen. Lukt verkleinen niet, dan gaat het origineel alleen mee als het uit
    zichzelf klein genoeg is: één geweigerde aanroep kost de hele ronde, en dan
    wordt er van vijfentwintig berichten niet één beoordeeld.
    """
    try:
        import io

        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(ruw)) as afb:
            afb = (ImageOps.exif_transpose(afb) or afb).convert("RGB")
            afb.thumbnail((AFBEELDING_MAX_PX, AFBEELDING_MAX_PX))
            buf = io.BytesIO()
            afb.save(buf, format="JPEG", quality=75)
            return buf.getvalue()
    except Exception as e:  # noqa: BLE001
        print(f"  (afbeelding niet verkleind: {e})")
        return ruw if len(ruw) < 3_500_000 else None


def _afbeeldingen(msg) -> list[dict]:
    """De schermafbeeldingen uit een mail, klaar om aan het model te geven.

    WAAROM DIT BESTAAT (30-08-2026). Amanda stuurde een foto van de melding
    "Publishing failed (HTTP 500): Internal Server Error". In de tekst van haar
    mail stond alleen "ik stuur een foto mee van de melding" — verder niets. Hier
    werd uitsluitend de platte tekst gelezen, dus wat er op die foto stond is
    nooit ergens aangekomen: niet op de lijst van de developer, en dus ook niet
    bij Daniel. Egbert deed twee keer hetzelfde met een importfout.

    Een foutmelding op een foto is nog steeds een foutmelding.
    """
    uit: list[dict] = []
    for deel in msg.walk():
        if deel.get_content_maintype() != "image":
            continue
        try:
            ruw = deel.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001
            continue
        klein = _verklein(ruw) if ruw else None
        if not klein:
            continue
        uit.append({"media_type": "image/jpeg",
                    "data": base64.b64encode(klein).decode("ascii")})
        if len(uit) >= MAX_AFBEELDINGEN:
            break
    return uit


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
                        # Alleen bij binnenkomende post: onze eigen uitgaande
                        # mail bevat hooguit ons eigen logo.
                        "afbeeldingen": _afbeeldingen(msg) if richting == "in" else [],
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
                NEEM EEN BESTAANDE SLEUTEL UIT DE LIJST HIERONDER zodra het over
                hetzelfde probleem gaat. Een nieuwe sleutel verzinnen voor iets
                wat er al staat is de duurste fout die je hier kunt maken: dan
                telt de storing als één melder, komt hij nooit boven aan de lijst
                en gaat niemand hem repareren. Verzin alleen een nieuwe sleutel
                als geen enkele bestaande erop past.
  "foutmelding": de foutmelding LETTERLIJK zoals hij er staat, als de klant er
                een noemt of er een schermafbeelding bij zit. Neem cijfers en
                codes precies over ("Publishing failed (HTTP 500): Internal
                Server Error"). Staat er geen foutmelding, dan "".
  "escalatie":  "" als het niets voor de directeur is, anders precies één van:
                "geld"  — factuur, terugbetaling, opzegging, betaalprobleem
                "vertrek" — hij is ontevreden of dreigt te stoppen
                "kan_niet_onderbouwen" — hij vraagt iets waar wij geen antwoord
                op hebben zonder erbij te raden
  "samenvatting": één zin, hooguit 20 woorden, in gewone taal, zonder jargon.

BIJLAGEN. Bij sommige berichten zitten schermafbeeldingen; die krijg je erbij,
met de message_id erboven. Lees wat erop staat. Klanten sturen vaak alleen een
foto met de zin "hier is de melding" erbij — de storing staat dan volledig op die
foto en nergens anders. Wat je op zo'n foto ziet telt precies zo zwaar als tekst:
zie je een foutmelding, dan is "storing" true en gaat de tekst in "foutmelding".

Geef ALLEEN de JSON-lijst terug, niets eromheen."""


def _beoordeel(berichten: list[dict], bestaande_themas: list[str],
               bestaande_sleutels: list[str] | None = None) -> list[dict]:
    if not berichten:
        return []
    sleutel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not sleutel:
        print("  !! ANTHROPIC_API_KEY ontbreekt — post niet beoordeeld")
        return []
    import anthropic
    lading = [{"message_id": b["message_id"], "richting": b["richting"],
               "van_of_naar": b["adres"], "onderwerp": b["onderwerp"],
               "tekst": b["tekst"][:2000],
               "bijlagen": len(b.get("afbeeldingen") or [])} for b in berichten]
    prompt = (
        (f"Thema's die al bestaan, hergebruik ze waar het past:\n"
         f"{', '.join(bestaande_themas[:60])}\n\n" if bestaande_themas else "")
        # De bestaande bugsleutels MOETEN mee. Zonder deze lijst kon het model
        # onmogelijk hergebruiken wat het niet kende, en verzon het bij elke mail
        # een nieuwe sleutel: op 30-08-2026 stonden er 45 sleutels waarvan 44 met
        # precies één melder, met vier verschillende namen voor dezelfde
        # Admarkt-importfout. Daardoor haalde vrijwel niets ooit de grens van
        # twee melders, kreeg vrijwel niets "MOET ZEKER", en startte de
        # automatische starter voor vrijwel niets een sessie.
        + (f"Bugsleutels die al bestaan. Gebruik er één van zodra het over "
           f"hetzelfde probleem gaat:\n{', '.join(sorted(bestaande_sleutels)[:120])}\n\n"
           if bestaande_sleutels else "")
        + f"De berichten:\n{json.dumps(lading, ensure_ascii=False)}"
    )
    inhoud: list[dict] = [{"type": "text", "text": prompt}]
    for b in berichten:
        for afb in b.get("afbeeldingen") or []:
            inhoud.append({"type": "text",
                           "text": f"Schermafbeelding bij message_id {b['message_id']}:"})
            inhoud.append({"type": "image",
                           "source": {"type": "base64",
                                      "media_type": afb["media_type"],
                                      "data": afb["data"]}})
    try:
        antwoord = L._claude(
            anthropic.Anthropic(api_key=sleutel),
            model=L.MODEL, max_tokens=16000,
            output_config={"effort": "low"},
            system=BEOORDEEL_REGELS,
            messages=[{"role": "user", "content": inhoud}])
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
def _kern(sleutel: str) -> frozenset:
    """De betekenisdragende woorden van een sleutel."""
    return frozenset(w for w in re.split(r"[^a-z0-9]+", (sleutel or "").lower())
                     if w and w not in SLEUTELRUIS)


def _bestaande_sleutel(nieuw: str, signalen: dict) -> str:
    """Valt deze sleutel samen met eentje die er al staat? Dan die gebruiken.

    Het model krijgt de bestaande sleutels nu mee, maar het blijft een model: het
    schrijft alsnog "admarkt-import-mislukt" naast "admarkt-import-fout". Twee
    sleutels voor één storing betekent twee keer één melder, en dus nooit
    voorrang. Dit is het vangnet daaronder.

    Een sleutel die bewust is AFGEWEZEN blijft buiten schot: daar is een besluit
    over genomen, en een nieuwe melding hoort dat besluit niet stilletjes terug
    te draaien.
    """
    kern = _kern(nieuw)
    if not kern:
        return nieuw
    beste, hoogste = nieuw, 0.0
    for bestaand, s in signalen.items():
        if bestaand == nieuw:
            return nieuw
        if s.get("status") == "afgewezen":
            continue
        andere = _kern(bestaand)
        if not andere:
            continue
        gelijkenis = len(kern & andere) / len(kern | andere)
        if gelijkenis > hoogste:
            beste, hoogste = bestaand, gelijkenis
    return beste if hoogste >= SLEUTEL_GELIJKENIS else nieuw


# Een serverfout is geen inschatting maar bewijs: er ging iets stuk aan ONZE kant.
_SERVERFOUT = re.compile(r"\b(http\s*)?5\d{2}\b|internal server error", re.I)


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
            "foutmelding": str(oordeel.get("foutmelding") or "")[:300],
        }
        if rij["bug_sleutel"]:
            rij["bug_sleutel"] = _bestaande_sleutel(rij["bug_sleutel"], signalen)
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
            # De letterlijke foutmelding erbij bewaren. Die staat vaak alleen op
            # een meegestuurde schermafbeelding, en juist die tekst is wat de
            # developer nodig heeft om de fout terug te vinden.
            if rij["foutmelding"]:
                meldingen = s.setdefault("foutmeldingen", [])
                if rij["foutmelding"] not in meldingen:
                    meldingen.append(rij["foutmelding"])
                del meldingen[:-5]
            # HET SEINTJE AAN DE DEVELOPER: dit moet met zekerheid gerepareerd,
            # niet "als het uitkomt". Drie aanleidingen, alle drie gemeten aan de
            # klant en niet aan een inschatting: hij is boos, hij dreigt te
            # stoppen, of het overkomt meer dan één iemand. De developer leest dit
            # bij het begin van elke sessie (zie CLAUDE.md).
            # Een serverfout hoort hier ook bij, en die stond er niet in. Amanda
            # kreeg op 30-08-2026 "Publishing failed (HTTP 500)" te zien en bleef
            # er vriendelijk onder — niet boos, niet vertrekkend, de enige melder.
            # Dus bleef het staan als gewone support terwijl publiceren voor haar
            # gewoon stuk was. Toon is geen maat voor ernst: een 500 is bewijs dat
            # er iets aan onze kant kapot is.
            serverfout = bool(_SERVERFOUT.search(rij["foutmelding"]))
            if (rij["stemming"] == "boos" or rij["escalatie"] == "vertrek"
                    or serverfout or len(s["melders"]) >= PATROON_VANAF):
                s["moet_zeker"] = True
                redenen = set(s.get("waarom_zeker") or [])
                if rij["stemming"] == "boos":
                    redenen.add("een klant is hier boos over")
                if rij["escalatie"] == "vertrek":
                    redenen.add("een klant dreigt hierom te stoppen")
                if serverfout:
                    redenen.add("de server gaf een interne fout terug")
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
    kapot = _bereikbaar()
    if kapot:
        # Niet doorwerken op een leeg beeld — zie _bereikbaar hierboven.
        print(f"  !! de administratie is niet te lezen, deze ronde slaat over: {kapot}")
        return {"gelezen": 0, "escalaties": 0, "storing": kapot}
    al = analyses()
    berichten = _nieuwe_post(set(al))
    if not berichten:
        return {"gelezen": 0, "escalaties": 0}
    themas = sorted({r.get("thema", "") for r in al.values() if r.get("thema")})
    oordelen = _beoordeel(berichten, themas, list(bugs()))
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
    # Uitgedoofde meldingen blijven zichtbaar. Werk dat stilletjes verdwijnt is
    # net zo erg als werk dat eeuwig blijft staan: als hier iets tussen staat
    # dat wél nog speelt, moet dat opvallen en teruggezet kunnen worden.
    doof = {k: v for k, v in signalen.items() if v.get("status") == "verlopen"}
    if doof:
        print(f"({len(doof)} melding(en) uitgedoofd omdat ze niet meer speelden — "
              f"niemand kreeg daar bericht van:)")
        for sleutel, s in sorted(doof.items(),
                                 key=lambda kv: str(kv[1].get("verlopen_op", "")))[-5:]:
            print(f"    ⌛ {sleutel} — {s.get('reden', '')}")
        print()
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
        for melding in (s.get("foutmeldingen") or [])[:3]:
            print(f"    foutmelding: {melding}")
        print(f"    gemeld door: {', '.join(melders[:8])}")


def fouten_tonen(args) -> None:
    """Wat er op de server stukging, met de code die de klant op zijn scherm zag.

    WAAROM DIT BESTAAT (30-08-2026). Een onverwachte fout in de server leverde de
    klant "HTTP 500: Internal Server Error" op en liet verder NERGENS een spoor
    na: niet in de database, niet in een lijst, alleen in de logregels van de
    container die na een herstart weg zijn. Amanda kon daardoor niet publiceren
    zonder dat iemand ooit kon zien waaróm. Nu krijgt elke onverwachte fout een
    code die zij op haar scherm ziet staan, en staat hij hier terug te vinden.
    """
    lijst = _lees("server_fouten", []) or []
    if not lijst:
        print("Geen serverfouten vastgelegd.")
        return
    for f in lijst[: (args.aantal if getattr(args, "aantal", 0) else 20)]:
        print(f"\n{f.get('code','?')}  {str(f.get('wanneer',''))[:16]}  "
              f"{f.get('methode','')} {f.get('pad','')}")
        print(f"    {f.get('soort','')}: {f.get('bericht','')}")
        for regel in str(f.get("spoor", "")).strip().splitlines()[-6:]:
            print(f"    | {regel}")


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


# De losse seintjes "developer → klantenservice" zijn er op 31-08-2026 weer
# uitgehaald. Ze meldden hetzelfde ding drie keer (aan het werk / gerepareerd /
# concept klaar) en vertelden geen van drieën het verhaal. Wat de twee samen
# gedaan hebben staat nu in ÉÉN mail: het seintje dat er een concept klaarligt.
# Zie `_samenwerking` in leadgen_mail.py.
# ------------------------------------------- meldingen die vanzelf uitdoven
#
# WAAROM DIT ER IS (31-08-2026, Daniel: "er is namelijk niks meer mbt
# zilverwebsite wat openstaat op dit moment").
#
# De lijst ging maar één kant op. Klantmail zette storingen erop, en er waren
# precies twee manieren om ze eraf te krijgen: `opgelost` of `afgewezen`, allebei
# door de developer. Handelde Daniel iets zelf af, of loste het vanzelf op, dan
# bleef het eeuwig staan. Gemeten: zeventien meldingen van Zilverwebsite stonden
# als "open" terwijl er volgens Daniel niets meer speelde, de oudste van 17-08.
#
# Dat is niet alleen rommelig:
#   * de automatische starter zet sessies op storingen die niet meer bestaan;
#   * de developer rapporteert een beeld dat structureel te somber is;
#   * en wie zo'n oude melding alsnog met `opgelost` afsluit, stuurt de klant
#     post over een probleem dat hij allang vergeten is — precies het soort mail
#     dat op 31-08 misging.
#
# Daarom een DERDE status, en dat onderscheid is de hele truc: `verlopen` haalt
# de melding van de lijst en stuurt NOOIT bericht naar de klant. Alleen
# `opgelost` doet dat. Uitdoven is geen reparatie en mag er ook niet op lijken.
# Hoe zwaarder het signaal, hoe langer we een melding vasthouden. Een gewone
# klacht waar iemand daarna niet meer op terugkwam is na een week vermoedelijk
# geschiedenis. Bij een klant die boos was, dreigde te stoppen, of bij een
# storing die meerdere mensen meldden, is stilte veel minder overtuigend — die
# houden we drie weken vast. Gemeten op 31-08-2026: met één vaste grens van 14
# dagen doofde geen enkele melding van Zilverwebsite uit, terwijl Daniel zei dat
# daar niets meer speelde; de meeste zaten net op 12 of 13 dagen.
VERLOOP_DAGEN = 7
VERLOOP_DAGEN_ZWAAR = 21


def _verloop_kandidaten(signalen: dict, staat: dict, nu=None) -> list[tuple[str, str]]:
    """(sleutel, reden) voor elke melding die stilletjes van de lijst mag.

    Het beslissende signaal is niet tijd maar CONTACT ZONDER HERHALING: de
    melder heeft ons ná zijn klacht nog geschreven (of kreeg antwoord) en is er
    niet op teruggekomen. Alleen tijd zou te zwak zijn — iemand die drie weken
    op vakantie is heeft zijn storing niet ingetrokken.

    Was er ná de melding geen enkel contact, dan blijft hij staan. Niets weten
    is geen reden om iets weg te halen.
    """
    nu = nu or datetime.now(timezone.utc)
    uit: list[tuple[str, str]] = []
    for sleutel, s in signalen.items():
        if s.get("status") != "open":
            continue
        laatst = _als_tijd(s.get("laatst"))
        grens = VERLOOP_DAGEN_ZWAAR if s.get("moet_zeker") else VERLOOP_DAGEN
        if not laatst or (nu - laatst).days < grens:
            continue
        melders = [m for m in (s.get("melders") or []) if m]
        if not melders:
            continue
        # ELKE melder moet erover heen zijn. Bij twee melders is één stille geen
        # bewijs dat het over is — de ander kan er nog middenin zitten.
        redenen = []
        for adres in melders:
            k = (staat.get(adres) or {})
            na = max(_seconden(k.get("laatste_inkomend")),
                     _seconden(k.get("daniel_antwoordde")))
            if not na or na <= laatst.timestamp():
                redenen = []
                break
            redenen.append(adres)
        if redenen:
            uit.append((sleutel, f"na {laatst:%d-%m} nog contact met "
                                 f"{', '.join(redenen[:3])} zonder dat het terugkwam"))
    return uit


def _als_tijd(waarde):
    try:
        d = datetime.fromisoformat(str(waarde))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _seconden(waarde) -> float:
    try:
        return float(waarde or 0)
    except (ValueError, TypeError):
        return 0.0


def laat_verlopen_uitdoven() -> int:
    """Zet stilgevallen meldingen op `verlopen`. Geen klant krijgt hier post van."""
    signalen = bugs()
    if not signalen:
        return 0
    staat = _lees("mail_state", {}) or {}
    kandidaten = _verloop_kandidaten(signalen, staat)
    for sleutel, reden in kandidaten:
        s = signalen[sleutel]
        s["status"] = "verlopen"
        s["verlopen_op"] = datetime.now(timezone.utc).isoformat()
        s["reden"] = reden
        s.pop("gemeld_als_patroon", None)
        print(f"  ⌛ '{sleutel}' uitgedoofd: {reden}")
    if kandidaten:
        _schrijf(BUG_SLEUTEL, signalen)
    return len(kandidaten)


def verlopen(args) -> None:
    """Handmatig: deze melding speelt niet meer, zonder de klant lastig te vallen."""
    signalen = bugs()
    s = signalen.get(args.sleutel)
    if not s:
        print(f"Geen storing bekend onder '{args.sleutel}'. "
              f"Bekend: {', '.join(sorted(signalen)) or 'geen'}")
        return
    s["status"] = "verlopen"
    s["verlopen_op"] = datetime.now(timezone.utc).isoformat()
    s["reden"] = args.reden
    s.pop("gemeld_als_patroon", None)
    _schrijf(BUG_SLEUTEL, signalen)
    print(f"'{args.sleutel}' staat op verlopen: {args.reden}. "
          f"Er gaat GEEN bericht naar de melder(s).")


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
    melders = s.get("melders", [])
    print(f"'{args.sleutel}' staat op opgelost. "
          f"{len(melders)} melder(s) krijgen bericht: "
          f"{', '.join(melders[:8])}")


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
    # Dezelfde vertaalslag als bij de broncode: wie "refresh" schrijft, bedoelt
    # verversen, en anders herkennen we een bekende storing niet in zijn woorden.
    laag = L.verrijk(tekst)
    if not laag.strip():
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
- Kort: vier tot zeven zinnen, ook als er meerdere punten zijn, dan een korte
  alinea per punt. Informeel Nederlands, en aan het eind het meegegeven
  ondertekeningsblok, letterlijk.
- BEGIN MET EXACT "Hi," EN NIETS ANDERS. Geen naam, geen bedrijfsnaam, niets
  tussen "Hi" en de komma. Je krijgt hier namelijk geen naam te zien, en wat je
  dan invult heb je verzonnen. Op 31-08-2026 opende de mail aan Zilverwebsite
  met "Hi Ronald" — die persoon bestaat daar niet.
- Vraag hem of het bij hem ook echt weg is.
Schrijf alleen de mailtekst.""" + L.TOON_KORT_EN_MENSELIJK


def bericht_over_reparaties() -> int:
    """Wie een storing meldde die nu gerepareerd is, hoort dat te weten.

    Dit is de terugweg developer -> klantenservice -> klant. Zonder dit blijft een
    reparatie onzichtbaar voor precies de mensen die de moeite namen hem te
    melden, en die melden de volgende keer niets meer.
    """
    signalen = bugs()
    # PER PERSOON, NIET PER STORING — en dat is geen opmaakkeuze.
    # Zolang er een antwoord voor deze persoon klaarligt komt hier niets bij (het
    # slot in _waarom_geen_concept). Ging dit per storing, dan kreeg iemand met vier
    # gerepareerde meldingen er één, en bleven de andere drie hangen tot Daniel
    # die eerste mail had verstuurd. Gemeten op 29-08-2026: Egbert had er vier
    # klaarstaan en hoorde niets — juist de klant die dreigde te stoppen.
    per_adres: dict[str, list[dict]] = {}
    for sleutel, s in signalen.items():
        if s.get("status") != "opgelost" or not s.get("uitleg"):
            continue
        for adres in s.get("melders", []):
            if adres not in set(s.get("bericht_verstuurd") or []):
                per_adres.setdefault(adres, []).append(s)

    gemaakt = 0
    for adres, reparaties in per_adres.items():
        # EERST HET SLOT, DAN PAS SCHRIJVEN. Andersom kostte elke ronde vier
        # modelaanroepen waarvan de tekst meteen werd weggegooid, elke tien
        # minuten opnieuw.
        reden = L._waarom_geen_concept(adres, None)
        if reden:
            print(f"  (nog geen bericht aan {adres}: {reden})")
            continue
        tekst = _herstelbericht(adres, reparaties)
        if not tekst:
            continue
        # BLIJFT EEN CONCEPT (31-08-2026). Dit bericht lijkt het veiligst van
        # allemaal — het is aan de code getoetst voordat het geschreven werd —
        # en juist hier ging het mis: de mail aan Zilverwebsite opende met "Hi
        # Ronald", een naam die daar niet bestaat. Getoetst op de feiten is niet
        # hetzelfde als getoetst op de aanhef.
        if L._zet_concept_klaar({"email": adres}, None, "", eigen_tekst=tekst,
                                bron="klantenservice + developer"):
            for s in reparaties:
                s["bericht_verstuurd"] = sorted(
                    set(s.get("bericht_verstuurd") or []) | {adres})
            gemaakt += 1
    if gemaakt:
        _schrijf(BUG_SLEUTEL, signalen)
    return gemaakt


def _herstelbericht(adres: str, signalen: list[dict]) -> str:
    """Eén mail over alles wat er voor deze persoon gerepareerd is."""
    sleutel = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not sleutel:
        return ""
    import anthropic
    punten = "\n\n".join(
        f"- Wat hij meldde: {s.get('omschrijving','')}\n"
        f"  Wat er gerepareerd is: {s.get('uitleg','')}" for s in signalen)
    kop = ("Deze persoon meldde meerdere dingen; ze zijn ALLEMAAL gerepareerd. "
           "Behandel ze in één mail, kort per punt, zonder ze te herhalen.\n\n"
           if len(signalen) > 1 else "")
    try:
        antwoord = L._claude(
            anthropic.Anthropic(api_key=sleutel),
            model=L.MODEL, max_tokens=16000,
            output_config={"effort": "low"},
            system=HERSTELBERICHT_REGELS,
            messages=[{"role": "user", "content":
                       f"{kop}{punten}\n\n"
                       f"Sluit af met exact dit blok:\n{L._ondertekening()}"}])
        tekst = "".join(b.text for b in antwoord.content
                        if getattr(b, "type", "") == "text").strip()
    except Exception as e:  # noqa: BLE001
        print(f"  !! herstelbericht voor {adres} mislukt ({type(e).__name__}: {e})")
        return ""
    tekst = _aanhef_zonder_naam(tekst, adres)
    # Te kort is geen bericht; dan liever niets dan iets halfs in de map.
    return tekst if len(tekst.split()) >= 15 else ""


# Een aanhef met iets tussen "Hi" en de komma.
_AANHEF_MET_NAAM = re.compile(r"^\s*(hi|hoi|hallo|beste|dag)\b[^\S\n]+([^\n,]+),",
                              re.I)


def _aanhef_zonder_naam(tekst: str, adres: str) -> str:
    """Elke naam uit de aanhef halen. Altijd, zonder uitzondering.

    WAAROM DIT EEN SLOT IS EN NIET ALLEEN EEN PROMPTREGEL (31-08-2026).
    De mail aan Zilverwebsite begon met "Hi Ronald". Zo iemand bestaat daar
    niet; het model had die naam verzonnen omdat de instructie letterlijk
    "Hi <naam>," vroeg terwijl er nergens een naam werd meegegeven.

    Die instructie is aangepast, maar een promptregel is een verzoek en geen
    garantie — en juist hier is de schade groot: een verkeerde voornaam in de
    eerste regel zegt tegen de klant dat er een machine schrijft die hem niet
    kent. Deze functie kijkt dus naar de tekst die er werkelijk uitkwam.

    Ook een bedrijfsnaam gaat eruit. Zilverwebsite is een winkelnaam en geen
    persoon; "Hi Zilverwebsite," leest net zo verkeerd. Dezelfde regel als bij
    de koude mail (zie `_persoonsnaam` in leadgen_mail.py): een naam in de
    aanhef alleen als iemand hem zelf heeft opgegeven, en dat is hier nooit zo.
    """
    treffer = _AANHEF_MET_NAAM.match(tekst or "")
    if not treffer:
        return tekst
    print(f"  ⚠ verzonnen aanhef weggehaald voor {adres}: "
          f"{treffer.group(0).strip()!r} -> 'Hi,'")
    return _AANHEF_MET_NAAM.sub("Hi,", tekst, count=1)


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
    f = sub.add_parser("fouten", help="wat er op de server stukging, met foutcode")
    f.add_argument("--aantal", type=int, default=20)
    f.set_defaults(func=fouten_tonen)
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
    v = sub.add_parser("verlopen", help="speelt niet meer; haalt hem van de lijst "
                                        "ZONDER de melder bericht te sturen")
    v.add_argument("sleutel")
    v.add_argument("reden", help="waarom hij niet meer speelt, in één zin")
    v.set_defaults(func=verlopen)
    sub.add_parser("uitdoven", help="stilgevallen meldingen automatisch van de lijst"
                   ).set_defaults(func=lambda a: print(
                       f"{laat_verlopen_uitdoven()} melding(en) uitgedoofd"))
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
