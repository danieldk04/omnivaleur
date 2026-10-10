"""WooCommerce: het API-adres van een winkel vinden (ontdek_api), en eerlijk zeggen
waarom het niet lukt.

WAAROM (10-10-2026, De Juiste Toon). Toon kreeg bij het koppelen van
dejuistetoon.eu: "doesn't look like a WordPress site". Zijn winkel IS WordPress
met WooCommerce (gemeten vanaf GitHub: Link-kop, /wp-json/ met wc/v3, en een
WooCommerce-401 op /wp-json/wc/v3/products). Hij draait op SiteGround, en
SiteGround's anti-bot geeft een verdacht IP HTTP 202 met een captcha-pagina in
plaats van de site. De oude code zag in een 202 geen fout en las de captcha als
"geen WordPress". De antwoorden hieronder zijn de echte kopregels van zijn winkel.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.platforms import woocommerce as w  # noqa: E402

DJT = "https://dejuistetoon.eu"
LINK = '<https://dejuistetoon.eu/wp-json/>; rel="https://api.w.org/"'
SG_KOP = {"server": "nginx", "x-httpd-modphp": "1", "x-proxy-cache": "MISS",
          "content-type": "text/html; charset=UTF-8"}
WP_HTML = ('<!DOCTYPE html><html lang="nl-NL"><head><title>DJT De Juiste Toon</title>'
           "<link rel='https://api.w.org/' href='https://dejuistetoon.eu/wp-json/' />"
           '<link rel="stylesheet" href="https://dejuistetoon.eu/wp-content/plugins/woocommerce/x.css">'
           "</head><body class=\"woocommerce-no-js\"></body></html>")
WP_INDEX = ('{"name":"DJT De Juiste Toon","url":"https:\\/\\/dejuistetoon.eu",'
            '"namespaces":["oembed\\/1.0","sg-security\\/v1","wc\\/v3","wc\\/v1"]}')
# Zo antwoordt SiteGround een IP dat zijn anti-bot niet vertrouwt.
SG_CAPTCHA = ('<html><head><link rel="icon" href="data:;"><meta http-equiv="refresh" '
              'content="0;/.well-known/sgcaptcha/?r=%2F&y=ipr:34.1.2.3:1791641104.000">'
              "</meta></head></html>")


def _ontdek(handler, adres=DJT):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                     follow_redirects=True) as c:
            return await w.ontdek_api(adres, client=c)
    return asyncio.run(go())


@pytest.fixture(autouse=True)
def _geen_wachten(monkeypatch):
    async def _slaap(_s): return None
    monkeypatch.setattr(w.asyncio, "sleep", _slaap)


def test_de_juiste_toon_zoals_github_hem_zag():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(200, headers={**SG_KOP, "link": LINK},
                                  text="" if req.method == "HEAD" else WP_HTML)
        return httpx.Response(404)
    assert _ontdek(h) == "https://dejuistetoon.eu/wp-json/"


def test_siteground_botcontrole_heet_geen_geen_wordpress():
    """De fout van Toon: overal 202 + captcha. Moet 'geblokkeerd' zijn, met SiteGround erbij."""
    def h(req):
        return httpx.Response(202, headers={**SG_KOP, "sg-captcha": "challenge"},
                              text="" if req.method == "HEAD" else SG_CAPTCHA)
    with pytest.raises(w.WooFout) as e:
        _ontdek(h)
    assert e.value.soort == "geblokkeerd"
    assert "SiteGround" in str(e.value)
    assert "WordPress site" not in str(e.value)
    assert "202" in e.value.detail and "sg-captcha=challenge" in e.value.detail


def test_siteground_captcha_ook_zonder_kopregel_herkend():
    def h(req):
        return httpx.Response(202, headers=SG_KOP, text="" if req.method == "HEAD" else SG_CAPTCHA)
    with pytest.raises(w.WooFout) as e:
        _ontdek(h)
    assert e.value.soort == "geblokkeerd" and "SiteGround" in str(e.value)


def test_link_kop_weg_dan_uit_de_html():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(200, headers=SG_KOP, text="" if req.method == "HEAD" else WP_HTML)
        return httpx.Response(404)
    assert _ontdek(h) == "https://dejuistetoon.eu/wp-json/"


def test_api_dicht_voor_bezoekers_is_toch_wordpress():
    """Een plugin die de REST API voor bezoekers dichtzet: 401 rest_login_required."""
    def h(req):
        if req.url.path == "/wp-json/":
            return httpx.Response(401, json={"code": "rest_login_required", "message": "x",
                                             "data": {"status": 401}})
        return httpx.Response(200, headers={"content-type": "text/html"},
                              text="<html><body>gewone pagina zonder sporen</body></html>")
    assert _ontdek(h) == DJT + "/wp-json/"


def test_index_zonder_link_kop_maar_met_namespaces():
    def h(req):
        if req.url.path == "/wp-json/":
            return httpx.Response(200, headers={"content-type": "application/json"}, text=WP_INDEX)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")
    assert _ontdek(h) == DJT + "/wp-json/"


def test_echte_niet_wordpress_site_blijft_geen_wordpress():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(200, headers={"content-type": "text/html"},
                                  text="<html><head><script src='//cdn.shopify.com/x.js'></script></head></html>")
        return httpx.Response(404, headers={"content-type": "text/html"}, text="<html>404</html>")
    with pytest.raises(w.WooFout) as e:
        _ontdek(h, "https://eenshopifywinkel.nl")
    assert e.value.soort == "geen_wordpress"


def test_wordpress_met_verborgen_api_zegt_dat():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(200, headers={"content-type": "text/html"},
                                  text=WP_HTML.replace("rel='https://api.w.org/'", "rel='x'"))
        return httpx.Response(404, headers={"content-type": "text/html"}, text="<html>404</html>")
    with pytest.raises(w.WooFout) as e:
        _ontdek(h)
    assert e.value.soort == "geen_woo_api"


def test_storing_eerst_opnieuw_proberen():
    tel = {"get": 0}

    def h(req):
        if req.url.path == "/" and req.method == "GET":
            tel["get"] += 1
            if tel["get"] == 1:
                return httpx.Response(503, headers={"content-type": "text/html"}, text="druk")
        if req.url.path == "/":
            return httpx.Response(200, headers={**SG_KOP, "link": LINK},
                                  text="" if req.method == "HEAD" else WP_HTML)
        return httpx.Response(404)
    assert _ontdek(h) == "https://dejuistetoon.eu/wp-json/"


def test_blijvende_storing_heet_storing():
    def h(req):
        return httpx.Response(500, headers={"content-type": "text/html"}, text="<html>Fatal</html>")
    with pytest.raises(w.WooFout) as e:
        _ontdek(h)
    assert e.value.soort == "serverfout" and e.value.status == 500


def test_cloudflare_uitdaging_heet_cloudflare():
    def h(req):
        return httpx.Response(403, headers={"server": "cloudflare", "cf-ray": "1",
                                            "cf-mitigated": "challenge", "content-type": "text/html"},
                              text="<title>Just a moment...</title>")
    with pytest.raises(w.WooFout) as e:
        _ontdek(h)
    assert e.value.soort == "geblokkeerd" and "Cloudflare" in str(e.value)


def test_api_verzoek_met_siteground_captcha_heet_geblokkeerd():
    """Na het koppelen (sleutelcontrole, bestellingen): 202 is geen antwoord."""
    def h(req):
        return httpx.Response(202, headers={**SG_KOP, "sg-captcha": "challenge"}, text=SG_CAPTCHA)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
            return await w.WooClient(DJT + "/wp-json/", "ck_x", "cs_y").verzoek(
                "GET", "wc/v3/products", {"per_page": 1}, client=c)
    with pytest.raises(w.WooFout) as e:
        asyncio.run(go())
    assert e.value.soort == "geblokkeerd" and "SiteGround" in str(e.value)
    assert "cs_y" not in e.value.detail, "het geheim mag nooit in de mail"


def test_mail_aan_daniel_bevat_wat_de_winkel_antwoordde(monkeypatch):
    from backend.api import platforms as api
    from backend.services import email as mail
    from backend.services import referral_mail

    verstuurd = {}
    monkeypatch.setattr(mail, "send_email", lambda subject, body: verstuurd.update(s=subject, b=body) or True)
    monkeypatch.setattr(referral_mail, "email_van", lambda _u: "djt@dejuistetoon.eu")
    api._WOO_ALARM_SINDS.clear()
    fout = w.WooFout(w.SITEGROUND_MELDING, "geblokkeerd", 202,
                     detail="GET https://dejuistetoon.eu/ -> 202 sg-captcha=challenge")
    assert api._meld_mislukte_woo_koppeling("u1", DJT, fout)
    assert "Soort fout: geblokkeerd" in verstuurd["b"]
    assert "sg-captcha=challenge" in verstuurd["b"]
