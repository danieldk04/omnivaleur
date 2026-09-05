"""Waarom Amanda's nieuw geplaatste Marktplaats-advertenties "niet werden geïmporteerd".

WAAROM DIT ER IS (05-09-2026, Amanda Haas)
"Ook importeert hij nieuw geplaatste advertenties niet van marktplaats."
Nagemeten: die advertenties wérden gevonden. Ze stonden alleen te verdrinken.
Op haar te-beoordelen lijst stonden 117 Marktplaats-advertenties, waarvan er
111 allang aan een artikel in haar overzicht hingen — hun advertentienummer
stond gewoon in `listings`. Alleen zes waren er echt nieuw.

Hoe die 111 daar kwamen: elke publicatie en elke herplaatsing levert een NIEUW
advertentienummer op. Een nummer dat de vorige scan nog niet kende gold als
"nieuw, de verkoper moet beslissen" — ook als wij die advertentie zelf een uur
eerder hadden geplaatst.

De regel: hangt het advertentienummer al aan een artikel, dan valt er niets te
beslissen. Alleen het NUMMER telt; een gelijkende titel is een vermoeden.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters = {}
        self.op, self.rijen_in = None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, *_a): return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a): return self

    def upsert(self, rijen, **_k):
        self.op = "upsert"
        self.rijen_in = rijen if isinstance(rijen, list) else [rijen]
        return self

    def execute(self):
        if self.op == "upsert":
            self.db.import_candidates.extend(dict(r) for r in self.rijen_in)
            return type("R", (), {"data": list(self.rijen_in)})()
        bron = getattr(self.db, self.tabel, [])
        rijen = [r for r in bron
                 if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings
        self.import_candidates = []
        self.jobs = []

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture(autouse=True)
def _lokale_helpers(monkeypatch):
    monkeypatch.setattr(api, "fetch_all", lambda q: q().execute().data or [])
    monkeypatch.setattr(api, "fetch_all_in",
                        lambda q, _kolom, _waarden: q().execute().data or [])


ITEM = {"id": "it1", "user_id": "u1", "title": "AH hamster knuffel kok nieuw",
        "sku": "IMP-1", "brand": None}
JOB = {"id": "j1", "user_id": "u1", "platform": "marktplaats", "action": "scan"}


def _kandidaat(db, nummer):
    return next(c for c in db.import_candidates
                if str(c["platform_listing_id"]) == nummer)


def test_een_advertentie_die_wij_zelf_plaatsten_hoeft_geen_beoordeling():
    """Dit is de 111. Ze hingen al aan een artikel en stonden tóch te wachten."""
    db = _DB(
        items=[ITEM],
        listings=[{"id": "l1", "item_id": "it1", "platform": "marktplaats",
                   "status": "active", "platform_listing_id": "m2439067409"}],
    )
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "m2439067409",
         "title": "AH hamster knuffel kok nieuw", "price": 10},
    ])
    assert _kandidaat(db, "m2439067409")["status"] == "linked"


def test_een_advertentie_die_zij_zelf_plaatste_wacht_nog_steeds_op_haar():
    """Dit zijn de zes. Die moeten juist wél zichtbaar blijven."""
    db = _DB(items=[ITEM], listings=[])
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "m2437013996",
         "title": "Switch On koffieapparaat nieuw", "price": 25},
    ])
    assert _kandidaat(db, "m2437013996")["status"] == "pending"


def test_een_gelijkende_titel_is_geen_bewijs():
    """Titelherkenning is een suggestie. Alleen het advertentienummer bewijst
    dat deze advertentie al in het overzicht staat."""
    db = _DB(
        items=[ITEM],
        listings=[{"id": "l1", "item_id": "it1", "platform": "marktplaats",
                   "status": "active", "platform_listing_id": "m-oud"}],
    )
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "m-nieuw",
         "title": "AH hamster knuffel kok nieuw", "price": 10},
    ])
    k = _kandidaat(db, "m-nieuw")
    assert k["status"] == "pending"
    assert k["suggested_item_id"] == "it1", "de suggestie hoort er wel te staan"


def test_een_eerdere_beslissing_blijft_staan():
    """Wat de verkoper al besliste (genegeerd, geïmporteerd) wint altijd."""
    db = _DB(items=[ITEM], listings=[])
    db.import_candidates_bestaand = []
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "m1", "title": "iets", "price": 1},
    ])
    # Tweede scan, nu met een eerdere beslissing in de tabel.
    db.import_candidates.clear()
    db.import_candidates.append({"user_id": "u1", "platform": "marktplaats",
                                 "platform_listing_id": "m1", "status": "ignored"})
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "m1", "title": "iets", "price": 1},
    ])
    assert _kandidaat(db, "m1")["status"] == "ignored"
