"""Eenmalig: de Notion-Leadlist verhuist naar de twee Google-spreadsheets.

    python3 scripts/leadgen_sheets_opzetten.py --droog     # alles opbouwen, niets schrijven
    python3 scripts/leadgen_sheets_opzetten.py             # echt vullen

Nodig: NOTION_TOKEN, SUPABASE_URL + SUPABASE_KEY (service_role) en
GOOGLE_SHEETS_SLEUTEL. Weigert te schrijven als de tab Leads al gevuld is: dit
script is voor de verhuizing, niet voor bijwerken. Dat doet de machine zelf.

Waar alles vandaan komt (14-09-2026):
  * Notion: wat Daniel zag. Fase, Status, datums, Notities, en het logboek dat als
    losse regels onder elke leadpagina stond.
  * Supabase (leadgen_opslag): het e-mailadres, aantal advertenties, website en
    plaats, want die stonden nooit in Notion, en de administratie van de machine
    (hoeveel mails, welke reeks).
  * De begintekst van de mailteksten: de sjablonen die tot vandaag in
    leadgen_mail.py stonden. Een aparte proef (voor-en-na) laat zien dat de mails
    uit de spreadsheet woord voor woord gelijk zijn aan wat de machine verstuurde.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402

import leadgen_mail as lm  # noqa: E402
import leadgen_sheets as ls  # noqa: E402

NOTION_DB = "399b0954-fb72-8053-a8fc-fa7c21616371"
MAIL_PLATFORMS = ("MP", "2dehands")

FASE_VOLGORDE = [
    "⚡ Jij bent aan zet", "⏳ Bal bij hen", "4. Gereageerd", "5. Video verstuurd",
    "6. Aanmeldlink verstuurd", "6. Calendly verstuurd", "7. Call geboekt", "Klant",
    "2. Benaderd", "T2. Tekst follow-up 1", "T3. Tekst follow-up 2 (laatste)",
    "3. Voice memo", "Voice Memo Follow up 1", "M3. Memo follow-up 2 (laatste)",
    "1. Te benaderen", "Gebruikt concurrent", "0. Kan (nog) niet", "Geen interesse",
    "Doodgelopen",
]

SOCIAL_KOLOMMEN = [
    "Naam", "Platform", "Link", "Fase", "Status", "Verkoopt", "Verkoopt op",
    "Bron / hashtag", "FB Groep", "Language", "Je/Jullie", "AI Generated Tekst",
    "Voice memo tekst", "Eerste contact", "Volgende actie op", "Follow-ups verstuurd",
    "Afgesloten reden", "Notities", "Aangemaakt",
]

LOGREGEL = re.compile(r"^(\d{2}-\d{2}-\d{4}(?: \d{2}:\d{2})?) — (.+)$", re.S)

UITLEG_MAIL = """Hoe deze spreadsheet werkt

TAB LEADS
Hier staan alle Marktplaats- en 2dehands-leads voor de e-mailoutreach. Instagram en Facebook staan in een aparte spreadsheet en komen hier nooit in.
De machine werkt deze kolommen zelf bij, uiterlijk tien minuten na elke gebeurtenis: Fase, Status, Mails verstuurd, Eerste contact, Volgende actie op, Laatste gebeurtenis, Afgesloten reden en Reeks.
Notities is van jou. Die kolom raakt de machine nooit aan.
Niet meer mailen: vink aan en die lead krijgt vanaf de volgende beurt geen enkele mail meer van de machine, ook geen video-opvolging.
Sorteren en filteren mag gewoon. Kolommen hernoemen of verwijderen niet, want de machine zoekt ze op naam.
Nieuwe leads zet de machine zelf onderaan.

TAB LOGBOEK
Alles wat er per lead gebeurde, met datum en tijd. Nieuwe regels komen onderaan. De regels van voor 14-09-2026 komen uit Notion.

TAB MAILTEKSTEN
Pas de teksten gewoon aan. De machine leest ze elke tien minuten opnieuw, dus een wijziging geldt vanaf de eerstvolgende mail.
Er zijn twee reeksen, A en B. Elke lead krijgt vast een van de twee, half om half, zodat je kunt zien welke beter werkt.
Elke mail staat er twee keer in: met je (eenmanszaak) en met jullie (bedrijf met meer mensen). De machine kiest zelf de juiste.
Een witregel in de cel maakt een nieuwe alinea. Een nieuwe regel in de cel maak je op de Mac met Cmd+Enter. Een enkele regelovergang wordt een spatie, want het mailprogramma van de ontvanger breekt de regels zelf af.
De invulvelden:
[aanhef] wordt Hi, of Hi met de voornaam als we die kennen.
[openingszin] wordt de persoonlijke zin over hun advertenties en webshop.
[platform] wordt Marktplaats of 2dehands, afhankelijk van waar de lead vandaan komt.
Typ je een invulveld dat de machine niet kent, zoals [naam], of laat je een tekst leeg, dan verstuurt de machine niets en krijg je een mail met wat er mis is. Zodra het klopt, haalt hij de gemiste mails vanzelf in.
De kolom Sleutel niet veranderen: daaraan herkent de machine welke mail het is.

HET RITME
Mail 1 gaat op een willekeurig moment overdag. Mail 2 volgt 2 dagen later, mail 3 nog eens 4 dagen later.
Antwoordt iemand, meldt iemand zich af of komt de mail niet aan, dan stopt de reeks meteen.
Na mail 3 en 10 dagen stilte gaat de lead naar Doodgelopen.
Mensen met een Omnivaleur-account krijgen nooit een mail van de machine.

VIDEO-OPVOLGING
Stuur jij iemand uit deze lijst een mail met de videolink en komt er niets terug, dan stuurt de machine na 3 dagen tekst V1 en na 7 dagen tekst V2, in hetzelfde mailgesprek.
Antwoordt diegene, of stuur jij zelf nog iets, dan stopt het meteen.
Op een video van meer dan 10 dagen oud komt geen opvolging meer.
Alleen voor leads uit deze lijst. Partners, groothandels en andere contacten krijgen nooit een automatische opvolging."""

UITLEG_SOCIAL = """Instagram & FB outreach

Dit is de lijst voor Instagram en Facebook. Hij staat bewust helemaal los van de e-mailoutreach: de mailmachine leest en schrijft hier nooit iets.
Instagram-leadgen staat sinds 06-09-2026 stil: 171 leads gaven geen enkele aanmelding en het Instagram-account is geblokkeerd.
Alles hier komt uit de Notion-Leadlist zoals die op 14-09-2026 was. Deze lijst werk je met de hand bij."""


def _notion(token: str, methode: str, pad: str, **kw) -> dict:
    r = httpx.request(methode, f"https://api.notion.com/v1/{pad}", timeout=60, **kw,
                      headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"})
    r.raise_for_status()
    return r.json()


def _waarde(prop: dict):
    soort = prop.get("type")
    v = prop.get(soort)
    if soort in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v or [])
    if soort in ("select", "status"):
        return (v or {}).get("name") or ""
    if soort == "multi_select":
        return ", ".join(x["name"] for x in v or [])
    if soort == "date":
        return ((v or {}).get("start") or "")[:10]
    if soort in ("url", "number", "checkbox"):
        return "" if v is None else v
    return ""


def notion_rijen(token: str) -> list[dict]:
    rijen, cursor = [], None
    while True:
        d = _notion(token, "POST", f"databases/{NOTION_DB}/query",
                    json={"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
        for pagina in d["results"]:
            rij = {k: _waarde(p) for k, p in pagina["properties"].items()}
            rij["_id"], rij["_aangemaakt"] = pagina["id"], pagina["created_time"][:10]
            rijen.append(rij)
        if not d.get("has_more"):
            return rijen
        cursor = d["next_cursor"]


def logregels(token: str, pagina_id: str) -> list[tuple[str, str]]:
    """De regels die de machine onder een leadpagina zette, als (datum, tekst)."""
    uit, cursor = [], None
    while True:
        d = _notion(token, "GET", f"blocks/{pagina_id}/children",
                    params={"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
        for blok in d["results"]:
            tekst = "".join(x.get("plain_text", "")
                            for x in (blok.get(blok["type"]) or {}).get("rich_text", []))
            gevonden = LOGREGEL.match(tekst.strip())
            if gevonden:
                uit.append((gevonden.group(1), gevonden.group(2).replace(" — ", ", ")))
        if not d.get("has_more"):
            return uit
        cursor = d["next_cursor"]


def _tijd(datum: str) -> datetime:
    return datetime.strptime(datum, "%d-%m-%Y %H:%M" if " " in datum else "%d-%m-%Y")


def _sleutel(url) -> str:
    return str(url or "").rstrip("/").lower()


def mailteksten() -> list[list[str]]:
    """De sjablonen uit leadgen_mail.py, voluit in een je- en een jullie-versie."""
    def alineas(tekst: str) -> str:
        return "\n\n".join(" ".join(a.split()) for a in tekst.split("\n\n") if a.strip())

    def invullen(sjabloon: str, vorm: str) -> str:
        return alineas(sjabloon.format(aanhef="[aanhef]", haakje="[openingszin]",
                                       bedrijf=lm.BEDRIJF, site=lm.SITE.replace("https://", ""),
                                       ondertekening="",
                                       **lm._jij({"je_jullie": "Jullie" if vorm == "jullie" else "Je"})))

    reeksen = {"A": lm.BEURTEN, "B": lm.BEURTEN_B}
    uitleg = dict(ls.TEKST_RIJEN)
    rijen = [ls.TEKST_KOLOMMEN]
    for reeks, beurten in reeksen.items():
        for n, (_, onderwerp, sjabloon) in enumerate(beurten):
            sleutel = f"{reeks}{n + 1}"
            cellen = []
            for vorm in ("je", "jullie"):
                o = onderwerp.format(**lm._jij({"je_jullie": "Jullie" if vorm == "jullie" else "Je"}))
                cellen.append(o.replace("Marktplaats", "[platform]") if reeks == "A" else o)
            for vorm in ("je", "jullie"):
                t = invullen(sjabloon, vorm)
                # B2 en B3 zeggen "anders dan op Marktplaats": dat klopt voor een
                # 2dehands-lead alleen met het platform erin. B1 noemt Marktplaats
                # naast 2dehands in één zin en blijft daarom zoals hij was.
                cellen.append(t.replace("Marktplaats", "[platform]") if sleutel in ("B2", "B3") else t)
            rijen.append([sleutel, uitleg[sleutel], *cellen])
    for n, sjabloon in enumerate(lm.WARM_OPVOLG):
        sleutel = f"V{n + 1}"
        rijen.append([sleutel, uitleg[sleutel] + " (jullie leeg: dan de je-tekst)",
                      "(zelfde mailgesprek als je video)", "",
                      alineas(sjabloon.format(link=lm.REGISTREREN, ondertekening="")), ""])
    rijen.append(["HANDTEKENING", uitleg["HANDTEKENING"], "", "", lm.ONDERTEKENING, ""])
    return rijen


def bouw(rijen: list[dict], logs: dict[str, list], leads: list[dict], state: dict) -> dict:
    per_url = {_sleutel(l.get("ig_url")): l for l in leads}
    mail, social, mail_log, social_log = [], [], [], []
    for rij in rijen:
        regels = logs.get(rij["_id"], [])
        if rij.get("Platform") in MAIL_PLATFORMS:
            lead = per_url.pop(_sleutel(rij.get("URL")), {})
            adres = (lead.get("email") or "").lower()
            st = state.get(adres) or {}
            mails = sum(1 for v in st.get("verstuurd", []) if str(v.get("beurt", "")).startswith("mail"))
            mail.append({
                "Bedrijf": rij.get("Name") or lm._bedrijfsnaam(lead) if lead else rij.get("Name"),
                "E-mail": adres, "Platform": rij["Platform"], "Link": rij.get("URL") or "",
                "Fase": rij.get("Fase") or "", "Status": rij.get("Status") or "",
                ls.STOP_KOLOM: False, "Mails verstuurd": mails or "",
                "Eerste contact": rij.get("Eerste contact") or "",
                "Volgende actie op": rij.get("Volgende actie op") or "",
                "Laatste gebeurtenis": " ".join(regels[-1]) if regels else "",
                "Afgesloten reden": rij.get("Afgesloten reden") or "",
                "Je/Jullie": rij.get("Je/Jullie") or lead.get("je_jullie") or "",
                "Reeks": st.get("variant") or "",
                "Verkoopt": rij.get("Verkoopt") or lead.get("verkoopt_vooral") or "",
                "Advertenties": lead.get("ads") or "",
                "Website": lead.get("site") or lead.get("website") or "",
                "Plaats": lead.get("plaats") or "", "Notities": rij.get("Notities") or ""})
            mail_log += [[d, rij.get("Name") or "", adres, t] for d, t in regels]
        elif rij.get("Platform") in ("IG", "FB") or rij.get("URL") or rij.get("Fase") or rij.get("Notities"):
            platform = rij.get("Platform") or ("FB" if "facebook.com" in str(rij.get("URL")) else "")
            social.append({**{k: rij.get(k, "") for k in SOCIAL_KOLOMMEN},
                           "Naam": rij.get("Name") or "", "Platform": platform,
                           "Link": rij.get("URL") or "", "Aangemaakt": rij["_aangemaakt"]})
            social_log += [[d, rij.get("Name") or "", rij.get("URL") or "", t] for d, t in regels]
    for lead in per_url.values():            # in de machine, maar nooit in Notion gezet
        if lead.get("email"):
            blad = ls.Leadblad(None, naam=lm._bedrijfsnaam)
            mail.append({**blad.leadvelden(lead), "Fase": "1. Te benaderen"})

    def volgorde(r):
        fase = r.get("Fase") or ""
        return (FASE_VOLGORDE.index(fase) if fase in FASE_VOLGORDE else 99,
                -(r.get("Advertenties") or 0 if isinstance(r.get("Advertenties"), int) else 0))
    mail.sort(key=volgorde)
    social.sort(key=volgorde)
    mail_log.sort(key=lambda r: _tijd(r[0]))
    social_log.sort(key=lambda r: _tijd(r[0]))
    return {"mail": mail, "social": social, "mail_log": mail_log, "social_log": social_log}


def _opmaak(sheets: ls.Sheets, bestand: str, tabs: dict[str, int], kolommen: list[str],
            aantal: int, teksten: bool) -> None:
    leads = tabs[ls.TAB_LEADS]
    kop = {"repeatCell": {"range": {"sheetId": leads, "startRowIndex": 0, "endRowIndex": 1},
                          "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                                         "backgroundColor": {"red": .9, "green": .93, "blue": .98}}},
                          "fields": "userEnteredFormat(textFormat,backgroundColor)"}}
    verzoeken = [
        kop,
        {"updateSheetProperties": {"properties": {"sheetId": leads, "gridProperties": {
            "frozenRowCount": 1, "frozenColumnCount": 1}},
            "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
        {"setBasicFilter": {"filter": {"range": {"sheetId": leads, "startRowIndex": 0,
                                                 "endColumnIndex": len(kolommen)}}}},
        {"autoResizeDimensions": {"dimensions": {"sheetId": leads, "dimension": "COLUMNS",
                                                 "startIndex": 0, "endIndex": len(kolommen)}}},
    ]
    if "Fase" in kolommen:
        verzoeken.append({"setDataValidation": {
            "range": {"sheetId": leads, "startRowIndex": 1, "endRowIndex": aantal + 2000,
                      "startColumnIndex": kolommen.index("Fase"), "endColumnIndex": kolommen.index("Fase") + 1},
            "rule": {"condition": {"type": "ONE_OF_LIST",
                                   "values": [{"userEnteredValue": f} for f in FASE_VOLGORDE]},
                     "strict": False, "showCustomUi": True}}})
    if ls.STOP_KOLOM in kolommen:
        s = kolommen.index(ls.STOP_KOLOM)
        verzoeken.append({"setDataValidation": {
            "range": {"sheetId": leads, "startRowIndex": 1, "endRowIndex": aantal + 2000,
                      "startColumnIndex": s, "endColumnIndex": s + 1},
            "rule": {"condition": {"type": "BOOLEAN"}}}})
    for naam in ("Laatste gebeurtenis", "Notities", "AI Generated Tekst", "Voice memo tekst"):
        if naam in kolommen:
            i = kolommen.index(naam)
            verzoeken.append({"updateDimensionProperties": {
                "range": {"sheetId": leads, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": 340}, "fields": "pixelSize"}})
    if ls.TAB_LOG in tabs:
        verzoeken += [{**kop, "repeatCell": {**kop["repeatCell"], "range": {
            "sheetId": tabs[ls.TAB_LOG], "startRowIndex": 0, "endRowIndex": 1}}},
            {"updateSheetProperties": {"properties": {"sheetId": tabs[ls.TAB_LOG], "gridProperties": {
                "frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
            {"updateDimensionProperties": {"range": {"sheetId": tabs[ls.TAB_LOG], "dimension": "COLUMNS",
                                                     "startIndex": 3, "endIndex": 4},
                                           "properties": {"pixelSize": 620}, "fields": "pixelSize"}}]
    if teksten:
        t = tabs[ls.TAB_TEKSTEN]
        verzoeken += [
            {**kop, "repeatCell": {**kop["repeatCell"], "range": {"sheetId": t, "startRowIndex": 0, "endRowIndex": 1}}},
            {"repeatCell": {"range": {"sheetId": t, "startRowIndex": 1},
                            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
            {"updateSheetProperties": {"properties": {"sheetId": t, "gridProperties": {"frozenRowCount": 1}},
                                       "fields": "gridProperties.frozenRowCount"}},
            {"addProtectedRange": {"protectedRange": {
                "range": {"sheetId": t, "startColumnIndex": 0, "endColumnIndex": 1},
                "description": "Sleutel: hieraan herkent de machine de mail", "warningOnly": True}}},
        ]
        for i, breedte in enumerate((110, 240, 240, 240, 520, 520)):
            verzoeken.append({"updateDimensionProperties": {
                "range": {"sheetId": t, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                "properties": {"pixelSize": breedte}, "fields": "pixelSize"}})
    u = tabs[ls.TAB_UITLEG]
    verzoeken += [
        {"updateDimensionProperties": {"range": {"sheetId": u, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                       "properties": {"pixelSize": 900}, "fields": "pixelSize"}},
        {"repeatCell": {"range": {"sheetId": u}, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                        "fields": "userEnteredFormat.wrapStrategy"}},
    ]
    sheets.wijzig(bestand, verzoeken)


def vul(sheets: ls.Sheets, bestand: str, tabnamen: list[str], inhoud: dict[str, list[list]],
        kolommen: list[str], teksten: bool) -> None:
    tabs = sheets.tabs(bestand)
    if ls.TAB_LEADS in tabs and len(sheets.lees(bestand, f"{ls.TAB_LEADS}!A1:B3")) > 1:
        sys.exit(f"{bestand}: de tab Leads is al gevuld. Dit script vult alleen een lege spreadsheet.")
    verzoeken, eerste = [], next(iter(tabs.items()))
    if ls.TAB_LEADS not in tabs:
        verzoeken.append({"updateSheetProperties": {"properties": {"sheetId": eerste[1], "title": ls.TAB_LEADS},
                                                    "fields": "title"}})
    for naam in tabnamen[1:]:
        if naam not in tabs:
            verzoeken.append({"addSheet": {"properties": {"title": naam}}})
    if verzoeken:
        sheets.wijzig(bestand, verzoeken)
        tabs = sheets.tabs(bestand)
    sheets.schrijf(bestand, [{"range": f"{naam}!A1", "values": waarden}
                             for naam, waarden in inhoud.items() if waarden])
    _opmaak(sheets, bestand, tabs, kolommen, len(inhoud[ls.TAB_LEADS]), teksten)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--droog", action="store_true", help="alles opbouwen en tonen, niets naar Google")
    args = ap.parse_args()

    token = lm._need("NOTION_TOKEN")
    rijen = notion_rijen(token)
    print(f"Notion: {len(rijen)} rijen gelezen, logboek per pagina ophalen...", flush=True)
    logs = {r["_id"]: logregels(token, r["_id"]) for r in rijen}
    leads = lm._load(lm.MP_LEADS) + lm._load(lm.TWEEDEHANDS_LEADS)
    state = lm._state()
    b = bouw(rijen, logs, leads, state)
    teksten = mailteksten()
    ls.controleer_teksten(teksten)          # de begintekst moet zelf door de controle komen

    mail_inhoud = {
        ls.TAB_LEADS: [ls.LEADS_KOLOMMEN] + [[r.get(k, "") for k in ls.LEADS_KOLOMMEN] for r in b["mail"]],
        ls.TAB_LOG: [ls.LOG_KOLOMMEN] + b["mail_log"],
        ls.TAB_TEKSTEN: teksten,
        ls.TAB_UITLEG: [[regel] for regel in UITLEG_MAIL.split("\n")],
    }
    social_inhoud = {
        ls.TAB_LEADS: [SOCIAL_KOLOMMEN] + [[r.get(k, "") for k in SOCIAL_KOLOMMEN] for r in b["social"]],
        ls.TAB_LOG: [["Datum", "Naam", "Link", "Wat er gebeurde"]] + b["social_log"],
        ls.TAB_UITLEG: [[regel] for regel in UITLEG_SOCIAL.split("\n")],
    }
    print(f"E-mail outreach: {len(b['mail'])} leads, {len(b['mail_log'])} logregels, "
          f"{len(teksten) - 1} mailteksten")
    print(f"Instagram & FB:  {len(b['social'])} leads, {len(b['social_log'])} logregels")
    if args.droog:
        uit = Path(os.environ.get("TMPDIR", "/tmp")) / "leadgen_sheets_voorbeeld.json"
        uit.write_text(json.dumps({"mail": mail_inhoud, "social": social_inhoud}, ensure_ascii=False, indent=1))
        print(f"droog: niets geschreven, voorbeeld in {uit}")
        return

    sheets = ls.Sheets()
    vul(sheets, ls.MAIL_SHEET, [ls.TAB_LEADS, ls.TAB_LOG, ls.TAB_TEKSTEN, ls.TAB_UITLEG],
        mail_inhoud, ls.LEADS_KOLOMMEN, teksten=True)
    vul(sheets, ls.SOCIAL_SHEET, [ls.TAB_LEADS, ls.TAB_LOG, ls.TAB_UITLEG],
        social_inhoud, SOCIAL_KOLOMMEN, teksten=False)
    print("Beide spreadsheets gevuld.")


if __name__ == "__main__":
    main()
