"""Weg van Vinted terwijl het elders nog te koop staat: een vraag, geen archief.

WAAROM DIT ER IS (12-09-2026, De Juiste Toon)
Hij verkocht 23 artikelen op Vinted en haalde die advertenties daar zelf weg,
zoals vrijwel iedereen doet. Op Marktplaats bleven ze gewoon staan. Dat was geen
storing: een uit de garderobe verdwenen advertentie ging stil naar 'delisted',
er werd niets afgemeld en niets gevraagd. Het antwoord op "wanneer gaan ze
automatisch van Marktplaats af" was dus: nooit.

Van absentie een verkoop maken blijft verboden (dat haalde ooit levende
advertenties overal weg). Maar op Vinted verloopt niets vanzelf, dus weg is met
de hand weggehaald: een zacht signaal, en dat hoort een ja/nee-vraag te worden.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402
from backend.api.listings import VERDENKING_REDENEN  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.op, self.velden = {}, {}, None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def neq(self, k, v): self.filters[f"neq:{k}"] = v; return self
    def in_(self, k, v): self.in_filters[k] = list(v); return self
    def order(self, *_a, **_k): return self
    def limit(self, _n): return self
    def range(self, *_a, **_k): return self

    def _match(self, r):
        for k, v in self.filters.items():
            if k.startswith("neq:"):
                if r.get(k[4:]) == v:
                    return False
            elif r.get(k) != v:
                return False
        return all(r.get(k) in vals for k, vals in self.in_filters.items())

    def execute(self):
        bron = self.db.items if self.tabel == "items" else self.db.listings
        rijen = [r for r in bron if self._match(r)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, items, listings):
        self.items, self.listings = items, listings

    def table(self, naam):
        return _Q(self, naam)


def _draai(db, scraped):
    """Roept de echte reconciliatie aan; geeft terug welke items zijn afgemeld."""
    afgemeld = []

    async def _nep_sold(item_id, platform, prijs=None):
        afgemeld.append((item_id, platform))

    origineel = (J.fetch_all, J.fetch_all_in, J.naast_de_lus, J.handle_item_sold)
    J.fetch_all = lambda bouw, *a, **k: bouw().execute().data
    J.fetch_all_in = lambda bouw, kolom, waarden, *a, **k: bouw().in_(kolom, list(waarden)).execute().data

    async def _naast(fn):
        return fn()

    J.naast_de_lus = _naast
    J.handle_item_sold = _nep_sold
    try:
        asyncio.run(J._reconcile_vinted_sales(
            db,
            {"user_id": "u1"},
            scraped,
            {"complete": True, "fetched": len(scraped), "total_entries": len(scraped)},
        ))
    finally:
        J.fetch_all, J.fetch_all_in, J.naast_de_lus, J.handle_item_sold = origineel
    return afgemeld


def test_weg_van_vinted_maar_nog_op_marktplaats_wordt_een_vraag():
    items = [
        {"id": "i1", "user_id": "u1", "sku": None, "title": "Kelim loper 74/42 cm"},
        {"id": "i2", "user_id": "u1", "sku": None, "title": "Smyrna kleedje 93/38 cm"},
    ]
    listings = [
        # i1: van Vinted verdwenen, staat nog op Marktplaats.
        {"id": "l1", "item_id": "i1", "platform": "vinted", "status": "active",
         "platform_listing_id": "111"},
        {"id": "l2", "item_id": "i1", "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m1"},
        # i2: van Vinted verdwenen, staat nergens anders meer.
        {"id": "l3", "item_id": "i2", "platform": "vinted", "status": "active",
         "platform_listing_id": "222"},
    ]
    db = _DB(items, listings)
    # De garderobe bevat alleen nog een derde advertentie: 111 en 222 zijn weg.
    afgemeld = _draai(db, [{"platform_listing_id": "999", "title": "Iets anders",
                            "is_closed": False}])

    vinted1 = next(l for l in listings if l["id"] == "l1")
    assert vinted1["status"] == "sold_unconfirmed", (
        "Een advertentie die van Vinted af is terwijl hij op Marktplaats nog te koop "
        f"staat moet een ja/nee-vraag worden, niet stil het archief in (was: {vinted1['status']})")
    assert vinted1.get("error_message") == VERDENKING_REDENEN["vinted_weg"]

    # Niets automatisch afgemeld: absentie is en blijft een zacht signaal.
    assert afgemeld == [], f"er mag niets automatisch zijn afgemeld, maar: {afgemeld}"

    # Staat het nergens anders meer, dan valt er niets te vragen.
    vinted2 = next(l for l in listings if l["id"] == "l3")
    assert vinted2["status"] == "delisted"

    # De Marktplaats-advertentie zelf blijft onaangeroerd tot de verkoper ja zegt.
    assert next(l for l in listings if l["id"] == "l2")["status"] == "active"


def test_gesloten_op_vinted_blijft_gewoon_een_verkoop():
    items = [{"id": "i1", "user_id": "u1", "sku": None, "title": "Lederhosen maat 54"}]
    listings = [
        {"id": "l1", "item_id": "i1", "platform": "vinted", "status": "active",
         "platform_listing_id": "111"},
        {"id": "l2", "item_id": "i1", "platform": "marktplaats", "status": "active",
         "platform_listing_id": "m1"},
    ]
    afgemeld = _draai(_DB(items, listings),
                      [{"platform_listing_id": "111", "title": "Lederhosen maat 54",
                        "is_closed": True}])
    assert afgemeld == [("i1", "vinted")], (
        "Vinted's eigen 'gesloten'-vlag is het harde signaal en moet gewoon "
        f"blijven afmelden, maar kreeg: {afgemeld}")
