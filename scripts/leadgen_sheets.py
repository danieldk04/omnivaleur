"""Het werkoverzicht van de outreach, in Google Sheets.

Sinds 14-09-2026 vervangt dit de Notion-Leadlist. Daniels hele omgeving draait op
Google; Notion was een losse plek waar hij niet vanzelf kwam. Twee spreadsheets in
de Drive-map "Omnivaleur", bewust volledig van elkaar gescheiden:

  * E-mail outreach (MAIL_SHEET): de Marktplaats- en 2dehands-leads die de
    mailmachine benadert, het logboek en de mailteksten.
  * Instagram & FB outreach (SOCIAL_SHEET): de social leads. De mailmachine komt
    daar nooit aan; Instagram en Facebook zijn een ander spoor.

WAT DE MACHINE HIER DOET EN WAT NIET
De echte administratie (wie is wanneer gemaild) blijft in Supabase. Dit is wat
Daniel ziet, plus twee dingen die hij zelf bedient:
  1. de tab Mailteksten, die elke beurt vers gelezen wordt;
  2. het vinkje "Niet meer mailen", waarmee hij iemand uit de reeks haalt.
Die twee worden streng gelezen: lukt het lezen niet, of klopt een tekst niet, dan
gaat er niets uit en krijgt Daniel een seintje. Een gemiste mail haal je in, een
mail met "[aanhef" midden in de zin niet.

TOEGANG
Een serviceaccount van Google (GOOGLE_SHEETS_SLEUTEL, de JSON zoals Google hem
downloadt) waarmee alleen deze twee bestanden gedeeld zijn. Het ziet niets anders
van Daniels Drive. Bewust geen OAuth met zijn eigen account: een app die bij
Google nog in "testmodus" staat krijgt een sleutel die na zeven dagen stil
verloopt, en dan staat de machine op een maandagochtend zonder dat iemand het ziet.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Callable
from urllib.parse import quote

MAIL_SHEET = "1O3RjWgNWVNzmpe9M3jmJ07yI-DGK3C7F7dOfQNR3-Jc"
SOCIAL_SHEET = "1gVzzE4lVKTMnM4qgp_ghn0Mn8g_-Q_owH3ED07h-QXs"
SLEUTEL_ENV = "GOOGLE_SHEETS_SLEUTEL"

SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://sheets.googleapis.com/v4/spreadsheets"

TAB_LEADS, TAB_LOG, TAB_TEKSTEN, TAB_UITLEG = "Leads", "Logboek", "Mailteksten", "Uitleg"

LEADS_KOLOMMEN = [
    "Bedrijf", "E-mail", "Platform", "Link", "Fase", "Status", "Niet meer mailen",
    "Mails verstuurd", "Eerste contact", "Volgende actie op", "Laatste gebeurtenis",
    "Afgesloten reden", "Je/Jullie", "Reeks", "Verkoopt", "Advertenties", "Website",
    "Plaats", "Notities",
]
STOP_KOLOM = "Niet meer mailen"
LOG_KOLOMMEN = ["Datum", "Bedrijf", "E-mail", "Wat er gebeurde"]


class SheetsFout(RuntimeError):
    """Google Sheets kon niet gelezen of beschreven worden."""


class TekstenFout(RuntimeError):
    """De tab Mailteksten is niet bruikbaar. De boodschap is voor Daniel geschreven."""


def kolomletter(index: int) -> str:
    """0 wordt A, 25 wordt Z, 26 wordt AA."""
    letters, n = "", index + 1
    while n:
        n, rest = divmod(n - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


class Sheets:
    """Een dunne laag over de Sheets-API: lezen, schrijven, rijen toevoegen.

    Alles wordt RAW geschreven. Bij USER_ENTERED maakt Google van een bedrijfsnaam
    als "+31 Vintage" of "=Mode" een formule, en dan staat er #ERROR! in de lijst.
    Datums gaan als 2026-09-14 de cel in; zo sorteren ze ook als tekst goed."""

    def __init__(self, sleutel: str | None = None, http=None) -> None:
        ruw = sleutel if sleutel is not None else os.environ.get(SLEUTEL_ENV, "")
        if not ruw.strip():
            raise SheetsFout(f"{SLEUTEL_ENV} ontbreekt, dus geen toegang tot Google Sheets")
        try:
            self._info = json.loads(ruw)
            self.email = self._info["client_email"]
        except Exception as e:  # noqa: BLE001
            raise SheetsFout(f"{SLEUTEL_ENV} is geen bruikbare Google-sleutel: {e}") from e
        if http is None:
            import httpx
            http = httpx.Client(timeout=30.0)
        self._http = http
        self._token, self._geldig_tot = "", 0.0

    def _toegang(self) -> str:
        if self._token and time.time() < self._geldig_tot - 60:
            return self._token
        from google.auth import crypt, jwt
        nu = int(time.time())
        bewijs = jwt.encode(crypt.RSASigner.from_service_account_info(self._info),
                            {"iss": self.email, "scope": SCOPE, "aud": TOKEN_URL,
                             "iat": nu, "exp": nu + 3600})
        r = self._http.post(TOKEN_URL, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": bewijs.decode() if isinstance(bewijs, bytes) else bewijs})
        if r.status_code >= 300:
            raise SheetsFout(f"Google gaf geen toegang ({r.status_code}): {r.text[:200]}")
        d = r.json()
        self._token = d["access_token"]
        self._geldig_tot = nu + int(d.get("expires_in", 3600))
        return self._token

    def _vraag(self, methode: str, pad: str, **kw) -> dict:
        # Google antwoordt onder drukte met 429 of een 5xx. Dat gaat binnen
        # seconden over, dus eerst even wachten voordat we het een storing noemen.
        fout = ""
        for poging in range(4):
            if poging:
                time.sleep(2 ** poging)
            try:
                r = self._http.request(methode, f"{API}/{pad}", **kw, headers={
                    "Authorization": f"Bearer {self._toegang()}"})
            except SheetsFout:
                raise
            except Exception as e:  # noqa: BLE001
                fout = f"geen verbinding: {e}"
                continue
            if r.status_code < 300:
                return r.json() if r.content else {}
            fout = f"{r.status_code}: {r.text[:300]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        raise SheetsFout(f"{methode} {pad.split('/')[0][:12]}… mislukt ({fout})")

    def lees(self, bestand: str, bereik: str) -> list[list]:
        d = self._vraag("GET", f"{bestand}/values/{quote(bereik, safe='')}",
                        params={"valueRenderOption": "UNFORMATTED_VALUE"})
        return d.get("values", [])

    def schrijf(self, bestand: str, blokken: list[dict]) -> None:
        if blokken:
            self._vraag("POST", f"{bestand}/values:batchUpdate",
                        json={"valueInputOption": "RAW", "data": blokken})

    def voeg_toe(self, bestand: str, tab: str, rijen: list[list]) -> None:
        if rijen:
            self._vraag("POST", f"{bestand}/values/{quote(tab + '!A1', safe='')}:append",
                        params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                        json={"values": rijen})

    def wijzig(self, bestand: str, verzoeken: list[dict]) -> dict:
        return self._vraag("POST", f"{bestand}:batchUpdate", json={"requests": verzoeken})

    def tabs(self, bestand: str) -> dict[str, int]:
        d = self._vraag("GET", bestand, params={"fields": "sheets.properties(sheetId,title)"})
        return {s["properties"]["title"]: s["properties"]["sheetId"] for s in d.get("sheets", [])}


# ── Mailteksten ───────────────────────────────────────────────────────────
# Daniel past de teksten zelf aan. Daarom staan ze voluit in een je-versie en een
# jullie-versie: gewone zinnen, zonder de tien grammaticacodes die de oude
# sjablonen nodig hadden ({zie_jij}, {jij_stopt}...). Er blijven drie invulvelden
# over, en die zijn in één zin uit te leggen.

TEKST_RIJEN = [
    ("A1", "Reeks A, mail 1: de eerste mail"),
    ("A2", "Reeks A, mail 2: 2 dagen na mail 1"),
    ("A3", "Reeks A, mail 3: 4 dagen na mail 2, de laatste"),
    ("B1", "Reeks B, mail 1: de eerste mail"),
    ("B2", "Reeks B, mail 2: 2 dagen na mail 1"),
    ("B3", "Reeks B, mail 3: 4 dagen na mail 2, de laatste"),
    ("V1", "Video-opvolging 1: 3 dagen na jouw video, als er niets terugkwam"),
    ("V2", "Video-opvolging 2: 7 dagen na jouw video, als er nog steeds niets kwam"),
    ("HANDTEKENING", "Staat onder elke mail hierboven"),
]
TEKST_KOLOMMEN = ["Sleutel", "Welke mail", "Onderwerp (je)", "Onderwerp (jullie)",
                  "Tekst (je)", "Tekst (jullie)"]
INVULVELDEN = {
    "[aanhef]": "wordt 'Hi', of 'Hi Albert' als we de voornaam kennen",
    "[openingszin]": "de persoonlijke eerste zin over hun advertenties en webshop",
    "[platform]": "wordt 'Marktplaats' of '2dehands', waar de lead vandaan komt",
}
_HAAK = re.compile(r"\[[^\[\]\n]{1,40}\]")


def controleer_teksten(rijen: list[list]) -> dict[str, dict[str, str]]:
    """Leest de tab Mailteksten en weigert alles wat een rare mail zou opleveren.

    Elke fout wordt verzameld, niet alleen de eerste: Daniel moet in één seintje
    kunnen zien wat er mis is, niet na elke reparatie weer een nieuw seintje."""
    if not rijen:
        raise TekstenFout("de tab Mailteksten is leeg of bestaat niet")
    kop = [str(c).strip() for c in rijen[0]]
    weg = [k for k in TEKST_KOLOMMEN if k not in kop]
    if weg:
        raise TekstenFout("in Mailteksten ontbreekt de kolom " + ", ".join(weg))
    plek = {k: kop.index(k) for k in TEKST_KOLOMMEN}

    gelezen: dict[str, dict[str, str]] = {}
    for rij in rijen[1:]:
        def cel(kolom: str, rij=rij) -> str:
            i = plek[kolom]
            return str(rij[i]).replace("\r\n", "\n").strip() if i < len(rij) else ""
        sleutel = cel("Sleutel").upper()
        if sleutel:
            gelezen[sleutel] = {"onderwerp_je": cel("Onderwerp (je)"),
                                "onderwerp_jullie": cel("Onderwerp (jullie)"),
                                "tekst_je": cel("Tekst (je)"),
                                "tekst_jullie": cel("Tekst (jullie)")}

    problemen: list[str] = []
    for sleutel, uitleg in TEKST_RIJEN:
        t = gelezen.get(sleutel)
        if t is None:
            problemen.append(f"de rij {sleutel} ({uitleg}) is weg")
            continue
        if sleutel == "HANDTEKENING":
            verplicht = ["tekst_je"]
        elif sleutel.startswith("V"):
            # Een video-opvolging gaat in dezelfde draad als jouw videomail en
            # krijgt dus diens onderwerp. Jullie-tekst mag leeg: dan de je-tekst.
            verplicht = ["tekst_je"]
        else:
            verplicht = ["onderwerp_je", "onderwerp_jullie", "tekst_je", "tekst_jullie"]
        for veld in verplicht:
            if len(t[veld]) < (2 if veld.startswith("onderwerp") or sleutel == "HANDTEKENING"
                               else 20):
                problemen.append(f"{sleutel}: {veld.replace('_', ' (')}) is leeg of te kort")
        for veld, waarde in t.items():
            naam = f"{sleutel} {veld.replace('_', ' (')})"
            onbekend = [h for h in _HAAK.findall(waarde) if h.lower() not in INVULVELDEN]
            if onbekend:
                problemen.append(f"{naam}: {', '.join(onbekend)} kent de machine niet "
                                 f"(wel: {', '.join(INVULVELDEN)})")
            if "{" in waarde or "}" in waarde:
                problemen.append(f"{naam}: bevat {{ of }}, dat is een oud codeteken")
            if waarde.count("[") != waarde.count("]"):
                problemen.append(f"{naam}: een [ of ] staat er niet in paren")
            if veld.startswith("onderwerp") and "\n" in waarde:
                problemen.append(f"{naam}: een onderwerp moet op één regel")
    if problemen:
        raise TekstenFout("\n".join(problemen))
    return gelezen


def lees_teksten(sheets: Sheets, bestand: str = MAIL_SHEET) -> dict[str, dict[str, str]]:
    try:
        rijen = sheets.lees(bestand, f"{TAB_TEKSTEN}!A1:F40")
    except SheetsFout as e:
        raise TekstenFout(f"de tab Mailteksten kon niet gelezen worden: {e}") from e
    return controleer_teksten(rijen)


def vul_in(tekst: str, waarden: dict[str, str]) -> str:
    """Invulvelden vervangen. Hoofdletters tellen niet: [Aanhef] mag ook."""
    return _HAAK.sub(lambda m: waarden.get(m.group(0).lower(), m.group(0)), tekst)


# ── De tab Leads ──────────────────────────────────────────────────────────


class Leadblad:
    """Schrijft per lead wat er gebeurde naar de tab Leads en het Logboek.

    Rijen worden op het e-mailadres gezocht, en kolommen op hun kopnaam, en
    allebei VLAK voor het schrijven opnieuw. Daniel sorteert en filtert in deze
    lijst; een rijnummer van vijf minuten geleden kan dan bij iemand anders horen.

    De machine raakt alleen de kolommen aan die hij zelf bijhoudt. Notities en het
    stopvinkje zijn van Daniel en worden nooit overschreven."""

    def __init__(self, sheets: Sheets, bestand: str = MAIL_SHEET, buffer: int = 15,
                 naam: Callable[[dict], str] | None = None) -> None:
        self.sheets, self.bestand, self.buffer = sheets, bestand, buffer
        self._naam = naam or (lambda l: l.get("handelsnaam") or l.get("full_name")
                              or l.get("name") or "")
        self._wachtend: list[tuple[dict, str, dict, str]] = []
        self.gemist: set[str] = set()
        self.nieuw = 0

    def _lees(self) -> tuple[list[str], list[list]]:
        waarden = self.sheets.lees(self.bestand, f"{TAB_LEADS}!A1:AZ")
        if not waarden:
            raise SheetsFout(f"de tab {TAB_LEADS} is leeg of bestaat niet")
        kop = [str(k).strip() for k in waarden[0]]
        if "E-mail" not in kop:
            raise SheetsFout(f"de kolom E-mail ontbreekt in {TAB_LEADS}")
        return kop, waarden[1:]

    def gestopt(self) -> set[str]:
        """Adressen waar Daniel "Niet meer mailen" heeft aangevinkt."""
        kop, rijen = self._lees()
        if STOP_KOLOM not in kop:
            raise SheetsFout(f"de kolom {STOP_KOLOM} ontbreekt in {TAB_LEADS}")
        e, s = kop.index("E-mail"), kop.index(STOP_KOLOM)
        uit = set()
        for rij in rijen:
            if len(rij) > max(e, s) and (rij[s] is True or
                                         str(rij[s]).strip().upper() in ("TRUE", "WAAR", "JA", "X")):
                uit.add(str(rij[e]).strip().lower())
        return uit

    def leadvelden(self, lead: dict) -> dict:
        return {"Bedrijf": self._naam(lead), "E-mail": (lead.get("email") or "").lower(),
                "Platform": "2dehands" if lead.get("platform") == "2dehands" else "MP",
                "Link": lead.get("ig_url") or "", "Je/Jullie": lead.get("je_jullie") or "Je",
                "Verkoopt": lead.get("verkoopt_vooral") or "", "Advertenties": lead.get("ads") or "",
                "Website": lead.get("site") or lead.get("website") or "",
                "Plaats": lead.get("plaats") or "", STOP_KOLOM: False}

    def noteer(self, lead: dict, regel: str, wensen: dict) -> None:
        self._wachtend.append((lead, regel, wensen, datetime.now().strftime("%d-%m-%Y %H:%M")))
        if len(self._wachtend) >= self.buffer:
            self.wegschrijven()

    def wegschrijven(self) -> int:
        """Alles wat klaarstaat in twee à drie verzoeken naar Google."""
        if not self._wachtend:
            return 0
        wachtend, self._wachtend = self._wachtend, []
        try:
            kop, rijen = self._lees()
            e = kop.index("E-mail")
            rij_van: dict[str, int] = {}
            for i, rij in enumerate(rijen):
                adres = str(rij[e]).strip().lower() if e < len(rij) else ""
                if adres:
                    rij_van.setdefault(adres, i + 2)
            blokken, nieuw, log = [], {}, []
            for lead, regel, wensen, tijd in wachtend:
                adres = (lead.get("email") or "").strip().lower()
                if not adres:
                    continue
                waarden = {**wensen, "Laatste gebeurtenis": f"{tijd} {regel}"}
                log.append([tijd, self._naam(lead), adres, regel])
                if adres in rij_van:
                    for kolom, waarde in waarden.items():
                        if kolom not in kop:
                            self.gemist.add(kolom)
                            continue
                        blokken.append({"range": f"{TAB_LEADS}!{kolomletter(kop.index(kolom))}"
                                                 f"{rij_van[adres]}",
                                        "values": [["" if waarde is None else waarde]]})
                else:
                    nieuw.setdefault(adres, self.leadvelden(lead)).update(waarden)
            self.sheets.schrijf(self.bestand, blokken)
            if nieuw:
                self.sheets.voeg_toe(self.bestand, TAB_LEADS,
                                     [[rij.get(k, "") for k in kop] for rij in nieuw.values()])
                self.nieuw += len(nieuw)
            self.sheets.voeg_toe(self.bestand, TAB_LOG, log)
        except SheetsFout:
            self._wachtend = wachtend + self._wachtend   # volgende poging neemt ze mee
            raise
        return len(wachtend)
