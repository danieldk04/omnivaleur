"""Een verkoop mag alleen op een kanaal geboekt worden dat het zelf zegt.

WAAROM DIT ER IS (17-09-2026, Daniel — artikel 1313)
In Analytics stond "(1313) Blue/White Zara Rugby Longsleeve" als verkocht op
VINTED, op 12-09, zonder bedrag. In werkelijkheid was het op Shopify verkocht:
bestelling #1079 van 06-09, EUR 14,99. De Vinted-advertentie (9256552127) geeft
404 — hij was weggehaald, en Vinted heeft nooit gezegd dat hij daar verkocht is.

Twee wegen brachten dat teweeg, en die worden hier allebei dichtgehouden:

1. De bestellingenpagina van Vinted werd met een breed net gelezen: elke rij die
   niet zichtbaar geannuleerd was telde als verkoop. Een gewoon gesprek over een
   artikel kon zo een verkoop worden. Een echte bestelling toont altijd het
   bedrag; zonder bedrag boeken we niets.
2. Een advertentie die uit de Vinted-kast verdwenen is gold als verkocht op
   Vinted. Dat is geen uitspraak van Vinted maar van ons (zie
   tests/test_vinted_weg_wordt_een_vraag.py).

En als vangnet erachter: handle_item_sold boekt niets meer zonder bewijs. Wie
geen bewijs meegeeft, krijgt de ja/nee-vraag in plaats van een verkoop.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.op, self.velden = {}, {}, None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def insert(self, v): self.op, self.velden = "insert", v; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def neq(self, k, v): self.filters[f"neq:{k}"] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self

    def _match(self, r):
        for k, v in self.filters.items():
            if k.startswith("neq:"):
                if r.get(k[4:]) == v:
                    return False
            elif r.get(k) != v:
                return False
        return all(r.get(k) in vals for k, vals in self.in_filters.items())

    def execute(self):
        bron = {"items": self.db.items, "listings": self.db.listings}.get(self.tabel, self.db.rest)
        if self.op == "insert":
            bron.append(dict(self.velden))
            return type("R", (), {"data": [dict(self.velden)]})()
        rijen = [r for r in bron if self._match(r)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings, self.rest = items, listings, []

    def table(self, naam):
        return _Q(self, naam)


def _situatie():
    items = [{"id": "i1", "user_id": "u1", "title": "(1313) Blue/White Zara Rugby Longsleeve"}]
    listings = [
        {"id": "v1", "item_id": "i1", "platform": "vinted", "status": "active",
         "platform_listing_id": "9256552127"},
        {"id": "s1", "item_id": "i1", "platform": "shopify", "status": "active",
         "platform_listing_id": "15843080372554"},
    ]
    return _DB(items, listings), listings


def _draai(monkeypatch, db, **kw):
    monkeypatch.setattr(cl, "get_db", lambda: db)

    async def _naast(fn, *_a, **_k):
        return fn()

    monkeypatch.setattr(cl, "naast_de_lus", _naast)
    try:
        asyncio.run(cl.handle_item_sold("i1", "vinted", **kw))
    except AttributeError as e:          # de nagebootste bouwer stopt bij het opruimen
        assert any(w in str(e) for w in ("in_", "order", "single")), f"onverwachte fout: {e}"


def test_zonder_bewijs_wordt_er_niets_geboekt(monkeypatch):
    db, listings = _situatie()
    _draai(monkeypatch, db)
    assert not [l for l in listings if l["status"] == "sold"], (
        "zonder bewijs dat Vinted het zelf zegt mag er geen verkoop in de boeken komen")
    assert listings[0]["status"] == "sold_unconfirmed", (
        "de verkoper hoort de ja/nee-vraag te krijgen")
    assert listings[1]["status"] == "active", (
        "en Shopify — waar de koper vandaan kan komen — mag niet worden aangeraakt")


@pytest.mark.parametrize("bewijs", [cl.BEWIJS_BESTELLING, cl.BEWIJS_KANAAL_ZEGT_VERKOCHT,
                                    cl.BEWIJS_VERKOPER])
def test_met_bewijs_wordt_hij_gewoon_geboekt(monkeypatch, bewijs):
    db, listings = _situatie()
    _draai(monkeypatch, db, sold_price=14.99, bewijs=bewijs)
    verkocht = [l for l in listings if l["status"] == "sold"]
    assert len(verkocht) == 1 and verkocht[0]["id"] == "v1", (
        f"met bewijs '{bewijs}' hoort de verkoop gewoon geboekt te worden")
    assert verkocht[0]["sold_price"] == 14.99


def test_een_verzonnen_bewijs_telt_niet(monkeypatch):
    db, listings = _situatie()
    _draai(monkeypatch, db, bewijs="lijkt me wel")
    assert not [l for l in listings if l["status"] == "sold"]


# ── 2. De bestellingenpagina van Vinted ─────────────────────────────────────

def _orders(monkeypatch, orders, items, listings):
    """Draait de echte reconcile-vinted-orders; geeft de boekingen terug."""
    from backend.api import listings as api

    db = _DB(items, listings)
    geboekt = []

    async def _nep_sold(item_id, platform, prijs=None, **kw):
        geboekt.append((item_id, platform, prijs, kw.get("bewijs")))
        for l in listings:
            if l["item_id"] == item_id and l["platform"] == platform:
                l["status"] = "sold"

    async def _naast(fn, *_a, **_k):
        return fn()

    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "naast_de_lus", _naast)
    monkeypatch.setattr(api, "fetch_all", lambda bouw, *a, **k: bouw().execute().data)
    monkeypatch.setattr(api, "handle_item_sold", _nep_sold)
    asyncio.run(api.reconcile_vinted_orders({"orders": orders}, user_id="u1"))
    return geboekt


def test_regel_zonder_bedrag_is_geen_bestelling(monkeypatch):
    """Precies wat er met 1313 gebeurde: een rij van de bestellingenpagina zonder
    bedrag, die alleen maar 'niet geannuleerd' was."""
    items = [{"id": "i1", "user_id": "u1",
              "title": "(1313) Blue/White Zara Rugby Longsleeve Poloshirt - Men XL - Very Good",
              "sku": "IMP-ADDEA51B"}]
    listings = [{"id": "v1", "item_id": "i1", "platform": "vinted", "status": "active",
                 "platform_listing_id": "9256552127"}]
    geboekt = _orders(monkeypatch, [{
        "sku": None, "price": None, "sold": True,
        "text": "(1313) Blue/White Zara Rugby Longsleeve Poloshirt - Men XL - Very Good",
    }], items, listings)
    assert geboekt == [], (
        "een regel zonder bedrag is geen bestelling en mag geen Vinted-verkoop "
        f"worden. Kreeg: {geboekt}")
    assert listings[0]["status"] == "active"


def test_echte_bestelling_met_bedrag_wordt_gewoon_geboekt(monkeypatch):
    items = [{"id": "i1", "user_id": "u1",
              "title": "(1340) Navy Suitsupply Henley - Men S - New With Tags", "sku": None}]
    listings = [{"id": "v1", "item_id": "i1", "platform": "vinted", "status": "active",
                 "platform_listing_id": "9619021814"}]
    geboekt = _orders(monkeypatch, [{
        "sku": None, "price": "€ 32,31", "sold": True, "date": ["2026-08-26T09:31:00+00:00"],
        "text": "(1340) Navy Suitsupply Henley - Men S - New With Tags € 32,31",
    }], items, listings)
    assert len(geboekt) == 1 and geboekt[0][:3] == ("i1", "vinted", 32.31), (
        f"een echte bestelling met bedrag hoort gewoon geboekt te worden. Kreeg: {geboekt}")
    assert geboekt[0][3] == cl.BEWIJS_BESTELLING
