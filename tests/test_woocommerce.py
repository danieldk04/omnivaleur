"""WooCommerce-koppeling (09-10-2026, Mikkis).

Draait de ECHTE handle_item_sold, de echte voorraadregel, de echte bestelronde
en de echte omzetting van een product naar een importkandidaat. Alleen de winkel
zelf is nagebootst (FakeWoo); tegen een echte WooCommerce draait
tests/test_woocommerce_live.py.

Voor-en-na: de versie van main van vóór deze koppeling (VOOR) kent WooCommerce
niet. Een verkoop op Marktplaats van een artikel dat ook in de winkel staat
probeerde daar het product af te melden, ook als er nog 5 stuks lagen.
"""
import asyncio
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.platforms import woocommerce as w  # noqa: E402
from backend.services import crosslist as cl  # noqa: E402
from backend.services import shopify_voorraad as sv  # noqa: E402
from backend.services import tweelingen  # noqa: E402
from backend.services import woocommerce_orders as wo  # noqa: E402
from backend.services import woocommerce_scan as ws  # noqa: E402
from backend.services import woocommerce_voorraad as wv  # noqa: E402

VOOR = "cf974bc2"


# ── Nagebootste database en winkel ──────────────────────────────────────────

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


class FakeWoo:
    """Wat de code van een winkel vraagt, met de antwoorden van een echte
    WooCommerce (vormen nagemeten op de lokale testwinkel, 09-10-2026)."""

    def __init__(self, producten, variaties=None, orders=None):
        self.p = {str(p["id"]): p for p in producten}
        self.v = {k: list(vs) for k, vs in (variaties or {}).items()}
        self.orders = orders or []
        self.modus, self.modus_gewijzigd = "basic", False
        self.schrijf = []

    async def product(self, pid): return self.p.get(str(pid))
    async def variaties(self, pid): return self.v.get(str(pid), [])
    async def producten(self, gewijzigd_na=None): return list(self.p.values())
    async def bestellingen(self, sinds): return list(self.orders)

    async def werk_bij(self, pid, velden, variatie=None):
        self.schrijf.append((str(pid), variatie, dict(velden)))
        doel = (next(v for v in self.v[str(pid)] if str(v["id"]) == str(variatie))
                if variatie else self.p[str(pid)])
        doel.update(velden)
        if "stock_quantity" in velden and doel.get("manage_stock"):
            doel["stock_status"] = "instock" if velden["stock_quantity"] > 0 else "outofstock"
        return doel


def _product(pid=101, stuks=1, beheer=True, **over):
    p = {"id": pid, "name": "Jottum winterjas Gerda", "type": "simple", "status": "publish",
         "manage_stock": beheer, "stock_quantity": stuks if beheer else None,
         "stock_status": "instock" if (stuks > 0 or not beheer) else "outofstock",
         "price": "45.00", "regular_price": "45.00", "sku": "MK-101",
         "permalink": "https://mikkis.nl/product/jottum-winterjas-gerda/",
         "date_created_gmt": "2026-10-01T10:00:00",
         "description": "<p>Mooie winterjas.</p><p>Materiaal: wol</p>",
         "images": [{"src": "https://mikkis.nl/a.jpg"}, {"src": "https://mikkis.nl/b.jpg"}],
         "attributes": [{"name": "Merk", "options": ["Jottum"]},
                        {"name": "Maat", "options": ["104"]},
                        {"name": "Staat", "options": ["Zo goed als nieuw"]},
                        {"name": "Geslacht", "options": ["Meisje"]}]}
    p.update(over)
    return p


def _situatie(winkel: FakeWoo, vlag=False):
    return _DB(
        items=[{"id": "i1", "user_id": "u1", "title": "Jottum winterjas Gerda", "sku": "MK-101"}],
        listings=[
            {"id": "w1", "item_id": "i1", "platform": "woocommerce", "status": "active",
             "platform_listing_id": "101"},
            {"id": "m1", "item_id": "i1", "platform": "marktplaats", "status": "active",
             "platform_listing_id": "m2400000001"},
            {"id": "v1", "item_id": "i1", "platform": "vinted", "status": "active",
             "platform_listing_id": "7000001"},
        ],
        platform_credentials=[{"user_id": "u1", "platform": "woocommerce",
                               "access_token": "ck_x", "refresh_token": "cs_x",
                               "extra_data": {"api_root": "https://mikkis.nl/wp-json/",
                                              **({sv.VLAG: True} if vlag else {})}}],
        jobs=[], sync_events=[],
    )


def _verkoop(module, monkeypatch, db, winkel, kanaal):
    gebeurd = {"woo_afgemeld": [], "extensie_weg": []}

    async def _naast(fn, *_a, **_k): return fn()

    async def _delist(l):
        if l["platform"] == "woocommerce":
            gebeurd["woo_afgemeld"].append(l["platform_listing_id"])
            # De echte afmelding: op uitverkocht, nooit wissen.
            await w.WooCommercePlatform().delete_listing(l["platform_listing_id"], {})

    for m in (module, sv, wv):
        monkeypatch.setattr(m, "naast_de_lus", _naast, raising=False)
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_delist_one", _delist)
    monkeypatch.setattr(module, "_nooit_online", lambda *_a: False)
    monkeypatch.setattr(module, "_last_listed_title", lambda *_a: "Jottum winterjas Gerda")
    monkeypatch.setattr(module, "_enqueue_extension_delete",
                        lambda _db, _u, _i, l, _r: gebeurd["extensie_weg"].append(l["platform"]))
    monkeypatch.setattr(tweelingen, "familie_ids", lambda _db, _it: ["i1"])
    monkeypatch.setattr(wv, "client_uit", lambda _c: winkel)
    monkeypatch.setattr(w, "client_uit", lambda _c: winkel)
    asyncio.run(module.handle_item_sold("i1", kanaal, sold_price=45.0,
                                        bewijs=module.BEWIJS_BESTELLING))
    return gebeurd


def _status(db, lid):
    return next(l["status"] for l in db.t["listings"] if l["id"] == lid)


def _oud():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/services/crosslist.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "woocommerce" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_crosslist_woo.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("backend.services.oude_crosslist_woo", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


# ── Voor: de oude code meldt een voorraadproduct af bij één verkoop elders ──

def test_oud_marktplaats_verkoop_meldt_product_met_voorraad_af(monkeypatch):
    winkel = FakeWoo([_product(stuks=5)])
    db = _situatie(winkel)
    g = _verkoop(_oud(), monkeypatch, db, winkel, "marktplaats")
    assert g["woo_afgemeld"] == ["101"], "de oude code kende geen winkelvoorraad"
    assert winkel.p["101"]["stock_quantity"] == 0, "alle 5 stuks weg na één verkoop"


# ── Na: de voorraadregel ─────────────────────────────────────────────────────

def test_marktplaats_verkoop_haalt_een_stuk_af_bij_voorraad(monkeypatch):
    winkel = FakeWoo([_product(stuks=5)])
    db = _situatie(winkel)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert winkel.p["101"]["stock_quantity"] == 4 and g["woo_afgemeld"] == []
    assert g["extensie_weg"] == [], "Vinted blijft staan: er zijn er nog 4"
    assert _status(db, "w1") == "active" and _status(db, "m1") == "delisted"
    assert any(l.get("extra_data", {}).get(sv.VLAG) for l in db.t["platform_credentials"]), \
        "5 stuks gezien: vanaf nu een voorraadwinkel"


def test_herhaalde_melding_haalt_geen_tweede_stuk_af(monkeypatch):
    winkel = FakeWoo([_product(stuks=5)])
    db = _situatie(winkel)
    _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert winkel.p["101"]["stock_quantity"] == 4


def test_uniek_artikel_elders_verkocht_gaat_in_de_winkel_op_uitverkocht(monkeypatch):
    winkel = FakeWoo([_product(stuks=1)])
    db = _situatie(winkel)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["woo_afgemeld"] == ["101"] and g["extensie_weg"] == ["vinted"]
    p = winkel.p["101"]
    assert p["stock_quantity"] == 0 and p["stock_status"] == "outofstock"
    assert p["status"] == "publish", "nooit wissen: de productpagina blijft"


def test_uniek_artikel_verkocht_in_de_winkel_haalt_het_elders_weg(monkeypatch):
    winkel = FakeWoo([_product(stuks=0)])   # de bestelling verlaagde de voorraad al
    db = _situatie(winkel)
    g = _verkoop(cl, monkeypatch, db, winkel, "woocommerce")
    assert sorted(g["extensie_weg"]) == ["marktplaats", "vinted"]
    assert _status(db, "w1") == "sold" and g["woo_afgemeld"] == []


def test_verkoop_in_de_winkel_met_voorraad_laat_alles_staan(monkeypatch):
    winkel = FakeWoo([_product(stuks=4)])
    db = _situatie(winkel, vlag=True)
    g = _verkoop(cl, monkeypatch, db, winkel, "woocommerce")
    assert g["extensie_weg"] == [] and all(l["status"] == "active" for l in db.t["listings"])


def test_laatste_stuk_elders_product_blijft_uitverkocht_staan(monkeypatch):
    winkel = FakeWoo([_product(stuks=1)])
    db = _situatie(winkel, vlag=True)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert winkel.p["101"]["stock_quantity"] == 0
    assert g["woo_afgemeld"] == [], "op, maar blijft staan om aan te vullen"
    assert g["extensie_weg"] == ["vinted"]


def test_twee_maten_met_voorraad_niet_raden(monkeypatch):
    winkel = FakeWoo([_product(type="variable", manage_stock=False, stock_quantity=None,
                               variations=[201, 202])],
                     {"101": [{"id": 201, "manage_stock": True, "stock_quantity": 1},
                              {"id": 202, "manage_stock": True, "stock_quantity": 2}]})
    db = _situatie(winkel)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert winkel.schrijf == [] and g["woo_afgemeld"] == [] and g["extensie_weg"] == []


def test_een_maat_over_gaat_eraf_bij_die_variant(monkeypatch):
    winkel = FakeWoo([_product(type="variable", manage_stock=False, stock_quantity=None,
                               variations=[201, 202])],
                     {"101": [{"id": 201, "manage_stock": True, "stock_quantity": 0},
                              {"id": 202, "manage_stock": True, "stock_quantity": 2}]})
    db = _situatie(winkel, vlag=True)
    _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert winkel.schrijf == [("101", "202", {"stock_quantity": 1})]


def test_winkel_onbereikbaar_bij_voorraadwinkel_laat_alles_staan(monkeypatch):
    class Kapot(FakeWoo):
        async def product(self, pid): raise w.WooFout("weg", "onbereikbaar")
    winkel = Kapot([_product(stuks=5)])
    db = _situatie(winkel, vlag=True)
    g = _verkoop(cl, monkeypatch, db, winkel, "marktplaats")
    assert g["woo_afgemeld"] == [] and g["extensie_weg"] == []


# ── De bestelronde ──────────────────────────────────────────────────────────

def _order(**over):
    o = {"id": 900, "status": "processing", "date_paid_gmt": "2026-10-09T08:00:00",
         "line_items": [{"product_id": 101, "variation_id": 0, "sku": "MK-101", "quantity": 1,
                         "total": "37.19", "total_tax": "7.81"}]}
    o.update(over)
    return o


def test_bestelregel_bedrag_per_stuk_met_btw():
    r = wo.regels_uit_bestelling(_order(line_items=[{"product_id": 5, "quantity": 2,
                                                     "total": "50.00", "total_tax": "10.50"}]))
    assert r[0]["price"] == 30.25 and r[0]["product_id"] == "5"


def test_bestelronde_meldt_verkoop_en_zet_merkteken(monkeypatch):
    from datetime import datetime, timezone
    winkel = FakeWoo([_product(stuks=0)], orders=[_order()])
    db = _situatie(winkel)
    geboekt = []

    async def _naast(fn, *_a, **_k): return fn()

    async def _sold(item_id, kanaal, **k): geboekt.append((item_id, kanaal, k["sold_price"], k["sold_at"]))

    monkeypatch.setattr(wo, "naast_de_lus", _naast)
    monkeypatch.setattr(wo, "client_uit", lambda _c: winkel)
    monkeypatch.setattr(cl, "handle_item_sold", _sold)
    rij = db.t["platform_credentials"][0]
    n = asyncio.run(wo.controleer_winkel(db, {**rij}, datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)))
    assert n == 1 and geboekt == [("i1", "woocommerce", 45.0, "2026-10-09T08:00:00Z")]
    assert rij["extra_data"]["orders_gezien_tot"].startswith("2026-10-09T08:50")


def test_bestelling_van_een_andere_verkoper_wordt_niet_gematcht(monkeypatch):
    db = _situatie(FakeWoo([]))
    db.t["items"][0]["user_id"] = "iemand-anders"

    async def _naast(fn, *_a, **_k): return fn()
    monkeypatch.setattr(wo, "naast_de_lus", _naast)
    assert asyncio.run(wo.match_verkoop(db, "u1", {"product_id": "101", "sku": "MK-101"})) is None


# ── Van product naar importkandidaat ───────────────────────────────────────

def test_scanregel_haalt_merk_maat_staat_en_doelgroep_uit_de_eigenschappen():
    r = ws.naar_scanregel(_product())
    assert (r["brand"], r["size"], r["condition"], r["gender"]) == \
        ("Jottum", "104", "Zo goed als nieuw", "kinderen")
    assert r["platform_listing_id"] == "101" and r["price"] == 45.0 and r["sku"] == "MK-101"
    assert r["photo_urls"] == ["https://mikkis.nl/a.jpg", "https://mikkis.nl/b.jpg"]
    assert r["material"] == "wol" and r["platform_listed_at"] == "2026-10-01T10:00:00Z"
    assert r["is_closed"] is False


def test_scanregel_meerdere_maten_geen_maat_en_uitverkocht_gesloten():
    r = ws.naar_scanregel(_product(attributes=[{"name": "Maat", "options": ["62", "68"]}],
                                   stock_status="outofstock"))
    assert r["size"] is None and r["is_closed"] is True


def test_unisex_blijft_open_voor_de_import():
    r = ws.naar_scanregel(_product(attributes=[{"name": "Geslacht", "options": ["Unisex"]}]))
    assert r["gender"] is None


def test_voorraadwinkel_herkend_aan_stuks_of_maten():
    assert ws.heeft_meerdere_stuks(_product(stuks=3))
    assert not ws.heeft_meerdere_stuks(_product(stuks=1))
    assert ws.heeft_meerdere_stuks(_product(type="variable", variations=[1, 2]))


# ── Adres, API en de getekende staat ─────────────────────────────────────────

def test_winkeladres_opschonen():
    assert w.normaliseer_adres("mikkis.nl") == "https://mikkis.nl"
    assert w.normaliseer_adres("https://www.Mikkis.nl/wp-admin/edit.php") == "https://www.mikkis.nl"
    assert w.normaliseer_adres("voorbeeld.nl/winkel-a/") == "https://voorbeeld.nl/winkel-a"
    assert w.normaliseer_adres("geen adres") == ""


def test_api_adres_met_en_zonder_mooie_permalinks():
    assert w._api_url("https://a.nl/wp-json/", "wc/v3/products", {"page": 2}) == \
        "https://a.nl/wp-json/wc/v3/products?page=2"
    u = w._api_url("https://a.nl/?rest_route=/", "wc/v3/products", {"page": 2})
    assert u == "https://a.nl/?rest_route=/wc/v3/products&page=2"
    assert w.site_van_api("https://a.nl/sub/wp-json/") == "https://a.nl/sub"


def test_koppeladres_volgt_de_permalinks():
    assert w.koppel_url("https://a.nl/wp-json/", "s", "https://r", "https://c") \
        .startswith("https://a.nl/wc-auth/v1/authorize?app_name=Omnivaleur&scope=read_write")
    assert "wc-auth-route=authorize" in w.koppel_url("https://a.nl/?rest_route=/", "s", "r", "c")


def test_staat_is_getekend_en_verloopt():
    s = w.maak_staat("u1", "https://a.nl/wp-json/", nu=1_000_000)
    assert w.lees_staat(s, nu=1_000_100) == {"u": "u1", "a": "https://a.nl/wp-json/", "t": 1_000_000}
    deel, sig = s.rsplit(".", 1)
    vals = w.maak_staat("aanvaller", "https://a.nl/wp-json/", nu=1_000_000).rsplit(".", 1)[0] + "." + sig
    assert w.lees_staat(vals, nu=1_000_100) is None, "andere inhoud, oude handtekening"
    assert w.lees_staat(s, nu=1_000_000 + w.STAAT_GELDIG_S + 1) is None


def test_oauth1_handtekening_is_stabiel():
    a = w.oauth1_params("GET", "http://a.nl/wp-json/wc/v3/products?per_page=1", "ck_1", "cs_1",
                        nonce="n", tijd=1)
    b = w.oauth1_params("GET", "http://a.nl/wp-json/wc/v3/products?per_page=1", "ck_1", "cs_1",
                        nonce="n", tijd=1)
    assert a == b and a["oauth_signature_method"] == "HMAC-SHA256"


# ── Oude winkels en rommelige antwoorden (09-10-2026) ──────────────────────

def test_php_waarschuwing_voor_de_gegevens_wordt_overgeslagen():
    tekst = ('<br />\n<b>Warning</b>:  require(/wordpress/.maintenance): failed to open stream in '
             '<b>/wordpress/wp-includes/load.php</b> on line <b>444</b><br />\n[{"id": 9}]')
    assert w.lees_json(tekst) == [{"id": 9}]
    try:
        w.lees_json("<html><body>Access denied</body></html>")
        raise AssertionError("een blokkadepagina is geen gegevens")
    except ValueError:
        pass


def test_oude_winkel_negeert_het_tijdfilter_en_geeft_alles(monkeypatch):
    """WooCommerce < 5.8 kent modified_after niet. Dan mag er geen oude
    bestelling als nieuwe verkoop binnenkomen, en stopt het bladeren."""
    pagina1 = ([{"id": i, "status": "completed", "date_created_gmt": "2026-10-09T08:00:00",
                 "date_modified_gmt": "2026-10-09T08:00:00"} for i in range(3)]
               + [{"id": 50 + i, "status": "completed", "date_created_gmt": "2025-01-01T00:00:00",
                   "date_modified_gmt": "2025-01-01T00:00:00"} for i in range(97)])
    pagina2 = [{"id": 900 + i, "status": "completed", "date_created_gmt": "2024-01-01T00:00:00",
                "date_modified_gmt": "2024-01-01T00:00:00"} for i in range(100)]
    gevraagd = []

    async def _verzoek(self, methode, route, params=None, **k):
        gevraagd.append(params["page"])
        return 200, (pagina1 if params["page"] == 1 else pagina2), {}

    monkeypatch.setattr(w.WooClient, "verzoek", _verzoek)
    uit = asyncio.run(w.WooClient("https://a.nl/wp-json/", "ck_x", "cs_x").bestellingen("2026-10-09T07:50:00"))
    assert [o["id"] for o in uit] == [0, 1, 2]
    assert gevraagd == [1, 2], "pagina 2 is helemaal oud: daar stopt het"


def test_alleen_betaalde_bestellingen_tellen(monkeypatch):
    rij = [{"id": i, "status": s, "date_created_gmt": "2026-10-09T08:00:00",
            "date_modified_gmt": "2026-10-09T08:00:00"}
           for i, s in enumerate(["pending", "processing", "on-hold", "cancelled", "completed",
                                  "failed", "refunded"])]

    async def _verzoek(self, *a, **k): return 200, rij, {}
    monkeypatch.setattr(w.WooClient, "verzoek", _verzoek)
    uit = asyncio.run(w.WooClient("https://a.nl/wp-json/", "ck_x", "cs_x").bestellingen("2026-10-09T07:00:00"))
    assert sorted(o["status"] for o in uit) == ["completed", "on-hold", "processing"]


def test_aanmaken_wordt_nooit_blind_herhaald(monkeypatch):
    """WooCommerce 5.1 crashte ná het opslaan (500); vier herhaalpogingen gaven
    vier bestellingen. Een product mag zo nooit dubbel in de winkel komen."""
    posts, gezocht = [], []

    async def _verzoek(self, methode, route, params=None, body=None, **k):
        if methode == "POST":
            posts.append(body["sku"])
            raise w.WooFout("crash", "serverfout", 500)
        gezocht.append(params.get("sku"))
        # Eerste zoektocht: nog niets. Na de crash: het product staat er wel.
        return 200, ([] if len(gezocht) == 1 else [{"id": 77, "permalink": "https://a.nl/p/77"}]), {}

    monkeypatch.setattr(w.WooClient, "verzoek", _verzoek)
    async def _geen_wacht(*_a): return None
    monkeypatch.setattr(w.asyncio, "sleep", _geen_wacht)
    creds = {"access_token": "ck_x", "refresh_token": "cs_x",
             "extra_data": {"api_root": "https://a.nl/wp-json/", "modus": "basic"}}
    uit = asyncio.run(w.WooCommercePlatform().create_listing(
        {"id": "abcdef123456789", "title": "Jas", "price": 10}, creds))
    assert posts == ["OMNI-abcdef123456"], "precies één keer aangemaakt"
    assert uit["platform_listing_id"] == "77", "het product van de crash teruggevonden"

