"""De omschrijving werd op het verkeerde kanaal gezocht.

AANLEIDING (07-09-2026, De Juiste Toon): "Waarom vult hij de discription niet
automatisch in?" Zijn dashboard toonde bij artikel na artikel "No description
yet — needed on every platform".

GEMETEN, niet aangenomen, op zijn echte voorraad van 1.319 artikelen:

  * 197 artikelen zonder omschrijving. Van die 197 heeft er 194 een
    2dehands-advertentie, 8 een Marktplaats-advertentie en 2 geen enkele.
  * Alle 196 die op 05-09 werden geïmporteerd stonden nog exact zoals ze binnen
    kwamen: `created_at` en `updated_at` op dezelfde seconde. De aanvulronde die
    elk kwartier draait had ze in twee dagen niet één keer aangeraakt.
  * De echte ronde erop losgelaten meldde: "0 van 20 items teruggevonden".

OORZAAK. `verrijk` zocht altijd op marktplaats.nl. Zijn advertenties staan op
2dehands.be. Daar komt een tweede kwaal bij: de artikelen zonder tekst staan
vooraan in de rij (`_urgentie`), dus de hele beurt van 150 ging op aan
2dehands-advertenties zoeken op Marktplaats. Zijn acht Marktplaats-artikelen
kwamen daardoor evenmin aan de beurt.

BEWIJS DAT HET KAN. Met dezelfde functies op 2dehands.be: verkopersnummer
gevonden, 6 van 6 vastzittende artikelen teruggevonden, omschrijvingen van 818
tot 932 tekens. Daarna de echte ronde droog gedraaid: 20 van 20 teruggevonden,
20 omschrijvingen, tegen 0 van 20 op de oude weg.
"""
import asyncio
import types
from pathlib import Path

import pytest

from backend.services import mp_enrich

WORTEL = Path(__file__).resolve().parents[1]

# Toons gemeten verhouding, op schaal: bijna alles op 2dehands, een handvol op
# Marktplaats, en twee artikelen waarvan we het kanaal niet weten.
OP_2DEHANDS = 190
OP_MARKTPLAATS = 8
ZONDER_ADVERTENTIE = 2


def _voorraad():
    items, listings = [], []
    for i in range(OP_2DEHANDS + OP_MARKTPLAATS + ZONDER_ADVERTENTIE):
        items.append({
            "id": f"i{i:04d}",
            "user_id": "toon",
            "title": f"Grand foulard woonkleed {i}",
            "price": 25.0,
            "photo_urls": ["een.jpg"],     # import levert één foto
            "brand": "", "size": "", "color": "", "condition": "",
            "description": None,           # dit is de klacht
        })
        if i < OP_2DEHANDS:
            listings.append({"item_id": f"i{i:04d}", "platform": "2dehands",
                             "status": "active"})
        elif i < OP_2DEHANDS + OP_MARKTPLAATS:
            listings.append({"item_id": f"i{i:04d}", "platform": "marktplaats",
                             "status": "active"})
    return items, listings


class NepDb:
    """Kent het verschil tussen `items` en `listings` — daar draait het hier om."""

    def __init__(self, items, listings, listings_stuk=False):
        self.items = {r["id"]: dict(r) for r in items}
        self.listings = listings
        self.listings_stuk = listings_stuk

    def table(self, naam):
        if naam == "listings" and self.listings_stuk:
            raise RuntimeError("verbinding weg")
        return NepTabel(self, naam)


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam
        self.venster = None
        self.alleen_leeg = False
        self.ids = None
        self.doel = None
        self.patch = None

    def select(self, *a, **kw):
        return self

    def or_(self, *a, **kw):
        self.alleen_leeg = True
        return self

    def in_(self, kolom, waarden):
        self.ids = list(waarden)
        return self

    def eq(self, kolom, waarde):
        if kolom == "id":
            self.doel = waarde
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def limit(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def range(self, start, eind):
        self.venster = (start, eind)
        return self

    def execute(self):
        if self.patch is not None:
            self.db.items[self.doel].update(self.patch)
            return types.SimpleNamespace(data=[{"id": self.doel}])
        if self.naam == "listings":
            rijen = list(self.db.listings)
            if self.ids is not None:
                rijen = [r for r in rijen if r["item_id"] in self.ids]
            return types.SimpleNamespace(data=rijen)
        rijen = list(self.db.items.values())
        if self.alleen_leeg:
            rijen = [r for r in rijen if not (r.get("description") or "").strip()]
        if self.ids is not None:
            rijen = [r for r in rijen if r["id"] in self.ids]
        if self.venster:
            start, eind = self.venster
            rijen = rijen[start:eind + 1]
        return types.SimpleNamespace(data=rijen)


@pytest.fixture(autouse=True)
def _schone_beurt():
    mp_enrich._beurt_per_verkoper.clear()


@pytest.fixture
def _nep_net(monkeypatch):
    """Beide marktplaatsen nabootsen en onthouden waar er gezocht is."""
    bezocht = {"zoek": [], "paginas": []}

    async def verkoper(_client, _titels, zoek_url=mp_enrich.ZOEK, **kw):
        bezocht["zoek"].append(zoek_url)
        return 44572806

    async def lijst(_client, _vid, deadline=0, zoek_url=mp_enrich.ZOEK,
                    basis=mp_enrich.BASIS, **kw):
        bezocht["zoek"].append(zoek_url)
        return {mp_enrich._sleutel(f"Grand foulard woonkleed {i}"):
                {"url": f"{basis}/v/a/{i}", "price": 25.0}
                for i in range(OP_2DEHANDS + OP_MARKTPLAATS + ZONDER_ADVERTENTIE)}

    async def pagina(_client, url):
        bezocht["paginas"].append(url)
        return {"description": f"volledige advertentietekst van {url}",
                "photo_urls": ["a.jpg", "b.jpg"],
                "brand": "", "size": "", "color": "", "condition": ""}

    async def _geen_pauze(*_a, **_k):
        return None

    monkeypatch.setattr(mp_enrich, "zoek_verkoper_id", verkoper)
    monkeypatch.setattr(mp_enrich, "haal_advertenties", lijst)
    monkeypatch.setattr(mp_enrich, "volledige_advertentie", pagina)
    monkeypatch.setattr(mp_enrich.asyncio, "sleep", _geen_pauze)
    return bezocht


def test_de_oude_ronde_ging_helemaal_op_aan_het_verkeerde_kanaal():
    """De voor-meting: zonder kanaalfilter bestaat de hele beurt uit artikelen
    die op Marktplaats niet te vinden zijn, en komen de acht die daar wél staan
    nooit aan de beurt."""
    items, _ = _voorraad()
    kandidaten = [r for r in items if mp_enrich._mist_iets(r)]
    beurt = mp_enrich._deze_ronde(kandidaten, "toon", 20)
    op_2dehands = {f"i{i:04d}" for i in range(OP_2DEHANDS)}
    assert {r["id"] for r in beurt} <= op_2dehands


def test_het_kanaal_met_de_meeste_lege_teksten_wint():
    items, listings = _voorraad()
    db = NepDb(items, listings)
    assert asyncio.run(mp_enrich.kanaal_met_meeste_gaten(db, "toon")) == "2dehands"


def test_er_wordt_op_2dehands_gezocht_en_niet_op_marktplaats(_nep_net):
    items, listings = _voorraad()
    db = NepDb(items, listings)
    asyncio.run(mp_enrich.verrijk(db, "toon", schrijf=True, maximaal=20,
                                  platform="2dehands"))
    assert _nep_net["zoek"], "er is helemaal niet gezocht"
    assert all("2dehands.be" in u for u in _nep_net["zoek"]), _nep_net["zoek"]
    assert all("2dehands.be" in u for u in _nep_net["paginas"])


def test_de_teksten_komen_er_ook_echt_in(_nep_net):
    items, listings = _voorraad()
    db = NepDb(items, listings)
    uit = asyncio.run(mp_enrich.verrijk(db, "toon", schrijf=True, maximaal=20,
                                        platform="2dehands"))
    assert uit["omschrijving"] == 20
    gevuld = [r for r in db.items.values() if (r.get("description") or "").strip()]
    assert len(gevuld) == 20


def test_de_marktplaats_ronde_pakt_alleen_marktplaats_artikelen(_nep_net):
    """Zo komen die acht wél aan de beurt, in plaats van achter 190
    onvindbare artikelen te blijven staan."""
    items, listings = _voorraad()
    db = NepDb(items, listings)
    asyncio.run(mp_enrich.verrijk(db, "toon", schrijf=True, maximaal=20,
                                  platform="marktplaats"))
    gevuld = {r["id"] for r in db.items.values() if (r.get("description") or "").strip()}
    op_2dehands = {f"i{i:04d}" for i in range(OP_2DEHANDS)}
    assert not (gevuld & op_2dehands)
    # De acht op Marktplaats plus de twee zonder advertentie: tien, en die
    # passen alle tien binnen de beurt van twintig.
    assert len(gevuld) == OP_MARKTPLAATS + ZONDER_ADVERTENTIE


def test_een_artikel_zonder_advertentie_blijft_bij_het_standaardkanaal(_nep_net):
    """Wie geen advertentierijen heeft moet zich precies gedragen zoals
    voorheen, anders repareert deze wijziging het ene account en breekt ze het
    andere."""
    items, _ = _voorraad()
    db = NepDb(items, [])          # geen enkele advertentie bekend
    uit = asyncio.run(mp_enrich.verrijk(db, "toon", schrijf=True, maximaal=20,
                                        platform="marktplaats"))
    assert uit["omschrijving"] == 20


def test_een_leesfout_stopt_het_andere_kanaal_maar_niet_het_standaardkanaal(_nep_net):
    items, listings = _voorraad()
    stuk = NepDb(items, listings, listings_stuk=True)
    uit = asyncio.run(mp_enrich.verrijk(stuk, "toon", schrijf=True, maximaal=20,
                                        platform="2dehands"))
    assert uit["omschrijving"] == 0
    assert "could not tell" in uit["reden"]

    stuk2 = NepDb(items, listings, listings_stuk=True)
    uit2 = asyncio.run(mp_enrich.verrijk(stuk2, "toon", schrijf=True, maximaal=20,
                                         platform="marktplaats"))
    assert uit2["omschrijving"] == 20


def test_de_beurtteller_van_de_twee_kanalen_loopt_niet_door_elkaar(_nep_net):
    items, listings = _voorraad()
    db = NepDb(items, listings)
    asyncio.run(mp_enrich.verrijk(db, "toon", schrijf=False, maximaal=5,
                                  platform="2dehands"))
    # Het standaardkanaal houdt de kale user_id als sleutel: daar mag niets aan
    # veranderd zijn voor de accounts die al draaiden.
    assert "toon@2dehands" in mp_enrich._beurt_per_verkoper
    assert "toon" not in mp_enrich._beurt_per_verkoper


def test_de_planner_en_de_knop_kiezen_allebei_het_kanaal():
    """Een keuze die alleen in de ene aanroeper zit, repareert de andere niet."""
    enrich = (WORTEL / "backend" / "services" / "mp_enrich.py").read_text(encoding="utf-8")
    blok = enrich.split("async def vul_ontbrekende_teksten_aan(")[1]
    assert "kanaal_met_meeste_gaten(" in blok
    assert "platform=kanaal" in blok

    items_api = (WORTEL / "backend" / "api" / "items.py").read_text(encoding="utf-8")
    knop = items_api.split("async def fill_from_marktplaats(")[1]
    knop = knop[:knop.index("async def fill_from_vinted(")]
    assert "kanaal_met_meeste_gaten(" in knop
    assert "platform=kanaal" in knop
