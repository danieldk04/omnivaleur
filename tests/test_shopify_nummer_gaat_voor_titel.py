"""Shopify-scan: het artikelnummer van de variant gaat voor de titel.

WAAROM DIT ER IS (24-09-2026, Revaleur)
Revaleur heeft veel stukken met exact dezelfde titel ("Grey Ralph Lauren Zip
Vest - Men L - Very Good"), alleen het nummer verschilt. De titelsleutel zag die
als tweelingen en koos er één. Zo werd Shopify-product 1014 voorgesteld als
artikel 945 (al aan een ánder Shopify-product gekoppeld, dus "Twice in your
Shopify store"), terwijl artikel 1014 gewoon op Marktplaats en 2dehands stond.
Na koppelen had een verkoop in de winkel 945 overal weggehaald en 1014 laten
staan. Gemeten op de echte winkel: 5 van de 12 van die meldingen waren zo fout.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.filters, self.op = db, tabel, {}, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def insert(self, rij): self.op, self.rij = "insert", rij; return self
    def upsert(self, rijen, **_k): self.op, self.rijen = "upsert", rijen; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, *_a): return self
    def is_(self, *_a): return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a): return self

    def execute(self):
        if self.op == "upsert":
            self.db.import_candidates.extend(dict(r) for r in self.rijen)
            return type("R", (), {"data": list(self.rijen)})()
        if self.op == "insert":
            getattr(self.db, self.tabel).append(dict(self.rij))
            return type("R", (), {"data": [self.rij]})()
        rijen = [r for r in getattr(self.db, self.tabel, [])
                 if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings
        self.import_candidates, self.jobs = [], []

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture(autouse=True)
def _lokale_helpers(monkeypatch):
    monkeypatch.setattr(api, "fetch_all", lambda q: q().execute().data or [])
    monkeypatch.setattr(api, "fetch_all_in", lambda q, _k, _w: q().execute().data or [])


JOB = {"id": "j1", "user_id": "u1", "platform": "shopify", "action": "scan"}
TITEL = "Grey Ralph Lauren Zip Vest - Men L - Very Good"


def _item(iid, nummer, sku=None):
    return {"id": iid, "user_id": "u1", "title": f"({nummer}) {TITEL}" if nummer else TITEL,
            "sku": sku or f"imp-{iid}", "brand": "Ralph Lauren"}


def _db():
    return _DB(
        items=[_item("a945", 945), _item("b939", 939), _item("c1014", 1014)],
        listings=[
            {"id": "l1", "item_id": "a945", "platform": "shopify", "status": "active",
             "platform_listing_id": "9001"},
            {"id": "l2", "item_id": "b939", "platform": "shopify", "status": "active",
             "platform_listing_id": "9002"},
            {"id": "l3", "item_id": "c1014", "platform": "marktplaats", "status": "active",
             "platform_listing_id": "m1"},
        ])


def _scan(db, sku, pid="9100"):
    api._store_scan_results(db, JOB, [{"platform_listing_id": pid, "title": TITEL,
                                       "price": 60, "sku": sku}])
    return next(c for c in db.import_candidates if c["platform_listing_id"] == pid)


def test_product_gaat_naar_het_artikel_met_zijn_eigen_nummer():
    db = _db()
    assert _scan(db, "1014")["suggested_item_id"] == "c1014"
    # En daarmee hangt het Shopify-product aan het artikel dat op Marktplaats
    # staat: een verkoop in de winkel haalt het dáár weg.
    assert any(l["item_id"] == "c1014" and l["platform"] == "shopify"
               and l["platform_listing_id"] == "9100" for l in db.listings)


def test_zelfde_titel_ander_nummer_is_geen_koppeling():
    db = _db()
    assert _scan(db, "352")["suggested_item_id"] is None
    assert not any(l["platform_listing_id"] == "9100" for l in db.listings)


def test_artikel_zonder_eigen_nummer_mag_nog_op_titel():
    db = _DB(items=[{"id": "x", "user_id": "u1", "title": "Blauwe vaas", "sku": "imp-x",
                     "brand": None}], listings=[])
    api._store_scan_results(db, JOB, [{"platform_listing_id": "7", "title": "Blauwe vaas",
                                       "price": 5, "sku": "V-12"}])
    assert db.import_candidates[0]["suggested_item_id"] == "x"


def test_bekend_productnummer_blijft_altijd_winnen():
    db = _db()
    assert _scan(db, "1014", pid="9001")["suggested_item_id"] == "a945"
