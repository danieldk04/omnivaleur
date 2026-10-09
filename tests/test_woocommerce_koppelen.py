"""WooCommerce koppelen met één klik: wat de WINKEL naar /woocommerce/callback stuurt.

De vorm komt uit WooCommerce 11.2 zelf (includes/class-wc-auth.php,
post_consumer_data): JSON met key_id, user_id (onze getekende staat),
consumer_key, consumer_secret en key_permissions, Content-Type
'application/json;charset=UTF-8'. Alles behalve precies 200 laat WooCommerce de
sleutel weer wissen en de verkoper een foutmelding zien.
"""
import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import platforms as api  # noqa: E402
from backend.platforms import woocommerce as w  # noqa: E402
from tests.test_woocommerce import _DB  # noqa: E402

API_ROOT = "https://mikkis.nl/wp-json/"


def _app():
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    return TestClient(app)


def _post(client, staat, ck="ck_" + "a" * 40, cs="cs_" + "b" * 40):
    import json
    return client.post("/api/platforms/woocommerce/callback",
                       content=json.dumps({"key_id": 7, "user_id": staat, "consumer_key": ck,
                                           "consumer_secret": cs, "key_permissions": "read_write"}),
                       headers={"Content-Type": "application/json;charset=UTF-8"})


def test_geldige_staat_geeft_200_en_controleert_de_sleutel(monkeypatch):
    gezien = []

    async def _controle(user_id, api_root, ck, cs): gezien.append((user_id, api_root, ck[:3], cs[:3]))
    monkeypatch.setattr(api, "_woo_controleer_en_bewaar", _controle)
    r = _post(_app(), w.maak_staat("user-1", API_ROOT))
    assert r.status_code == 200
    assert gezien == [("user-1", API_ROOT, "ck_", "cs_")]


def test_vervalste_of_verlopen_staat_wordt_geweigerd(monkeypatch):
    gezien = []

    async def _controle(*a): gezien.append(a)
    monkeypatch.setattr(api, "_woo_controleer_en_bewaar", _controle)
    c = _app()
    assert _post(c, "verzonnen.staat").status_code == 403
    oud = w.maak_staat("user-1", API_ROOT, nu=1)
    assert _post(c, oud).status_code == 403
    assert _post(c, w.maak_staat("user-1", API_ROOT), ck="geen-sleutel").status_code == 403
    assert gezien == [], "zonder geldige staat wordt er niets bewaard"


def test_bewaren_houdt_voorraadvlag_bij_dezelfde_winkel(monkeypatch):
    db = _DB(platform_credentials=[{"user_id": "u1", "platform": "woocommerce",
                                    "extra_data": {"api_root": API_ROOT, "voorraad_meerdere": True,
                                                   "orders_gezien_tot": "x", "verkoop_fout": {"r": 1}}}])
    bewaard = {}

    def _save(user_id, platform, tokens): bewaard.update(tokens)
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "_save_credentials", _save)
    api._bewaar_woo("u1", "ck_1", "cs_1", {"api_root": API_ROOT, "site": "https://mikkis.nl",
                                            "modus": "query"}, "knop")
    e = bewaard["extra_data"]
    assert bewaard["access_token"] == "ck_1" and bewaard["refresh_token"] == "cs_1"
    assert e["voorraad_meerdere"] is True and e["orders_gezien_tot"] == "x" and e["modus"] == "query"
    assert "verkoop_fout" not in e, "een nieuwe sleutel begint zonder oude storing"


def test_andere_winkel_begint_schoon(monkeypatch):
    db = _DB(platform_credentials=[{"user_id": "u1", "platform": "woocommerce",
                                    "extra_data": {"api_root": API_ROOT, "voorraad_meerdere": True}}])
    bewaard = {}
    monkeypatch.setattr(api, "get_db", lambda: db)
    monkeypatch.setattr(api, "_save_credentials", lambda u, p, t: bewaard.update(t))
    api._bewaar_woo("u1", "ck_1", "cs_1", {"api_root": "https://ander.nl/wp-json/",
                                            "site": "https://ander.nl", "modus": "basic"}, "sleutel")
    assert "voorraad_meerdere" not in bewaard["extra_data"]


def test_controle_na_de_knop_onthoudt_waarom_het_mislukte(monkeypatch):
    async def _weigert(*a): raise w.WooFout("WooCommerce did not accept the key.", "sleutel")
    monkeypatch.setattr(w, "controleer_sleutels", _weigert)
    monkeypatch.setattr(api, "_meld_mislukte_woo_koppeling", lambda *a: False)
    asyncio.run(api._woo_controleer_en_bewaar("u9", API_ROOT, "ck_x", "cs_x"))
    assert api._woo_mislukt["u9"] == "WooCommerce did not accept the key."
