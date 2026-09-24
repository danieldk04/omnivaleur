"""Import all koppelt alleen wat zeker is; de rest blijft staan als vraag.

WAAROM DIT ER IS (24-09-2026, Daniel)
Daniel importeert van Vinted, Marktplaats, 2dehands en Shopify, meerdere keren
achter elkaar, en wil daarna zonder na te lopen weten dat er niets dubbel in zijn
voorraad staat: "het systeem mag zelf koppelen, dingen die het 100% zeker weet;
de rest is twijfel." Tot nu toe hield "Import all" alleen een vertaalde tweeling
tegen. Deze gevallen gingen stil hun gang:

  * een tweede Shopify-product op een item dat al aan een ander product hangt
    (Revaleur 1071: twee verschillende truien met hetzelfde nummer)
  * een levende advertentie met het nummer van een VERKOCHT item, terwijl er
    ook een onverkochte rij met dat nummer bestaat (opnieuw ingekocht): de
    oudste, verkochte rij won
  * een levende advertentie met alleen het nummer van een verkocht item
  * alleen de titel gelijk, en dat item staat op dat kanaal al met een andere
    advertentie: werd stil een nieuw item, ook als het een dubbel geplaatste
    advertentie van hetzelfde stuk was

Draait bulk_import_candidates zelf, met een nagebootste database. Met
IMPORTS_BRON=<pad> draait dezelfde proef tegen een ander bestand (de oude versie).
"""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _laad():
    bron = os.environ.get("IMPORTS_BRON") or str(ROOT / "backend/api/imports.py")
    spec = importlib.util.spec_from_file_location("imports_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _R:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.op, self.cnt = db, tabel, [], "select", False

    def select(self, *_a, count=None, **_k):
        self.cnt = bool(count)
        return self
    def update(self, v): self.op, self.v = "update", v; return self
    def insert(self, r): self.op, self.r = "insert", r; return self
    def eq(self, k, v): self.f.append((k, lambda x, v=v: x == v)); return self
    def in_(self, k, vs): self.f.append((k, lambda x, vs=vs: x in vs)); return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a): return self
    def range(self, a, b): self.rng = (a, b); return self

    def execute(self):
        rijen = self.db.t[self.tabel]
        if self.op == "insert":
            rij = dict(self.r)
            rij.setdefault("id", f"{self.tabel}-{len(rijen)}")
            rij.setdefault("created_at", "2026-09-24")
            rijen.append(rij)
            return _R([rij])
        hit = [r for r in rijen if all(fn(r.get(k)) for k, fn in self.f)]
        if self.op == "update":
            for r in hit:
                r.update(self.v)
            return _R(hit)
        if hasattr(self, "rng"):
            hit = hit[self.rng[0]:self.rng[1] + 1]
        return _R(hit, count=len(hit) if self.cnt else None)


class _DB:
    def __init__(self, items, listings, cands):
        self.t = {"items": items, "listings": listings, "import_candidates": cands}

    def table(self, naam):
        return _Q(self, naam)


def _draai(items, listings, cands):
    imp = _laad()
    db = _DB(items, listings, cands)
    imp.get_db = lambda: db
    imp.fetch_all = lambda bouw: bouw().execute().data
    imp.fetch_all_in = lambda bouw, kolom, waarden: bouw().in_(kolom, list(waarden)).execute().data

    async def geen_tweelingen(*_a, **_k): return {}
    async def niets(*_a, **_k): return {}
    imp._find_twins = geen_tweelingen
    imp._infer_attributes_smart = niets
    import backend.services.photo_mirror as pm

    async def spiegel(lijsten, _uid): return [None for _ in lijsten]
    pm.mirror_photos_bulk = spiegel
    imp._BULK_IMPORT_CACHE.clear()
    uit = asyncio.run(imp.bulk_import_candidates({"limit": 50}, user_id="u"))
    return db, uit


def _cand(cid, platform, pid, titel, **extra):
    return {"id": cid, "user_id": "u", "status": "pending", "platform": platform,
            "platform_listing_id": pid, "platform_listing_url": f"https://x/{pid}",
            "title": titel, "price": 25, "photo_urls": [], "created_at": "2026-09-24",
            **extra}


def _item(iid, titel, created="2026-07-01"):
    return {"id": iid, "user_id": "u", "title": titel, "price": 25, "brand": None,
            "sku": f"IMP-{iid}", "created_at": created}


def _lst(iid, platform, pid, status="active"):
    return {"id": f"l-{iid}-{pid}", "item_id": iid, "platform": platform,
            "platform_listing_id": pid, "status": status}


def _scenario():
    items = [
        _item("A", "(1071) Trui col"),
        _item("S", "(500) Grijze trui", "2026-06-01"),   # verkocht, oudst
        _item("U", "(500) Grijze trui", "2026-09-18"),   # zelfde nummer, opnieuw ingekocht
        _item("V", "(600) Zwarte jas"),                  # alleen verkocht
        _item("T", "Blauwe jas Heren M"),                # al op Marktplaats (m1)
        _item("W", "(800) Sjaal"),                       # advertentie m9 is al bekend
    ]
    listings = [
        _lst("A", "shopify", "111"),
        _lst("S", "vinted", "v5", "sold"),
        _lst("U", "marktplaats", "m5"),
        _lst("V", "vinted", "v6", "sold"),
        _lst("T", "marktplaats", "m1"),
        _lst("W", "marktplaats", "m9"),
    ]
    cands = [
        _cand("c-shop", "shopify", "222", "Trui ronde hals", suggested_item_id="A"),
        _cand("c-500", "2dehands", "d5", "(500) Grijze trui"),
        _cand("c-600", "2dehands", "d6", "(600) Zwarte jas"),
        _cand("c-titel", "marktplaats", "m2", "Blauwe jas Heren M"),
        _cand("c-nieuw", "marktplaats", "m7", "(700) Nieuwe muts"),
        _cand("c-bekend", "marktplaats", "m9", "(800) Sjaal"),
    ]
    return items, listings, cands


def _status(db, cid):
    return next(c["status"] for c in db.t["import_candidates"] if c["id"] == cid)


def _item_van(db, platform, pid):
    return [l["item_id"] for l in db.t["listings"]
            if l["platform"] == platform and l["platform_listing_id"] == pid]


FOUT = []


def check(naam, ok, uitleg=""):
    print(("  ok   " if ok else "  FOUT ") + naam + ("" if ok else f"  ({uitleg})"))
    if not ok:
        FOUT.append(naam)


def test_zeker_koppelen_twijfel_laten_staan():
    db, uit = _draai(*_scenario())
    n_items_voor = 6

    check("tweede Shopify-product blijft een vraag", _status(db, "c-shop") == "pending",
          f"status {_status(db, 'c-shop')}, gekoppeld aan {_item_van(db, 'shopify', '222')}")
    check("zelfde nummer: advertentie gaat naar de onverkochte rij",
          _item_van(db, "2dehands", "d5") == ["U"], f"hangt aan {_item_van(db, '2dehands', 'd5')}")
    check("alleen een verkocht item met dat nummer: vraag", _status(db, "c-600") == "pending",
          f"status {_status(db, 'c-600')}, hangt aan {_item_van(db, '2dehands', 'd6')}")
    check("alleen de titel gelijk en al een andere advertentie: vraag",
          _status(db, "c-titel") == "pending", f"status {_status(db, 'c-titel')}")
    check("nergens een overeenkomst: nieuw item", _status(db, "c-nieuw") == "imported")
    check("bekende advertentie: gekoppeld, geen nieuw item",
          _status(db, "c-bekend") == "linked" and _item_van(db, "marktplaats", "m9") == ["W"])
    check("precies één nieuw item erbij", len(db.t["items"]) == n_items_voor + 1,
          f"{len(db.t['items']) - n_items_voor} nieuw")
    check("de vragen worden gemeld", uit["parked"] == 3, f"parked {uit['parked']}")

    # Nog een keer draaien op dezelfde stand mag niets toevoegen.
    imp_items = len(db.t["items"])
    imp = _laad()
    check("tweede ronde voegt niets toe", True)  # zie hieronder
    assert not FOUT, FOUT
    assert imp_items == n_items_voor + 1


def test_tweede_ronde_voegt_niets_toe():
    items, listings, cands = _scenario()
    db, _ = _draai(items, listings, cands)
    voor = len(db.t["items"])
    # Zelfde scan opnieuw: de al verwerkte advertenties komen terug als nieuwe
    # kandidaten, zoals een herhaalde scan ze aanlevert.
    for c in list(db.t["import_candidates"]):
        if c["status"] in ("linked", "imported"):
            db.t["import_candidates"].append({**c, "id": c["id"] + "-2", "status": "pending"})
    imp = _laad()
    imp.get_db = lambda: db
    imp.fetch_all = lambda bouw: bouw().execute().data
    imp.fetch_all_in = lambda bouw, kolom, waarden: bouw().in_(kolom, list(waarden)).execute().data

    async def geen(*_a, **_k): return {}
    imp._find_twins = geen
    imp._infer_attributes_smart = geen
    imp._BULK_IMPORT_CACHE.clear()
    asyncio.run(imp.bulk_import_candidates({"limit": 50}, user_id="u"))
    check("tweede ronde: geen enkel nieuw item", len(db.t["items"]) == voor,
          f"{len(db.t['items']) - voor} erbij")
    assert len(db.t["items"]) == voor


if __name__ == "__main__":
    for t in (test_zeker_koppelen_twijfel_laten_staan, test_tweede_ronde_voegt_niets_toe):
        try:
            t()
        except AssertionError:
            pass
    print("\n" + (f"{len(FOUT)} fout(en)" if FOUT else "alles ok"))
    sys.exit(1 if FOUT else 0)
