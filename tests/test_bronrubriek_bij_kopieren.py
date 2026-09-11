"""Kopiëren van Marktplaats naar 2dehands kijkt eerst waar de advertentie STAAT.

AANLEIDING (11-09-2026, Egbert Brouwer / Papa's Plectrums), zijn eigen woorden:

    "De miniatuur gitaartje moeten niet in de rubriek gitaren geplaatst worden,
     maar in: Verzamelen > Muziek, Artiesten en Beroemdheden.
     Het zou beter zijn als er op voorhand gekeken wordt met het kopiëren van MP
     naar 2eHands in welke categorieën de betreffende artikelen staan, hiermee
     voorkom je dat Omnivaleur probeert ze te listen in een betaalde categorie."

Twee dingen in één melding, en hij heeft bij allebei gelijk:

1. DE RUBRIEK WAS GERADEN. Bij het importeren leiden we de categorie af uit de
   titel, uit onze eigen lijst — en die lijst kent kleding, wonen, antiek,
   muziek, audio, games en sieraden. "Verzamelen" komt er niet in voor. Een
   miniatuurgitaartje belandt dan in Muziek en Instrumenten > Gitaren, want dat
   is de dichtstbijzijnde doos die wij hebben. Op Marktplaats staat datzelfde
   artikel gewoon in Verzamelen > Muziek, Artiesten en Beroemdheden, want dáár
   heeft hij het zelf neergezet.

2. GITAREN IS BIJ HEM EEN BETALENDE RUBRIEK. Op 10-09-2026 strandden 24 van zijn
   zoekertjes in precies die drie gitaarrubrieken (/plaats/728/746, /747, /748)
   op de knop "Naar betalen", terwijl zijn zoekertjes in Behuizingen en koffers
   op hetzelfde moment gratis online gingen. De verkeerde rubriek kostte hem dus
   niet alleen vindbaarheid maar ook zijn hele wachtrij.

Het HERPLAATSEN keek al op de advertentiepagina wat de echte categorie is (zie
relist.py, ingebouwd 30-08-2026 na dezelfde klacht van Amanda Haas). Het
KOPIËREN naar een ander kanaal deed dat niet. Dat gat dicht deze reparatie.

WAT DEZE PROEF WEL EN NIET BEWIJST. De nummers in de voorbeelden hieronder zijn
niet door ons vastgesteld en horen dat ook niet te worden: ze komen van de
advertentiepagina van Marktplaats zelf. Precies dat is de reparatie — we hoeven
een rubriek niet te kennen om er goed in te plaatsen. De proef bewijst dat we
overnemen wat de pagina zegt, welke nummers dat ook zijn.

Draaien: python3 -m pytest tests/test_bronrubriek_bij_kopieren.py -q
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as jobs_api            # noqa: E402
import backend.services.crosslist as crosslist  # noqa: E402
from backend.services.mp_enrich import categorie_uit_html  # noqa: E402

# Vast commitnummer, geen HEAD: zodra dit gecommit is vergelijkt HEAD de
# reparatie met zichzelf en bewijst de voor-en-na niets meer.
VOOR_DE_REPARATIE = "f54cbb33"
EGBERT = "bcdf9aa4-314d-49a2-9573-8818ad61073d"

# Zoals Marktplaats het op een advertentiepagina zet. De vorm is echt (zie
# categorie_uit_html en de meting van 30-08-2026 op een openbare advertentie);
# de nummers staan hier als voorbeeld van een rubriek die ONZE lijst niet kent.
PAGINA_VERZAMELEN = (
    '{"itemId":"m2199481234","l1CategoryId":322,"l1CategoryName":"Verzamelen",'
    '"l2CategoryId":1930,"l2CategoryName":"Muziek, Artiesten en Beroemdheden",'
    '"priceInfo":{"priceCents":1295,"priceType":"FIXED"}}'
)
VERZAMELEN = {"l1": 322, "l2": 1930, "l1_naam": "Verzamelen",
              "l2_naam": "Muziek, Artiesten en Beroemdheden"}

# Wat wij ervan maakten zolang we het zelf raadden.
GERADEN_GITAREN = "muziek snaarinstrumenten gitaren akoestisch"


# ── Een database die zich gedraagt als de rijen van Egbert ─────────────────
class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters = db, tabel, []

    def select(self, *_a, **_k):
        return self

    def eq(self, kolom, waarde):
        self.filters.append(("eq", kolom, waarde))
        return self

    def in_(self, kolom, waarden):
        self.filters.append(("in", kolom, list(waarden)))
        return self

    def __getattr__(self, _naam):
        def bouw(*_a, **_k):
            return self
        return bouw

    def execute(self):
        rijen = list(self.db.data.get(self.tabel, []))
        for soort, kolom, waarde in self.filters:
            if soort == "eq":
                rijen = [r for r in rijen if r.get(kolom) == waarde]
            elif soort == "in":
                rijen = [r for r in rijen if r.get(kolom) in waarde]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, **data):
        self.data = data

    def table(self, naam):
        return _Vraag(self, naam)


HET_GITAARTJE = {
    "id": "item-mini-gitaar",
    "user_id": EGBERT,
    "title": "Miniatuur gitaar Fender Stratocaster - verzamelobject",
    "category": GERADEN_GITAREN,
    "photo_urls": ["https://img/mini1.jpg", "https://img/mini2.jpg"],
}


def _db_met_zijn_marktplaats_advertentie():
    return _DB(listings=[{
        "item_id": HET_GITAARTJE["id"],
        "platform": "marktplaats",
        "status": "active",
        "platform_listing_url": "https://www.marktplaats.nl/v/verzamelen/m2199481234",
    }])


# ── 1. De pagina zelf ───────────────────────────────────────────────────────
def test_de_advertentiepagina_zegt_zelf_in_welke_rubriek_hij_staat():
    assert categorie_uit_html(PAGINA_VERZAMELEN) == VERZAMELEN


# ── 2. Het opzoeken vóór het kopiëren ───────────────────────────────────────
def test_de_rubriek_van_de_bronadvertentie_wordt_opgezocht(monkeypatch):
    gevraagd = []

    async def nep_kenmerken(url):
        gevraagd.append(url)
        return {"mp_category": categorie_uit_html(PAGINA_VERZAMELEN)}

    monkeypatch.setattr("backend.services.mp_enrich.advertentie_kenmerken", nep_kenmerken)
    uit = asyncio.run(crosslist.rubriek_van_de_bronadvertentie(
        _db_met_zijn_marktplaats_advertentie(), HET_GITAARTJE, EGBERT))
    assert uit == VERZAMELEN, uit
    assert gevraagd == ["https://www.marktplaats.nl/v/verzamelen/m2199481234"]


def test_een_ophaalronde_die_al_gedaan_is_wordt_niet_overgedaan(monkeypatch):
    """Bij een bulk van 5.533 artikelen scheelt dat 5.533 verzoeken."""
    async def nooit(_url):
        raise AssertionError("de pagina is een tweede keer opgehaald")

    monkeypatch.setattr("backend.services.mp_enrich.advertentie_kenmerken", nooit)
    uit = asyncio.run(crosslist.rubriek_van_de_bronadvertentie(
        _db_met_zijn_marktplaats_advertentie(), HET_GITAARTJE, EGBERT,
        al_gelezen=VERZAMELEN))
    assert uit == VERZAMELEN


def test_een_mislukte_opzoeking_kost_nooit_een_advertentie(monkeypatch):
    """Geen categorie is jammer; niet kunnen publiceren is erger."""
    async def stuk(_url):
        return {}

    async def ook_stuk(*_a, **_k):
        return {}

    monkeypatch.setattr("backend.services.mp_enrich.advertentie_kenmerken", stuk)
    monkeypatch.setattr("backend.services.mp_enrich.kenmerken_via_zoeken", ook_stuk)
    assert asyncio.run(crosslist.rubriek_van_de_bronadvertentie(
        _db_met_zijn_marktplaats_advertentie(), HET_GITAARTJE, EGBERT)) == {}


def test_zonder_advertentie_op_marktplaats_wordt_er_niets_opgehaald(monkeypatch):
    async def nooit(_url):
        raise AssertionError("er is geen bronadvertentie om te lezen")

    monkeypatch.setattr("backend.services.mp_enrich.advertentie_kenmerken", nooit)
    assert asyncio.run(crosslist.rubriek_van_de_bronadvertentie(
        _DB(listings=[]), HET_GITAARTJE, EGBERT)) == {}


# ── 3. Het belandt ook echt in de opdracht ───────────────────────────────────
BRON = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")


def test_publiceren_zoekt_de_rubriek_op_voordat_de_opdracht_klaarstaat():
    publiceren = BRON.split("async def publish_to_platforms(")[1].split("\nasync def ")[0]
    opzoeken = publiceren.index("rubriek_van_de_bronadvertentie(")
    in_de_opdracht = publiceren.index('payload["mp_category"] = mp_rubriek')
    assert opzoeken < in_de_opdracht, (
        "de rubriek wordt pas opgezocht nadat de opdracht al is gevuld")
    # En alleen op de kanalen waar hij iets betekent.
    blok = publiceren[:in_de_opdracht]
    assert 'if platform in ("marktplaats", "2dehands"):' in blok


def test_het_opzoeken_heeft_een_harde_tijdgrens():
    """Marktplaats throttelt met drie herkansingen van samen achttien seconden.
    Keer vijfduizend artikelen in een bulk is dat onwerkbaar."""
    publiceren = BRON.split("async def publish_to_platforms(")[1].split("\nasync def ")[0]
    blok = publiceren.split("rubriek_van_de_bronadvertentie(")[0][-800:]
    assert "asyncio.wait_for" in blok
    assert "timeout=BRONRUBRIEK_SECONDEN" in publiceren
    assert "asyncio.TimeoutError" in publiceren
    assert crosslist.BRONRUBRIEK_SECONDEN <= 20


def test_voor_de_reparatie_keek_het_kopieerpad_hier_niet_naar():
    """Tegenbewijs: zonder dit meet de proef hierboven niets."""
    oud = subprocess.run(
        ["git", "show", f"{VOOR_DE_REPARATIE}:backend/services/crosslist.py"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "rubriek_van_de_bronadvertentie" not in oud, "verkeerd commitnummer gepind"
    assert 'payload["mp_category"]' not in oud, (
        "het kopieerpad deed dit al — dan bewijst deze proef niets")


# ── 4. Groeperen op de rubriek van het FORMULIER, niet op onze eigen naam ───
def test_de_opgezochte_rubriek_bepaalt_de_groep():
    gitaartje = {"category": GERADEN_GITAREN, "mp_category": VERZAMELEN}
    echte_gitaar = {"category": GERADEN_GITAREN,
                    "mp_category": {"l1": 728, "l2": 746}}
    assert jobs_api.rubriek_sleutel(gitaartje) == "mp:322/1930"
    assert jobs_api.rubriek_sleutel(echte_gitaar) == "mp:728/746"
    assert jobs_api.rubriek_sleutel(gitaartje) != jobs_api.rubriek_sleutel(echte_gitaar), (
        "twee artikelen met dezelfde geraden naam landen in verschillende "
        "rubrieken; die mogen niet als één groep gelden")
    # Zonder opgezochte rubriek blijft het bij onze eigen naam, precies zoals het
    # tot nu toe werkte.
    assert jobs_api.rubriek_sleutel({"category": GERADEN_GITAREN}) == GERADEN_GITAREN
    assert jobs_api.rubriek_sleutel({}) == ""
    assert jobs_api.rubriek_sleutel(None) == ""
    # Een half blok is geen rubriek: met alleen een hoofdcategorie kun je geen
    # plaatsformulier openen.
    assert jobs_api.rubriek_sleutel({"category": "x", "mp_category": {"l1": 322}}) == "x"


def test_een_rem_op_gitaren_laat_het_gitaartje_met_rust(monkeypatch):
    """De rem mag alleen raken wat écht in de dure rubriek terechtkomt."""
    wachtrij = [
        {"id": "echte-gitaar", "item_id": "i1", "action": "create", "status": "pending",
         "platform": "2dehands",
         "payload": {"category": GERADEN_GITAREN, "mp_category": {"l1": 728, "l2": 746}}},
        {"id": "miniatuur", "item_id": "i2", "action": "create", "status": "pending",
         "platform": "2dehands",
         "payload": {"category": GERADEN_GITAREN, "mp_category": VERZAMELEN}},
    ]
    geannuleerd = []

    class _Wachtrij:
        def __init__(self, tabel):
            self.tabel, self.filters, self.wijziging = tabel, {}, None

        def select(self, *_a, **_k):
            return self

        def update(self, waarden):
            self.wijziging = waarden
            return self

        def eq(self, veld, waarde):
            self.filters[veld] = waarde
            return self

        def in_(self, veld, waarden):
            self.filters[f"in:{veld}"] = list(waarden)
            return self

        def __getattr__(self, _naam):
            def bouw(*_a, **_k):
                return self
            return bouw

        def execute(self):
            klaar = type("R", (), {"data": []})()
            if self.tabel == "jobs" and self.wijziging is None:
                klaar.data = [j for j in wachtrij
                              if j["status"] == self.filters.get("status", j["status"])]
            if self.tabel == "jobs" and self.wijziging is not None:
                geannuleerd.extend(self.filters.get("in:id", []))
            return klaar

    db = type("D", (), {"table": staticmethod(lambda naam: _Wachtrij(naam))})()
    monkeypatch.setattr(jobs_api, "execute_with_retry",
                        lambda bouwer, *_a, **_k: bouwer.execute())
    monkeypatch.setattr(jobs_api, "fetch_all", lambda *_a, **_k: [])
    aantal = jobs_api._stop_wachtrij(db, EGBERT, "2dehands", "reden", rubriek="mp:728/746")
    assert aantal == 1, f"{aantal} teruggenomen in plaats van 1"
    assert geannuleerd == ["echte-gitaar"], geannuleerd


# ── 5. Een rubriek die al eens geld vroeg, niet nog eens proberen ───────────
ECHTE_FOUT = (
    'Error: Not published — complete the fields marked in red and click publish yourself. '
    'Je hebt geen zoekertjesvorm gekozen. | Still on /plaats/728/748?title=, knop '
    '"Naar betalen" | Free option: knop niet gevonden | Page says: Plaats zoekertje '
    'Gekozen categorie Muziek en Instrumenten Gitaren | Elektrisch Wijzigen '
    'Dit is een betalende categorie'
)


def _mislukte_opdrachten():
    return _DB(jobs=[
        {"user_id": EGBERT, "platform": "2dehands", "action": "create", "status": "error",
         "payload": {"category": "muziek snaarinstrumenten gitaren elektrisch",
                     "mp_category": {"l1": 728, "l2": 748}},
         "result": {"error": ECHTE_FOUT}},
        # Een gewone mislukking in een gratis rubriek mag hier nooit in belanden.
        {"user_id": EGBERT, "platform": "2dehands", "action": "create", "status": "error",
         "payload": {"category": "muziek behuizingen en koffers"},
         "result": {"error": "Uploading the photos took too long"}},
    ])


def test_een_rubriek_die_geld_vroeg_wordt_onthouden():
    duur = jobs_api.betaalde_rubrieken(_mislukte_opdrachten(), EGBERT, "2dehands")
    assert list(duur) == ["mp:728/748"], duur
    # Met de naam zoals 2dehands hem toont, niet onze sleutel.
    assert duur["mp:728/748"] == "Muziek en Instrumenten Gitaren | Elektrisch"


def test_ook_opdrachten_van_voor_deze_reparatie_tellen_mee():
    """Zijn 24 mislukkingen van 10-09 droegen nog geen opgezochte rubriek.

    De extensie zet in de foutmelding wél op welke pagina ze bleef staan. Zonder
    die regel zou de rem pas gaan werken na de eerste NIEUWE mislukking — precies
    de mislukking die we willen voorkomen.
    """
    db = _DB(jobs=[{
        "user_id": EGBERT, "platform": "2dehands", "action": "create", "status": "error",
        "payload": {"category": "muziek snaarinstrumenten gitaren elektrisch"},
        "result": {"error": ECHTE_FOUT},
    }])
    duur = jobs_api.betaalde_rubrieken(db, EGBERT, "2dehands")
    assert "mp:728/748" in duur, duur
    # En onder onze eigen naam ook, want een opdracht zonder opgezochte rubriek
    # wordt op die naam herkend.
    assert "muziek snaarinstrumenten gitaren elektrisch" in duur, duur


def test_een_kanaalbrede_betaalmuur_telt_hier_niet_mee():
    """Die heeft zijn eigen, zwaardere rem; hij zegt niets over één rubriek."""
    db = _DB(jobs=[{
        "user_id": EGBERT, "platform": "2dehands", "action": "create", "status": "error",
        "payload": {"category": "x", "mp_category": {"l1": 728, "l2": 748}},
        "result": {"error": "2dehands.be/payments/orderOverview — betalende categorie"},
    }])
    assert jobs_api.betaalde_rubrieken(db, EGBERT, "2dehands") == {}


def test_publiceren_kijkt_vooraf_of_die_rubriek_geld_vraagt():
    publiceren = BRON.split("async def publish_to_platforms(")[1].split("\nasync def ")[0]
    blok = publiceren.split("betaalde_rubriek.get(platform)")[1][:600]
    assert "rubriek_sleutel(payload)" in blok, (
        "de rem moet kijken naar de rubriek waar deze opdracht ECHT in landt")
    assert '"status": "blocked"' in blok
    assert "continue" in blok, "er mag hier geen opdracht in de wachtrij komen"
    # En de melding mag niet beweren dat we een wachtrij hebben teruggenomen:
    # er is er geen, we hebben er juist geen aangemaakt.
    assert "vooraf=True" in blok


def test_de_melding_vooraf_belooft_geen_teruggenomen_wachtrij():
    vooraf = jobs_api._melding_rubriek_vraagt_geld(
        "2dehands", "Muziek en Instrumenten Gitaren | Elektrisch", vooraf=True)
    assert "We did not queue this one" in vooraf
    assert "taken the rest of your queue" not in vooraf
    assert "nothing was ordered" in vooraf.lower()
    assert "other categories" in vooraf
    # De bestaande tekst (achteraf) blijft ongewijzigd.
    achteraf = jobs_api._melding_rubriek_vraagt_geld("2dehands", "Gitaren | Elektrisch")
    assert "We have taken the rest of your queue" in achteraf


if __name__ == "__main__":  # handig bij het sleutelen
    raise SystemExit(pytest.main([__file__, "-q"]))
