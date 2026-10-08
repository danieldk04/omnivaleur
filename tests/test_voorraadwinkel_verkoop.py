"""Een verkoop bij een winkel met voorraad haalt niets weg en wist nooit het Shopify-product.

WAAROM DIT ER IS (08-10-2026, Goudlief 5aae4954). Gemeten: 4.919 producten,
3.907 met meer dan 5 stuks. De oude verkoopafhandeling behandelde elk artikel als
uniek: een Shopify-verkoop haalde Marktplaats en 2dehands offline, en een
verkoop op Marktplaats wiste het hele product uit de Shopify-winkel.

Draait de ECHTE handle_item_sold, nu en van vóór de reparatie (9f69689b).
"""
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl  # noqa: E402
from backend.services import shopify_voorraad as sv  # noqa: E402
from backend.services import tweelingen  # noqa: E402
import backend.platforms.shopify as shp  # noqa: E402

VOOR = "9f69689b"


class _Q:
    def __init__(self, db, naam):
        self.db, self.naam, self.f, self.upd, self.ins = db, naam, [], None, None

    def select(self, *_a, **_k): return self
    def limit(self, *_a): return self
    def order(self, *_a, **_k): return self
    def eq(self, k, v): self.f.append(lambda r: r.get(k) == v); return self
    def in_(self, k, vs): self.f.append(lambda r: r.get(k) in vs); return self
    def update(self, d): self.upd = d; return self
    def insert(self, d): self.ins = d; return self

    def execute(self):
        rijen = self.db.t.setdefault(self.naam, [])
        if self.ins is not None:
            rijen.append(dict(self.ins))
            return type("R", (), {"data": [self.ins]})
        hit = [r for r in rijen if all(f(r) for f in self.f)]
        if self.upd is not None:
            for r in hit:
                r.update(self.upd)
        return type("R", (), {"data": hit})


class _DB:
    def __init__(self, **t): self.t = t
    def table(self, naam): return _Q(self, naam)


def _situatie(stuks, vlag=True, varianten=None):
    db = _DB(
        items=[{"id": "i1", "user_id": "u1", "title": "Gouden ketting"}],
        listings=[
            {"id": "s1", "item_id": "i1", "platform": "shopify", "status": "active",
             "platform_listing_id": "10748006302023"},
            {"id": "m1", "item_id": "i1", "platform": "marktplaats", "status": "active",
             "platform_listing_id": "m2400000001"},
            {"id": "t1", "item_id": "i1", "platform": "2dehands", "status": "active",
             "platform_listing_id": "m2400000002"},
        ],
        platform_credentials=[{"user_id": "u1", "platform": "shopify",
                               "extra_data": {"shop_domain": "goudlief.myshopify.com",
                                              **({sv.VLAG: True} if vlag else {})}}],
        jobs=[], sync_events=[],
    )
    winkel = {"varianten": varianten or [{"id": 1, "inventory_item_id": 11,
                                          "inventory_management": "shopify",
                                          "inventory_quantity": stuks}]}
    return db, winkel


def _verkoop(module, monkeypatch, db, winkel, kanaal):
    gebeurd = {"shopify_gewist": False, "extensie_weg": [], "stuk_eraf": 0}

    async def _naast(fn, *_a, **_k): return fn()

    async def _creds(_c): return "goudlief.myshopify.com", "tok"

    async def _lees(_s, _t, _pid): return winkel["varianten"]

    async def _eraf(_s, _t, v):
        v["inventory_quantity"] -= 1
        gebeurd["stuk_eraf"] += 1
        return True

    async def _delist(l):
        if l["platform"] == "shopify":
            gebeurd["shopify_gewist"] = True

    for m in (module, sv):
        monkeypatch.setattr(m, "naast_de_lus", _naast)
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_delist_one", _delist)
    monkeypatch.setattr(module, "_nooit_online", lambda *_a: False)
    monkeypatch.setattr(module, "_last_listed_title", lambda *_a: "Gouden ketting")
    monkeypatch.setattr(module, "_enqueue_extension_delete",
                        lambda _db, _u, _i, l, _r: gebeurd["extensie_weg"].append(l["platform"]))
    monkeypatch.setattr(tweelingen, "familie_ids", lambda _db, _it: ["i1"])
    monkeypatch.setattr(shp, "_shop_creds", _creds)
    monkeypatch.setattr(sv, "lees_varianten", _lees)
    monkeypatch.setattr(sv, "een_stuk_eraf", _eraf)
    asyncio.run(module.handle_item_sold("i1", kanaal, sold_price=24.95,
                                        bewijs=module.BEWIJS_BESTELLING))
    return gebeurd


def _oud():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/services/crosslist.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "shopify_voorraad" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_crosslist_voorraad.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("backend.services.oude_crosslist_voorraad", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _status(db, pid):
    return next(l["status"] for l in db.t["listings"] if l["id"] == pid)


# ── Voor de reparatie: de schade aantonen ───────────────────────────────────

def test_oud_marktplaats_verkoop_wist_shopify_product(monkeypatch):
    db, winkel = _situatie(stuks=123)
    g = _verkoop(_oud(), monkeypatch, db, winkel, "marktplaats")
    assert g["shopify_gewist"], "de oude code wiste het product met 123 stuks voorraad"


def test_oud_shopify_verkoop_haalt_marktplaats_weg(monkeypatch):
    db, winkel = _situatie(stuks=122)
    g = _verkoop(_oud(), monkeypatch, db, winkel, "shopify")
    assert sorted(g["extensie_weg"]) == ["2dehands", "marktplaats"]
    assert _status(db, "s1") == "sold"


# ── Na de reparatie ─────────────────────────────────────────────────────────

def test_marktplaats_verkoop_haalt_een_stuk_af(monkeypatch):
    db, winkel = _situatie(stuks=123)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert not g["shopify_gewist"] and g["extensie_weg"] == []
    assert g["stuk_eraf"] == 1 and winkel["varianten"][0]["inventory_quantity"] == 122
    assert _status(db, "s1") == "active" and _status(db, "t1") == "active"
    assert _status(db, "m1") == "delisted", "die advertentie had zijn koper"


def test_herhaalde_melding_haalt_geen_tweede_stuk_af(monkeypatch):
    db, winkel = _situatie(stuks=123)
    _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["stuk_eraf"] == 0 and winkel["varianten"][0]["inventory_quantity"] == 122


def test_shopify_verkoop_met_voorraad_laat_alles_staan(monkeypatch):
    db, winkel = _situatie(stuks=122)
    g = _verkoop(cl, monkeypatch, db, winkel, "shopify")
    assert g["extensie_weg"] == [] and g["stuk_eraf"] == 0
    assert all(l["status"] == "active" for l in db.t["listings"])


def test_laatste_stuk_elders_verkocht_product_blijft_uitverkocht_staan(monkeypatch):
    db, winkel = _situatie(stuks=1)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["stuk_eraf"] == 1 and winkel["varianten"][0]["inventory_quantity"] == 0
    assert not g["shopify_gewist"], "het product moet aangevuld kunnen worden"
    assert g["extensie_weg"] == ["2dehands"], "op is op: 2dehands gaat offline"
    assert _status(db, "m1") == "sold"


def test_laatste_stuk_in_shopify_verkocht_haalt_de_rest_weg(monkeypatch):
    db, winkel = _situatie(stuks=0)
    g = _verkoop(cl, monkeypatch, db, winkel, "shopify")
    assert sorted(g["extensie_weg"]) == ["2dehands", "marktplaats"]


def test_shopify_teller_op_1_kiest_de_voorzichtige_kant(monkeypatch):
    # De teller kan nog de stand van vóór de bestelling tonen: 1 kan 0 zijn.
    db, winkel = _situatie(stuks=1)
    g = _verkoop(cl, monkeypatch, db, winkel, "shopify")
    assert sorted(g["extensie_weg"]) == ["2dehands", "marktplaats"] and not g["shopify_gewist"]


def test_meerdere_varianten_niet_raden(monkeypatch):
    varianten = [{"id": 1, "inventory_item_id": 11, "inventory_management": "shopify", "inventory_quantity": 41},
                 {"id": 2, "inventory_item_id": 12, "inventory_management": "shopify", "inventory_quantity": 38}]
    db, winkel = _situatie(stuks=0, varianten=varianten)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["stuk_eraf"] == 0 and not g["shopify_gewist"] and g["extensie_weg"] == []


# ── Tweedehands met één stuk: precies het oude gedrag ───────────────────────

def test_uniek_artikel_ongewijzigd(monkeypatch):
    for kanaal in ("marktplaats", "shopify"):
        db_n, w_n = _situatie(stuks=1 if kanaal == "marktplaats" else 0, vlag=False)
        nieuw = _verkoop(cl, monkeypatch, db_n, w_n, kanaal)
        db_o, w_o = _situatie(stuks=1 if kanaal == "marktplaats" else 0, vlag=False)
        oud = _verkoop(_oud(), monkeypatch, db_o, w_o, kanaal)
        assert nieuw == oud, f"{kanaal}: nieuw {nieuw} tegen oud {oud}"
        assert [l["status"] for l in db_n.t["listings"]] == [l["status"] for l in db_o.t["listings"]]


def test_eerste_keer_meer_dan_een_stuk_zet_de_vlag(monkeypatch):
    db, winkel = _situatie(stuks=5, vlag=False)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert db.t["platform_credentials"][0]["extra_data"].get(sv.VLAG) is True
    assert not g["shopify_gewist"] and g["stuk_eraf"] == 1


def test_shopify_onbereikbaar_bij_voorraadwinkel_wist_niets(monkeypatch):
    db, winkel = _situatie(stuks=10)

    async def _kapot(*_a): raise RuntimeError("503")

    monkeypatch.setattr(sv, "lees_varianten", _kapot)
    gebeurd = {"gewist": False}

    async def _delist(l): gebeurd["gewist"] |= l["platform"] == "shopify"

    async def _naast(fn, *_a, **_k): return fn()

    async def _creds(_c): return "goudlief.myshopify.com", "tok"

    for m in (cl, sv):
        monkeypatch.setattr(m, "naast_de_lus", _naast)
    monkeypatch.setattr(cl, "get_db", lambda: db)
    monkeypatch.setattr(cl, "_delist_one", _delist)
    monkeypatch.setattr(cl, "_enqueue_extension_delete", lambda *_a: None)
    monkeypatch.setattr(tweelingen, "familie_ids", lambda _db, _it: ["i1"])
    monkeypatch.setattr(shp, "_shop_creds", _creds)
    asyncio.run(cl.handle_item_sold("i1", "marktplaats", bewijs=cl.BEWIJS_BESTELLING))
    assert not gebeurd["gewist"] and _status(db, "s1") == "active"
