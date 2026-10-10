"""WooCommerce via de browser van de klant (services/woocommerce_browser.py).

WAAROM (10-10-2026, De Juiste Toon). SiteGround laat onze server niet in
dejuistetoon.eu (HTTP 202 captcha), de browser van de klant wel. Hier draait de
ECHTE WooClient, het echte doorgeefluik, de echte afmelding, wachtrij, webhook
en koppel-endpoints. Nagebootst zijn alleen de database (_DB), de winkel
(_Winkel, met de vormen van een echte WooCommerce) en de browser (_browser):
die doet precies wat frontend/app.html doet: opdrachten ophalen, het verzoek
uitvoeren, en alleen de kopregels teruggeven die een browser via CORS mag lezen.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.database as database  # noqa: E402
from backend.api import platforms as api  # noqa: E402
from backend.api.deps import get_current_user  # noqa: E402
from backend.platforms import woocommerce as w  # noqa: E402
from backend.services import woocommerce_browser as wb  # noqa: E402
from backend.services import woocommerce_orders as wo  # noqa: E402
def _laad_proef(naam):
    """Een andere proef laden via zijn pad: op GitHub staat er een pakket 'tests'
    in site-packages (meegeleverd door een afhankelijkheid) dat voorgaat."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_proef_{naam}", ROOT / "tests" / f"{naam}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_DB = _laad_proef("test_woocommerce")._DB

ROOT_API = "https://dejuistetoon.eu/wp-json/"
CK, CS = "ck_" + "a" * 40, "cs_" + "b" * 40
# Wat een browser van een antwoord van een andere site mag lezen: de veilige
# kopregels plus wat WordPress zelf vrijgeeft (gemeten op dejuistetoon.eu:
# access-control-expose-headers: X-WP-Total, X-WP-TotalPages, Link).
LEESBAAR = ("content-type", "x-wp-total", "x-wp-totalpages", "link", "retry-after")


class _Winkel:
    """Een WooCommerce die de server weigert (SiteGround) en de browser toelaat."""

    def __init__(self, n_producten=3):
        self.producten = {i: {"id": i, "name": f"Kelim {i}", "type": "simple", "status": "publish",
                              "manage_stock": True, "stock_quantity": 1, "stock_status": "instock",
                              "price": "95.00", "sku": f"DJT-{i}", "permalink": f"https://dejuistetoon.eu/p/{i}",
                              "images": [], "attributes": [], "date_created_gmt": "2026-09-01T10:00:00"}
                          for i in range(1, n_producten + 1)}
        self.webhooks = []
        self.verzoeken = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.verzoeken.append((req.method, req.url.path, req.headers.get("user-agent", "")))
        if "Omnivaleur" in req.headers.get("user-agent", ""):
            return httpx.Response(202, headers={"sg-captcha": "challenge", "content-type": "text/html"},
                                  text='<meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=%2F">')
        if req.headers.get("authorization") != "Basic " + base64.b64encode(f"{CK}:{CS}".encode()).decode():
            return httpx.Response(401, json={"code": "woocommerce_rest_cannot_view", "message": "x",
                                             "data": {"status": 401}})
        pad = req.url.path.removeprefix("/wp-json/")
        q = parse_qs(urlsplit(str(req.url)).query)
        if pad == "wc/v3/products" and req.method == "GET":
            per, pagina = int(q.get("per_page", ["10"])[0]), int(q.get("page", ["1"])[0])
            alle = sorted(self.producten.values(), key=lambda p: p["id"])
            stuk = alle[(pagina - 1) * per: pagina * per]
            paginas = max(1, -(-len(alle) // per))
            return httpx.Response(200, json=stuk, headers={"x-wp-total": str(len(alle)),
                                                           "x-wp-totalpages": str(paginas),
                                                           "x-geheim": "niet leesbaar"})
        if pad.startswith("wc/v3/products/"):
            p = self.producten.get(int(pad.split("/")[-1]))
            if p is None:
                return httpx.Response(404, json={"code": "woocommerce_rest_product_invalid_id"})
            if req.method == "PUT":
                p.update(json.loads(req.content))
                if p.get("stock_quantity") == 0:
                    p["stock_status"] = "outofstock"
            return httpx.Response(200, json=p)
        if pad == "wc/v3/webhooks" and req.method == "GET":
            return httpx.Response(200, json=self.webhooks)
        if pad == "wc/v3/webhooks" and req.method == "POST":
            w_ = {**json.loads(req.content), "id": len(self.webhooks) + 1}
            self.webhooks.append(w_)
            return httpx.Response(201, json=w_)
        if pad.startswith("wc/v3/webhooks/") and req.method == "PUT":
            w_ = next(x for x in self.webhooks if x["id"] == int(pad.split("/")[-1]))
            w_.update(json.loads(req.content))
            return httpx.Response(200, json=w_)
        return httpx.Response(404, json={"code": "rest_no_route"})


async def _browser(user_id, winkel, stop: asyncio.Event, kapot=False):
    """Doet wat _wooVoerUit in frontend/app.html doet."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(winkel)) as c:
        while not stop.is_set():
            for o in await wb.haal_opdrachten(user_id, wacht_s=0.2):
                assert "user-agent" not in {k.lower() for k in o["kopregels"]}, \
                    "een browser mag geen User-Agent zetten"
                if kapot:
                    wb.lever_antwoord(user_id, o["id"], {"fout": "Failed to fetch"})
                    continue
                r = await c.request(o["methode"], o["url"], headers={
                    **o["kopregels"], "user-agent": "Mozilla/5.0 Chrome/129"},
                    content=o["inhoud"].encode() if o["inhoud"] else None)
                wb.lever_antwoord(user_id, o["id"], {
                    "status": r.status_code, "tekst": r.text,
                    "kopregels": {k: v for k, v in r.headers.items() if k in LEESBAAR}})


def _met_browser(user_id, winkel, werk, kapot=False):
    wb._klanten.clear()     # elke asyncio.run is een eigen lus

    async def go():
        stop = asyncio.Event()
        taak = asyncio.create_task(_browser(user_id, winkel, stop, kapot))
        await asyncio.sleep(0.05)
        try:
            return await werk()
        finally:
            stop.set()
            await taak
    return asyncio.run(go())


@pytest.fixture(autouse=True)
def _schoon(monkeypatch):
    wb._klanten.clear()
    wb._onderhoud_bezig.clear()
    monkeypatch.setattr(wb, "_start_onderhoud", lambda _u: None)
    monkeypatch.setattr(w, "PAUZE_S", 0)
    monkeypatch.setattr(w, "WACHT_S", (0, 0, 0))
    monkeypatch.setattr(wb, "WACHT_S", 1)


def _rij(**extra):
    return {"user_id": "u1", "platform": "woocommerce", "access_token": CK, "refresh_token": CS,
            "extra_data": {"api_root": ROOT_API, "site": "https://dejuistetoon.eu", "modus": "basic",
                           "via_browser": True, **extra}}


def _db_met(rij=None, **t):
    db = _DB(platform_credentials=[rij or _rij()], **t)

    async def _naast(fn, *_a, **_k): return fn()
    return db, _naast


# ── Het doorgeefluik ─────────────────────────────────────────────────────

def test_server_zelf_krijgt_de_captcha():
    """Uitgangspunt: zonder browser is dit Toons situatie."""
    winkel = _Winkel()

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(winkel),
                                     headers={"User-Agent": w.UA}) as c:
            return await w.WooClient(ROOT_API, CK, CS).verzoek("GET", "wc/v3/products", client=c)
    with pytest.raises(w.WooFout) as e:
        asyncio.run(go())
    assert e.value.soort == "geblokkeerd"


def test_alle_producten_via_de_browser_met_bladeren():
    winkel = _Winkel(n_producten=250)
    client = w.client_uit(_rij())
    assert client.transport is not None
    producten = _met_browser("u1", winkel, client.producten)
    assert [p["id"] for p in producten] == list(range(1, 251))
    assert all("Omnivaleur" not in ua for _m, _p, ua in winkel.verzoeken), \
        "elk verzoek moet via de browser zijn gegaan"


def test_zonder_browser_meteen_duidelijke_fout():
    client = w.client_uit(_rij())
    with pytest.raises(w.WooFout) as e:
        asyncio.run(client.producten())
    assert e.value.soort == "geen_browser"


def test_browserfout_bij_aanmaken_wordt_nooit_herhaald():
    """Failed to fetch kan ook betekenen: de winkel kreeg het wel. Een POST nooit blind opnieuw."""
    winkel = _Winkel()
    client = w.client_uit(_rij())
    with pytest.raises(w.WooFout):
        _met_browser("u1", winkel, lambda: client.verzoek("POST", "wc/v3/products", body={"name": "x"}),
                     kapot=True)
    assert winkel.verzoeken == []


def test_verkeerde_sleutel_via_de_browser_heet_sleutel():
    winkel = _Winkel()
    client = w.WooClient(ROOT_API, CK, "cs_fout", "basic", wb.BrowserTransport("u1"))
    with pytest.raises(w.WooFout) as e:
        _met_browser("u1", winkel, lambda: client.verzoek("GET", "wc/v3/products"))
    assert e.value.soort == "sleutel"


# ── Elders verkocht terwijl het dashboard dicht is ──────────────────────

def test_uitverkocht_wacht_op_de_browser_en_gebeurt_daarna(monkeypatch):
    winkel = _Winkel()
    db, naast = _db_met()
    monkeypatch.setattr(database, "naast_de_lus", naast)
    monkeypatch.setattr(database, "get_db", lambda: db)
    rij = db.t["platform_credentials"][0]

    # Dicht: niets kwijt, het gaat in de wachtrij.
    assert asyncio.run(w.WooCommercePlatform().delete_listing("2", rij)) is True
    assert rij["extra_data"][wb.WACHTRIJ] == ["2"]
    assert winkel.producten[2]["stock_status"] == "instock"

    # Open: de wachtrij wordt afgewerkt.
    gelukt = _met_browser("u1", winkel, lambda: wb.werk_wachtrij_af(db, "u1"))
    assert gelukt == 1
    assert winkel.producten[2]["stock_quantity"] == 0
    assert winkel.producten[2]["stock_status"] == "outofstock"
    assert rij["extra_data"][wb.WACHTRIJ] == []


def test_uitverkocht_met_open_browser_meteen():
    winkel = _Winkel()
    rij = _rij()
    assert _met_browser("u1", winkel, lambda: w.WooCommercePlatform().delete_listing("3", rij))
    assert winkel.producten[3]["stock_status"] == "outofstock"
    assert wb.WACHTRIJ not in rij["extra_data"]


def test_bestellingenronde_slaat_dichte_browserwinkel_over_zonder_storing(monkeypatch):
    db, naast = _db_met()
    monkeypatch.setattr(wo, "naast_de_lus", naast)
    monkeypatch.setattr(wo, "get_db", lambda: db)
    uit = asyncio.run(wo.controleer_woocommerce_verkopen())
    assert uit == {"winkels": 1, "verkocht": 0}
    assert "verkoop_fout" not in db.t["platform_credentials"][0]["extra_data"], \
        "geen 'we kunnen je winkel niet bereiken' terwijl het via de browser gewoon werkt"


# ── Webhook: de winkel meldt een bestelling zelf ─────────────────────────

def test_webhook_aanmaken_en_weer_aanzetten(monkeypatch):
    winkel = _Winkel()
    db, naast = _db_met()
    monkeypatch.setattr(database, "naast_de_lus", naast)
    uit = _met_browser("u1", winkel, lambda: wb.zorg_voor_webhook(db, "u1"))
    extra = db.t["platform_credentials"][0]["extra_data"]
    assert "aangemaakt" in uit and len(winkel.webhooks) == 2
    assert {h["topic"] for h in winkel.webhooks} == {"order.created", "order.updated"}
    assert all(h["delivery_url"] == wb.webhook_url(extra["webhook_token"]) for h in winkel.webhooks)
    assert all(h["secret"] == extra["webhook_geheim"] for h in winkel.webhooks)

    # WooCommerce zette hem stil uit na vijf mislukte afleveringen.
    winkel.webhooks[1]["status"] = "disabled"
    uit = _met_browser("u1", winkel, lambda: wb.zorg_voor_webhook(db, "u1"))
    assert "weer aangezet" in uit and winkel.webhooks[1]["status"] == "active"
    assert len(winkel.webhooks) == 2
    assert _met_browser("u1", winkel, lambda: wb.zorg_voor_webhook(db, "u1")) == "in orde"


def _app(monkeypatch, db, user="u1"):
    async def naast(fn, *_a, **_k): return fn()
    monkeypatch.setattr(api, "naast_de_lus", naast)
    monkeypatch.setattr(api, "get_db", lambda: db)
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _teken(geheim, inhoud):
    return base64.b64encode(hmac.new(geheim.encode(), inhoud, hashlib.sha256).digest()).decode()


def test_webhook_bestelling_wordt_verwerkt(monkeypatch):
    db, _ = _db_met(_rij(webhook_token="c" * 32, webhook_geheim="geheim"))
    verwerkt = []

    async def _verwerk(_db, user_id, order): verwerkt.append((user_id, order["id"])); return 1
    monkeypatch.setattr(wo, "verwerk_bestelling", _verwerk)
    c = _app(monkeypatch, db)
    order = json.dumps({"id": 991, "status": "processing", "line_items": [{"product_id": 2}]}).encode()
    url = "/api/platforms/woocommerce/webhook/" + "c" * 32
    r = c.post(url, content=order, headers={"x-wc-webhook-signature": _teken("geheim", order),
                                            "x-wc-webhook-topic": "order.updated"})
    assert r.status_code == 200 and verwerkt == [("u1", 991)]
    # Vervalst: niets verwerkt.
    r = c.post(url, content=order, headers={"x-wc-webhook-signature": _teken("ander", order)})
    assert r.status_code == 401 and len(verwerkt) == 1
    # De proefmelding die WooCommerce bij het aanmaken stuurt.
    assert c.post(url, content=b"webhook_id=7").status_code == 200
    # Onbekend adres.
    assert c.post("/api/platforms/woocommerce/webhook/" + "d" * 32, content=order).status_code == 404


def test_webhook_handelt_de_echte_verkoop_af(monkeypatch):
    """verwerk_bestelling: alleen betaald telt, en de verkoop gaat naar handle_item_sold."""
    from backend.services import crosslist as cl
    db = _DB(listings=[{"item_id": "i9", "platform": "woocommerce", "platform_listing_id": "2"}],
             items=[{"id": "i9", "user_id": "u1"}])

    async def naast(fn, *_a, **_k): return fn()
    monkeypatch.setattr(wo, "naast_de_lus", naast)
    verkocht = []

    async def _sold(item_id, platform, **k): verkocht.append((item_id, platform, k.get("sold_price")))
    monkeypatch.setattr(cl, "handle_item_sold", _sold)
    regel = {"product_id": 2, "quantity": 1, "total": "95.00", "total_tax": "0"}
    assert asyncio.run(wo.verwerk_bestelling(db, "u1", {"id": 1, "status": "pending", "line_items": [regel]})) == 0
    assert asyncio.run(wo.verwerk_bestelling(db, "u1", {"id": 1, "status": "processing", "line_items": [regel]})) == 1
    assert verkocht == [("i9", "woocommerce", 95.0)]


# ── Koppelen ─────────────────────────────────────────────────────────────

def test_sleutel_plakken_server_geblokkeerd_geeft_409_met_kopregel(monkeypatch):
    db, _ = _db_met()
    db.t["platform_credentials"] = []
    c = _app(monkeypatch, db)

    async def _blok(*_a, **_k): raise w.WooFout(w.SITEGROUND_MELDING, "geblokkeerd", 202)
    monkeypatch.setattr(w, "controleer_sleutels", _blok)
    monkeypatch.setattr(api, "_meld_mislukte_woo_koppeling", lambda *_a: True)
    r = c.post("/api/platforms/woocommerce/connect-keys",
               json={"store": "dejuistetoon.eu", "consumer_key": CK, "consumer_secret": CS})
    assert r.status_code == 409 and r.headers.get(api.VIA_BROWSER_KOP) == "1"
    assert "SiteGround" in r.json()["detail"]


def test_sleutel_plakken_via_de_browser(monkeypatch):
    winkel = _Winkel(n_producten=7)
    db, _ = _db_met()
    db.t["platform_credentials"] = []
    bewaard = {}
    monkeypatch.setattr(api, "_save_credentials", lambda u, p, t: bewaard.update(t))
    monkeypatch.setattr(api, "_woo_webhook_op_achtergrond", lambda _u: asyncio.sleep(0))
    c = _app(monkeypatch, db)

    async def werk():
        # De TestClient is synchroon; laat hem in een thread lopen naast de browser.
        return await asyncio.to_thread(c.post, "/api/platforms/woocommerce/connect-keys", json={
            "store": "dejuistetoon.eu", "api_root": ROOT_API, "consumer_key": CK, "consumer_secret": CS})
    # Het doorgeefluik zit in het geheugen van het proces; de TestClient draait
    # een eigen lus, dus de browser draait hier in die van de app.
    with c:     # één lus voor de hele proef, zoals de echte server
        r = _met_browser_in_app(c, "u1", winkel, werk)
    assert r.status_code == 200, r.text
    assert r.json()["producten"] == 7
    assert bewaard["extra_data"]["via_browser"] is True
    assert bewaard["extra_data"]["api_root"] == ROOT_API


def test_browser_api_adres_moet_bij_de_winkel_horen():
    assert api._browser_api_root("https://dejuistetoon.eu", "https://dejuistetoon.eu/wp-json/")
    assert api._browser_api_root("https://dejuistetoon.eu", "https://www.dejuistetoon.eu/?rest_route=/")
    assert not api._browser_api_root("https://dejuistetoon.eu", "https://kwaad.nl/wp-json/")
    assert not api._browser_api_root("https://dejuistetoon.eu", "http://dejuistetoon.eu/wp-json/")
    assert not api._browser_api_root("https://dejuistetoon.eu", "https://dejuistetoon.eu/iets/")


def test_knop_via_de_browser_staat_en_callback(monkeypatch):
    db, _ = _db_met()
    db.t["platform_credentials"] = []
    c = _app(monkeypatch, db)
    r = c.get("/api/platforms/woocommerce/auth-url",
              params={"store": "dejuistetoon.eu", "api_root": ROOT_API})
    assert r.status_code == 200 and r.json()["via_browser"] is True
    staat = parse_qs(urlsplit(r.json()["url"]).query)["user_id"][0]
    assert w.lees_staat(staat)["b"] == 1
    assert r.json()["url"].startswith("https://dejuistetoon.eu/wc-auth/v1/authorize?")

    # De winkel stuurt de sleutel; de server kan niet controleren en bewaart hem via de browser.
    bewaard = {}
    monkeypatch.setattr(api, "_save_credentials", lambda u, p, t: bewaard.update(u=u, **t))
    asyncio.run(api._woo_controleer_en_bewaar("u1", ROOT_API, CK, CS, True))
    assert bewaard["u"] == "u1" and bewaard["extra_data"]["via_browser"] is True

    r = c.get("/api/platforms/woocommerce/auth-url",
              params={"store": "dejuistetoon.eu", "api_root": "https://kwaad.nl/wp-json/"})
    assert r.status_code == 400


def _met_browser_in_app(client, user_id, winkel, werk):
    """De browser draait in een eigen thread met een eigen lus, net als een echte."""
    import threading
    klaar = threading.Event()

    def browser():
        async def lus():
            async with httpx.AsyncClient(transport=httpx.MockTransport(winkel)) as c:
                while not klaar.is_set():
                    for o in await _via_app(client, "get", "/api/platforms/woocommerce/browser/opdrachten"):
                        r = await c.request(o["methode"], o["url"], headers={
                            **o["kopregels"], "user-agent": "Mozilla/5.0 Chrome/129"},
                            content=o["inhoud"].encode() if o["inhoud"] else None)
                        await asyncio.to_thread(client.post, "/api/platforms/woocommerce/browser/antwoord", json={
                            "id": o["id"], "status": r.status_code, "tekst": r.text,
                            "kopregels": {k: v for k, v in r.headers.items() if k in LEESBAAR}})
        asyncio.run(lus())

    t = threading.Thread(target=browser, daemon=True)
    t.start()
    try:
        return asyncio.run(werk())
    finally:
        klaar.set()
        t.join(timeout=40)


async def _via_app(client, methode, pad):
    r = await asyncio.to_thread(getattr(client, methode), pad)
    return r.json().get("opdrachten", [])


def test_browser_valt_weg_tijdens_afmelden_gaat_in_de_wachtrij(monkeypatch):
    """Online, maar het verzoek mislukt in de browser: niet kwijt, maar wachtrij.
    En een mislukte wachtrijronde laat het product in de wachtrij staan."""
    winkel = _Winkel()
    db, naast = _db_met()
    monkeypatch.setattr(database, "naast_de_lus", naast)
    monkeypatch.setattr(database, "get_db", lambda: db)
    rij = db.t["platform_credentials"][0]
    assert _met_browser("u1", winkel, lambda: w.WooCommercePlatform().delete_listing("2", rij), kapot=True)
    assert rij["extra_data"][wb.WACHTRIJ] == ["2"]
    assert _met_browser("u1", winkel, lambda: wb.werk_wachtrij_af(db, "u1"), kapot=True) == 0
    assert rij["extra_data"][wb.WACHTRIJ] == ["2"], "mislukt is niet gelukt"
    assert _met_browser("u1", winkel, lambda: wb.werk_wachtrij_af(db, "u1")) == 1
    assert rij["extra_data"][wb.WACHTRIJ] == [] and winkel.producten[2]["stock_status"] == "outofstock"
