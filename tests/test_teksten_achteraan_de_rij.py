"""De teksten die achteraan de rij stonden kwamen nooit aan de beurt.

Amanda Haas, 01-09-2026: "Hij haalt wel nog steeds niet alle teksten uit de
omschrijvingen in de advertenties op." De aanvulronde uit 29-08 draaide, maar
deed bij haar elk kwartier niets.

Nagemeten aan haar echte voorraad (479 items, verkopersnummer 12058863):
459 items tellen als "mist iets" — ze verkoopt brocante, dus merk en maat zijn
leeg en blijven dat. Van de eerste 150 uit die lijst had er geen enkele een lege
omschrijving; het eerste item zonder tekst stond op plek 150, één plaats achter
de afkapstreep van `open_[:maximaal]`. Elke ronde opnieuw, en dezelfde muur zat
voor de knop "Fill from Marktplaats".

Deze test zet die vorm na en draait de echte `verrijk` erdoorheen, met de
selectie van vóór vandaag ernaast.
"""
import asyncio
import types

import pytest

from backend.services import mp_enrich


# Amanda's gemeten vorm: 479 items, de eerste 150 hebben tekst, daarna zitten de
# 200 zonder tekst. Geen enkel item heeft merk of maat, dus alles "mist iets".
EERST_MET_TEKST = 150
ZONDER_TEKST = 200
TOTAAL = 479


def _voorraad():
    items = []
    for i in range(TOTAAL):
        heeft_tekst = i < EERST_MET_TEKST or i >= EERST_MET_TEKST + ZONDER_TEKST
        items.append({
            "id": f"i{i:04d}",
            "user_id": "amanda",
            "title": f"Vintage artikel {i}",
            "price": 12.5,
            "photo_urls": ["a.jpg", "b.jpg"],
            "brand": "",          # brocante: nooit een merk
            "size": "",           # en nooit een maat
            "color": "bruin",
            "condition": "used",
            "description": "haar eigen tekst" if heeft_tekst else None,
        })
    return items


class NepDb:
    """Alleen wat `verrijk` echt aanroept."""

    def __init__(self, items):
        self.items = {r["id"]: dict(r) for r in items}
        self.updates = {}

    def table(self, naam):
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
        self.alleen_leeg = True          # description.is.null,description.eq.
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
        if self.patch is not None:       # een update
            self.db.items[self.doel].update(self.patch)
            self.db.updates.setdefault(self.doel, {}).update(self.patch)
            return types.SimpleNamespace(data=[{"id": self.doel}])
        rijen = list(self.db.items.values())
        if self.alleen_leeg:
            rijen = [r for r in rijen if not (r.get("description") or "").strip()]
        if self.ids is not None:
            rijen = [r for r in rijen if r["id"] in self.ids]
        if self.venster:                 # fetch_all bladert
            start, eind = self.venster
            rijen = rijen[start:eind + 1]
        return types.SimpleNamespace(data=rijen)


@pytest.fixture(autouse=True)
def _schone_beurt():
    mp_enrich._beurt_per_verkoper.clear()


@pytest.fixture
def _geen_marktplaats(monkeypatch):
    """Marktplaats nabootsen: elke advertentie bestaat en heeft een tekst."""
    async def verkoper(_client, _titels):
        return 12058863

    async def lijst(_client, _vid, deadline=0, **kw):
        return {mp_enrich._sleutel(f"Vintage artikel {i}"):
                {"url": f"https://www.marktplaats.nl/v/a/{i}", "price": 12.5,
                 "title": f"Vintage artikel {i}"}
                for i in range(TOTAAL)}

    async def pagina(_client, url):
        return {"description": f"volledige advertentietekst van {url}",
                "photo_urls": ["a.jpg", "b.jpg", "c.jpg"],
                "brand": "", "size": "", "color": "", "condition": ""}

    monkeypatch.setattr(mp_enrich, "zoek_verkoper_id", verkoper)
    monkeypatch.setattr(mp_enrich, "haal_advertenties", lijst)
    monkeypatch.setattr(mp_enrich, "volledige_advertentie", pagina)
    # De beleefde pauzes tussen aanvragen bij Marktplaats overslaan: er is hier
    # geen Marktplaats om beleefd tegen te zijn, en 150 items x 0,25 seconde
    # zou het tijdsbudget van de ronde zelf opsouperen.
    async def _geen_pauze(*_a, **_k):
        return None

    monkeypatch.setattr(mp_enrich.asyncio, "sleep", _geen_pauze)


def test_de_oude_selectie_zag_geen_enkele_lege_tekst():
    """Waarom er niets gebeurde: de afkapstreep lag vóór het eerste gat."""
    rijen = _voorraad()
    for r in rijen:
        r["heeft_tekst"] = bool(r["description"])
    open_ = [r for r in rijen if mp_enrich._mist_iets(r)]
    oud = open_[:150]                     # de regel van vóór 01-09-2026
    assert len(open_) == TOTAAL           # alles mist merk en maat
    assert sum(1 for r in oud if not r["heeft_tekst"]) == 0


def test_de_lege_teksten_staan_nu_vooraan():
    rijen = _voorraad()
    for r in rijen:
        r["heeft_tekst"] = bool(r["description"])
    open_ = [r for r in rijen if mp_enrich._mist_iets(r)]
    nu = mp_enrich._deze_ronde(open_, "amanda", 150)
    assert len(nu) == 150
    assert all(not r["heeft_tekst"] for r in nu)


def test_een_ronde_vult_de_teksten_echt(_geen_marktplaats):
    """De echte `verrijk`, niet een nagebouwde versie ervan."""
    db = NepDb(_voorraad())
    uit = asyncio.run(mp_enrich.verrijk(db, "amanda", schrijf=True, maximaal=150))
    assert uit["omschrijving"] == 150
    geschreven = [p for p in db.updates.values() if "description" in p]
    assert len(geschreven) == 150


def test_twee_rondes_maken_alle_teksten_af(_geen_marktplaats):
    db = NepDb(_voorraad())
    totaal = 0
    for _ in range(2):
        totaal += asyncio.run(
            mp_enrich.verrijk(db, "amanda", schrijf=True, maximaal=150))["omschrijving"]
    assert totaal == ZONDER_TEKST
    leeg = [r for r in db.items.values() if not (r.get("description") or "").strip()]
    assert leeg == []


def test_bestaande_tekst_blijft_staan(_geen_marktplaats):
    """Wat de verkoper zelf schreef mag deze ronde nooit overschrijven."""
    db = NepDb(_voorraad())
    for _ in range(3):
        asyncio.run(mp_enrich.verrijk(db, "amanda", schrijf=True, maximaal=150))
    eigen = [r for r in db.items.values() if r["description"] == "haar eigen tekst"]
    assert len(eigen) == TOTAAL - ZONDER_TEKST


def test_een_onvulbare_kop_houdt_de_rest_niet_eeuwig_tegen():
    """Dezelfde fout in een nieuw jasje: een kop die nooit gevuld raakt.

    Levert een ronde niets op, dan schuift de startplek door, zodat de items
    daarachter alsnog aan de beurt komen."""
    open_ = [{"id": f"i{i}", "heeft_tekst": False, "price": 1,
              "photo_urls": ["a", "b"]} for i in range(400)]
    eerste = mp_enrich._deze_ronde(open_, "vast", 150)
    tweede = mp_enrich._deze_ronde(open_, "vast", 150)
    derde = mp_enrich._deze_ronde(open_, "vast", 150)
    gezien = {r["id"] for r in eerste + tweede + derde}
    assert len(gezien) == 400
    assert not ({r["id"] for r in eerste} & {r["id"] for r in tweede})


def test_na_een_geslaagde_ronde_begint_de_volgende_weer_vooraan(_geen_marktplaats):
    db = NepDb(_voorraad())
    asyncio.run(mp_enrich.verrijk(db, "amanda", schrijf=True, maximaal=150))
    assert "amanda" not in mp_enrich._beurt_per_verkoper
