"""WooCommerce via de browser, van begin tot eind in een ECHTE Chromium.

WAAROM (10-10-2026, De Juiste Toon). De koppeling via de browser hangt aan
dingen die je met nagebootste Python niet bewijst: CORS en de preflight bij een
Authorization-kopregel, welke kopregels een browser mag lezen, fetch zonder
cookies, en de echte JavaScript in frontend/app.html. Hier draait alles echt:
  - onze FastAPI-routes (uvicorn), met een nagebootste database;
  - de functies uit frontend/app.html, letterlijk eruit geknipt;
  - Chromium (Playwright);
  - een winkel op https die zich gedraagt als WordPress (CORS precies zoals
    rest_send_cors_headers, gemeten op dejuistetoon.eu) en als SiteGround: onze
    server krijgt HTTP 202 met sg-captcha, een browser komt erin.
Met WOO_E2E_WINKEL=https://... staat er een echte WooCommerce achter de
SiteGround-nabootsing (zo draait hij op GitHub, met WordPress Playground).

Draait alleen als Playwright er is.
"""
import asyncio
import base64
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pw = pytest.importorskip("playwright.sync_api")

import backend.database as database  # noqa: E402
from backend.api import platforms as api  # noqa: E402
from backend.api.deps import get_current_user  # noqa: E402
from backend.platforms import woocommerce as w  # noqa: E402
from backend.services import woocommerce_browser as wb  # noqa: E402
from tests.test_woocommerce import _DB  # noqa: E402
from tests.test_woocommerce_browser import CK, CS, _Winkel  # noqa: E402

ECHT = os.environ.get("WOO_E2E_WINKEL")          # een echte WooCommerce erachter
ECHT_CK = os.environ.get("WOO_E2E_CK") or CK
ECHT_CS = os.environ.get("WOO_E2E_CS") or CS

FUNCTIES = ["_wooAdres", "startWooKnop", "submitWooKeys", "wooDoorgeefStart", "_wooVoerUit",
            "wooZoekApiInBrowser", "_wooKnopViaBrowser", "_wooControleerViaBrowser"]


def _vrije_poort():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _knip_uit_app() -> str:
    """De echte functies uit frontend/app.html, zoals een klant ze krijgt."""
    bron = (ROOT / "frontend" / "app.html").read_text()
    stukken = []
    for naam in ("WOO_NIET_GEVONDEN", "WOO_DOORGEEF"):
        m = re.search(rf"^const {naam} = .*?;$", bron, re.M)
        assert m, naam
        stukken.append(m.group(0))
    for naam in FUNCTIES:
        m = re.search(rf"^(async )?function {naam}\(.*?^\}}$", bron, re.M | re.S)
        assert m, f"functie {naam} niet gevonden in app.html"
        stukken.append(m.group(0))
    return "\n\n".join(stukken)


PAGINA = """<!doctype html><meta charset="utf-8">
<input id="woo-store-input"><input id="woo-ck-input"><input id="woo-cs-input">
<button id="woo-connect-btn"></button><button id="woo-keys-btn"></button>
<script>
const API = '';
window.__melding = []; window.__gekoppeld = null;
async function apiFetch(url, opts = {}) {
  return fetch(url, { ...opts, headers: { Authorization: 'Bearer proef', ...(opts.headers || {}) } });
}
async function parseJsonSafe(r) { try { return await r.json(); } catch (_) { return null; } }
function _wooMsg(t, s) { window.__melding.push([s, t]); }
function _wooToonSleutels() {}
function _wooGekoppeld(site) { window.__gekoppeld = site || 'ja'; }
function connectWooCommerce() {}
function showToast() {}
const state = { connected: ['woocommerce'] };
%s
</script>"""


# ── De winkel: WordPress-CORS + SiteGround-nabootsing ────────────────────

WP_CORS = {"access-control-allow-methods": "OPTIONS, GET, POST, PUT, PATCH, DELETE",
           "access-control-allow-credentials": "true",
           "access-control-allow-headers": "Authorization, X-WP-Nonce, Content-Disposition, Content-MD5, Content-Type",
           "access-control-expose-headers": "X-WP-Total, X-WP-TotalPages, Link"}


def _winkel_app(winkel: _Winkel | None, echt: str | None, verzoeken: list):
    """ASGI-app. Server (geen browser) → 202 sg-captcha; browser → WordPress."""
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        kop = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        inhoud = b""
        while True:
            m = await receive()
            inhoud += m.get("body", b"")
            if not m.get("more_body"):
                break
        pad = scope["path"] + (("?" + scope["query_string"].decode()) if scope["query_string"] else "")
        ua = kop.get("user-agent", "")
        verzoeken.append((scope["method"], pad, "browser" if "Mozilla" in ua else ua))
        if "Mozilla" not in ua:
            await _stuur(send, 202, {"content-type": "text/html", "sg-captcha": "challenge"},
                         b'<html><head><meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/?r=%2F"></head></html>')
            return
        if echt:
            async with httpx.AsyncClient(verify=False) as c:
                r = await c.request(scope["method"], echt.rstrip("/") + pad, content=inhoud or None,
                                    headers={k: v for k, v in kop.items() if k not in ("host", "content-length")})
            await _stuur(send, r.status_code, {k: v for k, v in r.headers.items()
                                               if k not in ("content-length", "content-encoding", "transfer-encoding")},
                         r.content)
            return
        cors = ({"access-control-allow-origin": kop["origin"], **WP_CORS, "vary": "Origin"}
                if kop.get("origin") else {})
        if scope["method"] == "OPTIONS":
            await _stuur(send, 200, {**cors, "allow": "GET, POST, PUT"}, b"")
            return
        if scope["path"] == "/wp-json/":
            await _stuur(send, 200, {**cors, "content-type": "application/json",
                                     "link": '<https://127.0.0.1/wp-json/>; rel="https://api.w.org/"'},
                         json.dumps({"name": "Proefwinkel", "namespaces": ["wp/v2", "wc/v3"]}).encode())
            return
        r = winkel(httpx.Request(scope["method"], "https://winkel" + pad, content=inhoud,
                                 headers={k: v for k, v in kop.items() if k in ("authorization", "content-type", "user-agent")}))
        await _stuur(send, r.status_code, {**cors, **{k: v for k, v in r.headers.items()
                                                      if k not in ("content-length",)}}, r.content)
    return app


async def _stuur(send, status, kop, inhoud):
    await send({"type": "http.response.start", "status": status,
                "headers": [(k.encode(), str(v).encode()) for k, v in kop.items()]
                + [(b"content-length", str(len(inhoud)).encode())]})
    await send({"type": "http.response.body", "body": inhoud})


def _certificaat(map_: Path):
    sleutel, cert = map_ / "sleutel.pem", map_ / "cert.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-keyout", str(sleutel), "-out", str(cert), "-subj", "/CN=127.0.0.1",
                    "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True)
    return sleutel, cert


def _start(app, poort, **ssl_):
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=poort, log_level="warning",
                                           lifespan="off", **ssl_))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.05)
    raise RuntimeError("server start niet")


@pytest.fixture
def omgeving(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    sleutel, cert = _certificaat(tmp_path)
    # Onze server vertrouwt het proefcertificaat (zoals een echt certificaat),
    # zodat hij echt de SiteGround-captcha krijgt en geen certificaatfout.
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))

    winkel = None if ECHT else _Winkel(n_producten=230)
    verzoeken: list = []
    wp, ons = _vrije_poort(), _vrije_poort()
    winkel_srv = _start(_winkel_app(winkel, ECHT, verzoeken), wp,
                        ssl_keyfile=str(sleutel), ssl_certfile=str(cert))

    db = _DB(platform_credentials=[], items=[], listings=[])

    def _bewaar(user_id, platform, tokens):
        db.t["platform_credentials"] = [r for r in db.t["platform_credentials"]
                                        if not (r["user_id"] == user_id and r["platform"] == platform)]
        db.t["platform_credentials"].append({"user_id": user_id, "platform": platform, **tokens})

    async def _naast(fn, *_a, **_k): return fn()
    for mod in (api, database):
        monkeypatch.setattr(mod, "get_db", lambda: db)
        monkeypatch.setattr(mod, "naast_de_lus", _naast)
    monkeypatch.setattr(api, "_save_credentials", _bewaar)
    monkeypatch.setattr(api, "_meld_mislukte_woo_koppeling", lambda *_a: True)   # geen echte mail
    monkeypatch.setattr(wb, "ONLINE_S", 2)
    monkeypatch.setattr(wb, "WACHT_S", 3)
    wb._klanten.clear()
    wb._onderhoud_bezig.clear()

    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: "u1"
    pagina = PAGINA % _knip_uit_app()
    app.get("/proef", response_class=HTMLResponse)(lambda: pagina)

    # Wat de server zelf aan de winkel vraagt, in ZIJN lus (net als de scan,
    # de afmelding en de bestellingenronde in het echt).
    @app.get("/proef/producten")
    async def _producten():
        c = w.client_uit(db.t["platform_credentials"][0])
        return {"n": len(await c.producten()), "via": type(c.transport).__name__}

    @app.post("/proef/uitverkocht/{pid}")
    async def _uitverkocht(pid: str):
        return {"ok": await w.WooCommercePlatform().delete_listing(pid, db.t["platform_credentials"][0])}

    @app.get("/proef/online")
    async def _online():
        return {"online": wb.online("u1")}

    ons_srv = _start(app, ons)
    yield {"db": db, "winkel": winkel, "verzoeken": verzoeken,
           "winkel_url": f"https://127.0.0.1:{wp}", "ons": f"http://127.0.0.1:{ons}"}
    ons_srv.should_exit = winkel_srv.should_exit = True


def _product(omg, pid):
    if omg["winkel"]:
        return omg["winkel"].producten[int(pid)]
    r = httpx.get(f"{ECHT.rstrip('/')}/wp-json/wc/v3/products/{pid}", auth=(ECHT_CK, ECHT_CS), verify=False)
    return r.json()


def test_koppelen_inlezen_en_afmelden_via_een_echte_browser(omgeving):
    omg = omgeving
    with pw.sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(ignore_https_errors=True)
        pagina = ctx.new_page()
        pagina.goto(omg["ons"] + "/proef")

        # 1. Sleutel plakken, precies wat Toons assistent deed.
        pagina.fill("#woo-store-input", omg["winkel_url"])
        pagina.fill("#woo-ck-input", ECHT_CK)
        pagina.fill("#woo-cs-input", ECHT_CS)
        pagina.evaluate("submitWooKeys()")
        pagina.wait_for_function("window.__gekoppeld !== null || window.__melding.some(m => m[0] === 'fout')",
                                 timeout=60000)
        meldingen = pagina.evaluate("window.__melding")
        assert pagina.evaluate("window.__gekoppeld"), f"niet gekoppeld: {meldingen}"
        assert any("through this browser" in t for _s, t in meldingen)
        rij = omg["db"].t["platform_credentials"][0]
        assert rij["extra_data"]["via_browser"] is True
        assert rij["extra_data"]["api_root"] == omg["winkel_url"] + "/wp-json/"
        # De server zelf kreeg de captcha; alles wat slaagde kwam van de browser.
        assert any(v[2] != "browser" for v in omg["verzoeken"]), "de server probeerde het eerst zelf"

        # 2. Inlezen: de server leest de hele winkel, via de browser.
        r = httpx.get(omg["ons"] + "/proef/producten", timeout=120)
        assert r.json()["via"] == "BrowserTransport"
        if omg["winkel"]:
            assert r.json()["n"] == 230

        # 3. Elders verkocht, browser open: meteen op uitverkocht.
        pid = "5" if omg["winkel"] else str(os.environ["WOO_E2E_PRODUCT_1"])
        assert httpx.post(omg["ons"] + f"/proef/uitverkocht/{pid}", timeout=60).json()["ok"]
        assert _product(omg, pid)["stock_status"] == "outofstock"

        # 4. Webhook staat in de winkel (onderhoud bij het eerste contact).
        if omg["winkel"]:
            for _ in range(50):
                if len(omg["winkel"].webhooks) == 2:
                    break
                time.sleep(0.2)
            assert {h["topic"] for h in omg["winkel"].webhooks} == {"order.created", "order.updated"}

        if not omg["winkel"]:
            hooks = []
            for _ in range(50):
                hooks = httpx.get(f"{ECHT.rstrip('/')}/wp-json/wc/v3/webhooks", auth=(ECHT_CK, ECHT_CS),
                                  verify=False).json()
                if len(hooks) >= 2:
                    break
                time.sleep(0.3)
            assert {h["topic"] for h in hooks} == {"order.created", "order.updated"}, hooks
            assert all(h["status"] == "active" for h in hooks), hooks

        # 5. Browser dicht, elders verkocht: wachtrij. Weer open: gebeurt alsnog.
        pagina.close()
        for _ in range(100):
            if not httpx.get(omg["ons"] + "/proef/online").json()["online"]:
                break
            time.sleep(0.2)
        pid2 = "6" if omg["winkel"] else str(os.environ["WOO_E2E_PRODUCT_2"])
        assert httpx.post(omg["ons"] + f"/proef/uitverkocht/{pid2}", timeout=60).json()["ok"]
        assert rij["extra_data"].get(wb.WACHTRIJ) == [pid2]
        assert _product(omg, pid2)["stock_status"] == "instock"

        pagina = ctx.new_page()
        pagina.goto(omg["ons"] + "/proef")
        pagina.evaluate("wooDoorgeefStart()")
        for _ in range(150):
            if not rij["extra_data"].get(wb.WACHTRIJ):
                break
            time.sleep(0.2)
        assert rij["extra_data"].get(wb.WACHTRIJ) == []
        assert _product(omg, pid2)["stock_status"] == "outofstock"
        browser.close()
