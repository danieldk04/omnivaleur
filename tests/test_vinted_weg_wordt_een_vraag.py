"""Weg uit de Vinted-kast is een VRAAG, geen verkoop op Vinted.

WAAROM DIT ER IS (17-09-2026, Daniel — artikel 1313)
Artikel 1313 was op Shopify verkocht (bestelling #1079 van 06-09, EUR 14,99).
Zijn Vinted-advertentie was weggehaald, en daardoor stond de verkoop in
Analytics als een VINTED-verkoop van 12-09, zonder bedrag. Drie dingen fout in
één regel: het kanaal, de datum en het bedrag. En Shopify, waar de koper vandaan
kwam, kreeg een verwijderopdracht.

De aanname erachter (12-09-2026, De Juiste Toon) was: op Vinted verloopt niets
vanzelf, dus weg uit de kast betekent dat de verkoper hem zelf weghaalde, en dat
doet vrijwel iedereen na een verkoop. Dat klopt — alleen zegt het niets over
WAAR het verkocht is, en juist een verkoop elders is de reden dat de advertentie
weg is.

Dus: afwezigheid is weer een aanwijzing. Staat het artikel nog ergens anders te
koop, dan krijgt de verkoper de ja/nee-vraag (en bij "ja" wijst hij het kanaal
aan). Staat het nergens meer, dan gaat de rij het archief in. Vinteds eigen
"gesloten"-vlag blijft wél gewoon een verkoop: dat zegt Vinted zelf.

De rem op een kapotte scan blijft: verdwijnt er in één ronde een te groot deel
van de kast, dan gelooft de code zichzelf niet.
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

    async def _nep_sold(item_id, platform, prijs=None, bewijs=None, **_k):
        assert bewijs, ("elke boeking moet zeggen waarom we weten dat het op DIT "
                        "kanaal verkocht is")
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


def test_weg_van_vinted_wordt_een_vraag_en_nooit_een_vinted_verkoop():
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
    # De kast bevat alleen nog een derde advertentie: 111 en 222 zijn weggehaald.
    afgemeld = _draai(db, [{"platform_listing_id": "999", "title": "Iets anders",
                            "is_closed": False}])

    assert afgemeld == [], (
        "Een verdwenen advertentie is geen bewijs van een verkoop OP VINTED; er "
        f"mag niets geboekt worden. Kreeg: {afgemeld}")
    v1 = next(l for l in listings if l["id"] == "l1")
    assert v1["status"] == "sold_unconfirmed", (
        "Staat het artikel nog op Marktplaats, dan hoort de verkoper de vraag te "
        f"krijgen. Kreeg: {v1['status']}")
    assert v1["error_message"] == VERDENKING_REDENEN["vinted_weg"]
    assert next(l for l in listings if l["id"] == "l2")["status"] == "active", (
        "de Marktplaats-advertentie mag niet zijn aangeraakt")
    assert next(l for l in listings if l["id"] == "l3")["status"] == "delisted", (
        "staat het nergens anders meer te koop, dan valt er niets te vragen en "
        "gaat de rij naar het archief")


def test_een_halve_kast_ineens_weg_is_geen_dag_verkopen():
    """De rem: dit is precies het beeld van een kapotte scan, niet van verkopen."""
    items = [{"id": f"i{n}", "user_id": "u1", "sku": None, "title": f"Artikel {n}"}
             for n in range(30)]
    listings = []
    for n in range(30):
        listings.append({"id": f"v{n}", "item_id": f"i{n}", "platform": "vinted",
                         "status": "active", "platform_listing_id": str(1000 + n)})
        listings.append({"id": f"m{n}", "item_id": f"i{n}", "platform": "marktplaats",
                         "status": "active", "platform_listing_id": f"m{n}"})
    # De momentopname meldt zichzelf als volledig, maar bevat er nog maar vijf.
    kast = [{"platform_listing_id": str(1000 + n), "title": f"Artikel {n}",
             "is_closed": False} for n in range(5)]
    afgemeld = _draai(_DB(items, listings), kast)

    assert afgemeld == [], (
        "25 van de 30 advertenties ineens weg is een kapotte scan; er mag dan niets "
        f"automatisch worden afgemeld. Kreeg: {len(afgemeld)} afmeldingen")
    vinted = [l for l in listings if l["platform"] == "vinted" and l["id"] != "v0"]
    assert all(l["status"] in ("sold_unconfirmed", "active") for l in vinted)
    gevraagd = [l for l in vinted if l["status"] == "sold_unconfirmed"]
    assert gevraagd, "de verkoper hoort de ja/nee-vraag te krijgen in plaats van niets"
    assert gevraagd[0]["error_message"] == VERDENKING_REDENEN["vinted_weg"]
    assert all(l["status"] == "active" for l in listings if l["platform"] == "marktplaats"), (
        "er mag geen enkele Marktplaats-advertentie zijn aangeraakt")


def test_weg_van_vinted_en_nergens_anders_te_koop():
    items = [{"id": "i1", "user_id": "u1", "sku": None, "title": "Alleen op Vinted"}]
    listings = [{"id": "l1", "item_id": "i1", "platform": "vinted", "status": "active",
                 "platform_listing_id": "111"}]
    afgemeld = _draai(_DB(items, listings), [{"platform_listing_id": "999",
                                              "title": "Iets anders", "is_closed": False}])
    assert afgemeld == []
    assert listings[0]["status"] == "delisted", (
        "nergens anders te koop: geen vraag, gewoon het archief in")


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
