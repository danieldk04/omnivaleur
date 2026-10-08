"""Nieuwe Shopify-producten komen vanzelf binnen (services/shopify_auto_import.py).

AANLEIDING (08-10-2026, Janneke 31d28378): "En nieuwe producten worden vanzelf
gesynchroniseerd?" Dat werden ze niet. Dit bestand bewaakt wat de ronde wel en
vooral níet mag doen:
  * alleen bij wie Shopify als bron gebruikt, of het zelf aanzet;
  * alleen producten die nog nooit gezien zijn: wat de verkoper liet liggen of
    negeerde blijft van hem;
  * nooit een product dat we zelf net publiceerden, nooit een uitverkocht product;
  * de importbeslissing van de knop, beperkt tot precies die kandidaten;
  * de ronde stopt altijd, ook als alles twijfel is.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.api import imports as imp
from backend.services import instellingen
from backend.services import shopify_auto_import as auto

NU = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


class _Klok(datetime):
    @classmethod
    def now(cls, tz=None):
        return NU


# ── nagebootste database ──────────────────────────────────────────────────
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
    def upsert(self, rijen, **_k): self.op, self.r = "upsert", rijen; return self
    def eq(self, k, v): self.f.append((k, lambda x, v=v: x == v)); return self
    def in_(self, k, vs): self.f.append((k, lambda x, vs=vs: x in vs)); return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self.lim = n; return self
    def range(self, a, b): self.rng = (a, b); return self

    def execute(self):
        rijen = self.db.t.setdefault(self.tabel, [])
        if self.op == "insert":
            rij = dict(self.r)
            rij.setdefault("id", f"{self.tabel}-{len(rijen)}")
            rij.setdefault("created_at", "2026-10-08")
            rijen.append(rij)
            return _R([rij])
        if self.op == "upsert":
            for nieuw in self.r:
                oud = next((r for r in rijen if r["platform_listing_id"] == nieuw["platform_listing_id"]
                            and r["platform"] == nieuw["platform"]), None)
                if oud:
                    oud.update(nieuw)
                else:
                    rijen.append({"id": f"c-{nieuw['platform_listing_id']}", **nieuw})
            return _R(self.r)
        hit = [r for r in rijen if all(fn(r.get(k)) for k, fn in self.f)]
        if self.op == "update":
            for r in hit:
                r.update(self.v)
            return _R(hit)
        if hasattr(self, "rng"):
            hit = hit[self.rng[0]:self.rng[1] + 1]
        if hasattr(self, "lim"):
            hit = hit[:self.lim]
        return _R(hit, count=len(hit) if self.cnt else None)


class _DB:
    def __init__(self, **tabellen):
        self.t = {"items": [], "listings": [], "import_candidates": [], "jobs": [],
                  "platform_credentials": [], **tabellen}

    def table(self, naam):
        return _Q(self, naam)


def _product(pid, titel, *, uur_oud=5, voorraad=1, sku=None):
    return {"id": pid, "title": titel, "handle": f"p{pid}", "vendor": "Kidsshop",
            "body_html": "Mooi.", "images": [{"src": f"https://cdn.shopify.com/{pid}.jpg"}],
            "variants": [{"price": "12.50", "sku": sku or "", "inventory_management": "shopify",
                          "inventory_quantity": voorraad}],
            "options": [], "tags": "",
            "created_at": (NU - timedelta(hours=uur_oud)).isoformat()}


def _cand(pid, status, titel="Oud"):
    return {"id": f"c-{pid}", "user_id": "u", "platform": "shopify", "status": status,
            "platform_listing_id": str(pid), "platform_listing_url": f"https://x/{pid}",
            "title": titel, "price": 10, "photo_urls": [], "created_at": "2026-10-01"}


# ── 1. wat telt als nieuw ─────────────────────────────────────────────────
def test_alleen_wat_nog_nooit_gezien_is_en_te_koop_staat():
    producten = [
        _product(1, "Al kandidaat"),
        _product(2, "Eigen advertentie"),
        _product(3, "Nieuw rompertje"),
        _product(4, "Uitverkocht", voorraad=0),
        _product(5, "Net door ons gepubliceerd", uur_oud=0.1),
    ]
    nieuw = auto.nieuwe_producten(producten, {"1", "2"}, NU)
    assert [p["id"] for p in nieuw] == [3]


def test_bekende_productnummers_komen_uit_kandidaten_en_eigen_advertenties(monkeypatch):
    db = _DB(import_candidates=[_cand(1, "ignored"), {**_cand(9, "pending"), "user_id": "ander"}],
             items=[{"id": "i1", "user_id": "u"}],
             listings=[{"item_id": "i1", "platform": "shopify", "platform_listing_id": "2"},
                       {"item_id": "i1", "platform": "vinted", "platform_listing_id": "77"}])
    monkeypatch.setattr(auto, "fetch_all", lambda bouw: bouw().execute().data)
    monkeypatch.setattr(auto, "fetch_all_in",
                        lambda bouw, kolom, waarden: bouw().in_(kolom, list(waarden)).execute().data)
    assert auto._bekende_productnummers(db, "u") == {"1", "2"}


# ── 2. aan of uit ─────────────────────────────────────────────────────────
def test_zonder_eigen_keuze_alleen_aan_bij_wie_uit_shopify_importeerde():
    db = _DB(import_candidates=[_cand(1, "pending")])
    assert auto.staat_aan(db, "u", {"shopify_auto_import": None}) is False
    db.t["import_candidates"].append(_cand(2, "imported"))
    assert auto.staat_aan(db, "u", {"shopify_auto_import": None}) is True


def test_een_bewuste_keuze_wint_altijd():
    db = _DB(import_candidates=[_cand(2, "imported")])
    assert auto.staat_aan(db, "u", {"shopify_auto_import": False}) is False
    assert auto.staat_aan(_DB(), "u", {"shopify_auto_import": True}) is True


def test_instellingen_bewaren_keuze_en_stand():
    uit = instellingen._schoon({"shopify_auto_import": True,
                                "shopify_auto_import_stand": {"gecontroleerd": "x", "rommel": 1}})
    assert uit["shopify_auto_import"] is True
    assert uit["shopify_auto_import_stand"] == {"gecontroleerd": "x"}
    assert instellingen._schoon({})["shopify_auto_import"] is None
    assert instellingen._schoon({"shopify_auto_import": None})["shopify_auto_import"] is None


# ── 3. de importknop, beperkt tot deze kandidaten ─────────────────────────
@pytest.fixture
def bulk_op_nepdb(monkeypatch):
    def zet(db):
        monkeypatch.setattr(imp, "get_db", lambda: db)
        monkeypatch.setattr(imp, "fetch_all", lambda bouw: bouw().execute().data)
        monkeypatch.setattr(imp, "fetch_all_in",
                            lambda bouw, kolom, waarden: bouw().in_(kolom, list(waarden)).execute().data)

        async def geen(*_a, **_k): return {}
        monkeypatch.setattr(imp, "_find_twins", geen)
        monkeypatch.setattr(imp, "_infer_attributes_smart", geen)
        monkeypatch.setattr(imp, "ruimte_over", lambda *_a: None)
        import backend.services.photo_mirror as pm

        async def spiegel(lijsten, _uid): return [None for _ in lijsten]
        monkeypatch.setattr(pm, "mirror_photos_bulk", spiegel)
        imp._BULK_IMPORT_CACHE.clear()
    return zet


def test_bulk_met_candidate_ids_laat_de_rest_liggen(bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "pending", "Laat liggen"), _cand(2, "pending", "Nieuw")])
    bulk_op_nepdb(db)
    uit = asyncio.run(imp.bulk_import_candidates(
        {"platform": "shopify", "candidate_ids": ["c-2"], "limit": 25}, user_id="u"))
    assert uit["created"] == 1 and uit["remaining"] == 0
    status = {c["id"]: c["status"] for c in db.t["import_candidates"]}
    assert status == {"c-1": "pending", "c-2": "imported"}
    assert [i["title"] for i in db.t["items"]] == ["Nieuw"]


# ── 4. de hele ronde ──────────────────────────────────────────────────────
def _ronde(monkeypatch, bulk_op_nepdb, db, producten, keuze=None, toegang=True):
    bulk_op_nepdb(db)
    stand = {}
    monkeypatch.setattr(auto, "get_db", lambda: db)
    monkeypatch.setattr(auto, "fetch_all", lambda bouw: bouw().execute().data)
    monkeypatch.setattr(auto, "fetch_all_in",
                        lambda bouw, kolom, waarden: bouw().in_(kolom, list(waarden)).execute().data)
    monkeypatch.setattr(instellingen, "lees",
                        lambda _u: {**instellingen.STANDAARD, "shopify_auto_import": keuze})
    monkeypatch.setattr(instellingen, "schrijf",
                        lambda _u, w: stand.update(w.get("shopify_auto_import_stand", {})))

    async def mag(_u): return toegang
    monkeypatch.setattr(auto, "_mag_importeren", mag)
    monkeypatch.setattr(auto, "datetime", _Klok)
    import backend.platforms.shopify as sp
    import backend.services.shopify_scan as scan
    import backend.services.shopify_voorraad as vr

    async def creds(_c): return "kids.myshopify.com", "tok"
    async def lees(_s, _t): return producten
    async def vlag(*_a): return None
    monkeypatch.setattr(sp, "_shop_creds", creds)
    monkeypatch.setattr(scan, "lees_producten", lees)
    monkeypatch.setattr(vr, "markeer_als_voorraadwinkel", vlag)

    # De echte opslag leest jobs, items en listings met kolommen die deze
    # nabootsing niet kent; hier telt alleen dat er een kandidaat 'pending' komt.
    import backend.api.jobs as jobs
    gezien = []

    def opslaan(db_, job, regels):
        gezien.extend(r["platform_listing_id"] for r in regels)
        db_.table("import_candidates").upsert(
            [{"user_id": job["user_id"], "platform": "shopify", "status": "pending",
              "suggested_item_id": None, "photo_urls": [], **r} for r in regels]).execute()
    monkeypatch.setattr(jobs, "_store_scan_results", opslaan)
    db.t["platform_credentials"].append({"user_id": "u", "platform": "shopify",
                                         "access_token": "x", "extra_data": {}})
    uit = asyncio.run(auto.importeer_nieuwe_producten("u"))
    return uit, stand, gezien


def test_een_nieuw_product_wordt_een_artikel_en_de_rest_blijft_van_de_verkoper(monkeypatch, bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "imported"), _cand(2, "pending", "Liet ze liggen"),
                                _cand(3, "ignored")])
    producten = [_product(1, "Oud"), _product(2, "Liet ze liggen"), _product(3, "Genegeerd"),
                 _product(4, "Nieuw rompertje maat 74")]
    uit, stand, gezien = _ronde(monkeypatch, bulk_op_nepdb, db, producten)
    assert gezien == ["4"]
    assert uit["toegevoegd"] == 1
    assert [i["title"] for i in db.t["items"]] == ["Nieuw rompertje maat 74"]
    status = {c["platform_listing_id"]: c["status"] for c in db.t["import_candidates"]}
    assert status == {"1": "imported", "2": "pending", "3": "ignored", "4": "imported"}
    assert db.t["listings"][0]["platform_listing_id"] == "4"
    assert stand["laatst_toegevoegd_om"] == NU.isoformat() and stand["fout"] is None
    # En de volgende ronde doet niets meer.
    uit2, _, gezien2 = _ronde(monkeypatch, bulk_op_nepdb, db, producten)
    assert uit2 == {"nieuw": 0} and gezien2 == [] and len(db.t["items"]) == 1


def test_wie_shopify_nooit_als_bron_gebruikte_krijgt_niets(monkeypatch, bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "pending")])
    uit, _, gezien = _ronde(monkeypatch, bulk_op_nepdb, db, [_product(4, "Nieuw")])
    assert uit == {"overgeslagen": "uit"} and gezien == [] and db.t["items"] == []


def test_zelf_aangezet_werkt_ook_zonder_eerdere_import(monkeypatch, bulk_op_nepdb):
    db = _DB()
    uit, _, _ = _ronde(monkeypatch, bulk_op_nepdb, db, [_product(4, "Nieuw")], keuze=True)
    assert uit["toegevoegd"] == 1


def test_uitgezet_doet_niets_ook_niet_bij_een_bron(monkeypatch, bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "imported")])
    uit, _, _ = _ronde(monkeypatch, bulk_op_nepdb, db, [_product(4, "Nieuw")], keuze=False)
    assert uit == {"overgeslagen": "uit"} and db.t["items"] == []


def test_proef_verlopen_maakt_niets_aan(monkeypatch, bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "imported")])
    uit, _, _ = _ronde(monkeypatch, bulk_op_nepdb, db, [_product(4, "Nieuw")], toegang=False)
    assert uit == {"overgeslagen": "geen toegang"} and db.t["items"] == []


def test_niet_tegelijk_met_een_scan_met_de_knop(monkeypatch, bulk_op_nepdb):
    db = _DB(import_candidates=[_cand(1, "imported")],
             jobs=[{"id": "j", "user_id": "u", "platform": "shopify", "action": "scan",
                    "status": "claimed"}])
    uit, _, _ = _ronde(monkeypatch, bulk_op_nepdb, db, [_product(4, "Nieuw")])
    assert uit == {"overgeslagen": "scan of import loopt"} and db.t["items"] == []


def test_twijfel_blijft_staan_en_de_ronde_stopt(monkeypatch, bulk_op_nepdb):
    """Alles twijfel: niets aanmaken, netjes melden, en nooit blijven draaien."""
    db = _DB(import_candidates=[_cand(1, "imported")])
    rondes = []
    echt = imp.bulk_import_candidates

    async def tel(body, user_id):
        rondes.append(body["offset"])
        return await echt(body, user_id=user_id)

    async def alles_tweeling(cands, *_a):
        return {c["id"]: "x" for c in cands}
    monkeypatch.setattr(imp, "bulk_import_candidates", tel)

    def zet_met_twijfel(d):
        bulk_op_nepdb(d)
        monkeypatch.setattr(imp, "_find_twins", alles_tweeling)
    uit, stand, _ = _ronde(monkeypatch, zet_met_twijfel, db,
                           [_product(p, f"Nieuw {p}") for p in range(10, 40)])
    assert uit["toegevoegd"] == 0 and uit["te_controleren"] == 30
    assert stand["te_controleren"] == 30
    assert len(rondes) <= 3
    assert all(c["status"] == "pending" for c in db.t["import_candidates"]
               if c["platform_listing_id"] != "1")


def test_de_ronde_draait_elk_uur():
    from pathlib import Path
    bron = (Path(__file__).resolve().parents[1] / "backend/scheduler.py").read_text()
    assert 'id="shopify_auto_import"' in bron
    blok = bron[bron.index("importeer_alle_winkels),"):bron.index('id="shopify_auto_import"')]
    assert '"interval"' in blok and "hours=1" in blok
