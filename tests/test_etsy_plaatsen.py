"""De Etsy-plaatsstroom tegen een nagebootste Etsy (geen echt verkeer)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.config import settings
from backend.platforms import etsy


@pytest.fixture(autouse=True)
def sleutels(monkeypatch):
    monkeypatch.setattr(settings, "etsy_api_keystring", "ks")
    monkeypatch.setattr(settings, "etsy_shared_secret", "sec")
    etsy._taxonomie_cache.update({"tot": 0.0, "bladeren": []})


def test_jaar_uit_titel_en_decennium():
    assert etsy.jaar_uit_item({"title": "Vintage 1992 jas"}) == 1992
    assert etsy.jaar_uit_item({"title": "mooie 80s jacket"}) == 1985
    assert etsy.jaar_uit_item({"title": "jaren 70 vest"}) == 1975
    assert etsy.jaar_uit_item({"title": "Ralph Lauren vest", "description": "bijna nieuw 2019"}) is None
    assert etsy.jaar_uit_item({"title": "x", "year": 1988}) == 1988


def test_taxonomie_kiest_passend_blad():
    bladen = [(1, ("Clothing", "Men's Clothing", "Jackets & Coats")),
              (2, ("Clothing", "Women's Clothing", "Jackets & Coats")),
              (3, ("Bags & Purses", "Backpacks"))]
    assert etsy.kies_taxonomie(bladen, {"title": "Zip vest", "category": "jas", "gender": "heren"}) == 1
    assert etsy.kies_taxonomie(bladen, {"title": "Zip vest", "category": "jas", "gender": "dames"}) == 2
    assert etsy.kies_taxonomie(bladen, {"title": "iets raars", "category": "xyz"}) is None


def _nep_etsy(calls):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p, m = req.url.path, req.method
        if not p.startswith("/photos"):
            assert req.headers["x-api-key"] == "ks:sec"
        if p.endswith("/seller-taxonomy/nodes"):
            return httpx.Response(200, json={"results": [
                {"id": 10, "name": "Clothing", "children": [
                    {"id": 11, "name": "Men's Clothing", "children": [{"id": 12, "name": "Jackets & Coats", "children": []}]}]}]})
        if "/users/" in p and p.endswith("/shops"):
            return httpx.Response(200, json={"shop_id": 99})
        if p.endswith("/shipping-profiles") and m == "GET":
            return httpx.Response(200, json={"results": [{"shipping_profile_id": 5}]})
        if p.endswith("/readiness-state-definitions") and m == "GET":
            return httpx.Response(200, json={"results": [{"readiness_state_id": 6}]})
        if p.endswith("/shops/99/listings") and m == "POST":
            return httpx.Response(201, json={"listing_id": 777})
        if p.endswith("/policies/return") and m == "GET":
            return httpx.Response(200, json={"results": [{"return_policy_id": 8}]})
        if p.endswith("/images"):
            return httpx.Response(201, json={})
        if p.endswith("/listings/777") and m == "PATCH":
            return httpx.Response(200, json={"state": "active"})
        if m == "GET" and p.startswith("/photos"):
            return httpx.Response(200, content=b"jpg")
        return httpx.Response(404, json={})
    return handler


def _creds():
    return {"access_token": "123.abc", "refresh_token": "r",
            "token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}


def _patch_http(monkeypatch, calls):
    echt = httpx.AsyncClient
    monkeypatch.setattr(etsy.httpx, "AsyncClient",
                        lambda **kw: echt(transport=httpx.MockTransport(_nep_etsy(calls)), **kw))


ITEM = {"title": "Vintage 1990 jas", "price": 20, "category": "jas", "gender": "heren",
        "description": "mooi", "photo_urls": ["https://x.test/photos/1.jpg"]}


def test_plaatsen_activeert_na_foto_en_retourbeleid(monkeypatch):
    calls = []
    _patch_http(monkeypatch, calls)
    res = asyncio.run(etsy.EtsyPlatform().create_listing(dict(ITEM), _creds()))
    assert res["state"] == "active" and res["platform_listing_id"] == "777"
    volgorde = [c for c in calls if c[0] in ("POST", "PATCH")]
    assert volgorde[0][1].endswith("/shops/99/listings")
    assert volgorde[-1] == ("PATCH", "/v3/application/shops/99/listings/777")


def test_jonger_dan_20_jaar_wordt_geweigerd_zonder_etsy_aan_te_raken(monkeypatch):
    calls = []
    _patch_http(monkeypatch, calls)
    with pytest.raises(ValueError):
        asyncio.run(etsy.EtsyPlatform().create_listing({**ITEM, "title": "Jas 2019"}, _creds()))
    assert not [c for c in calls if c[0] == "POST"]


def test_zonder_foto_geen_listing(monkeypatch):
    calls = []
    _patch_http(monkeypatch, calls)
    with pytest.raises(RuntimeError):
        asyncio.run(etsy.EtsyPlatform().create_listing({**ITEM, "photo_urls": []}, _creds()))
    assert not [c for c in calls if c[0] == "POST"]


def test_geen_koppeling_geeft_duidelijke_fout():
    with pytest.raises(RuntimeError, match="isn't connected"):
        asyncio.run(etsy.EtsyPlatform().create_listing(dict(ITEM), {}))


def test_toegang_alleen_ultra_of_eigenaar(monkeypatch):
    from backend.services import etsy_toegang as t
    t._cache.clear()
    monkeypatch.setattr(settings, "etsy_open_voor_ultra", True)
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: "klant@x.nl")
    monkeypatch.setattr("backend.services.billing.is_owner_email", lambda e: e == "eigenaar@x.nl")
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "plus")
    assert t.etsy_toegang("u1") is False
    t._cache.clear()
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "ultra")
    assert t.etsy_toegang("u1") is True
    t._cache.clear()
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: "eigenaar@x.nl")
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "light")
    assert t.etsy_toegang("u2") is True


def test_jaarveld_gaat_voor_tekst_en_toegang_is_standaard_alleen_eigenaar(monkeypatch):
    assert etsy.jaar_uit_item({"title": "jas 1999", "vintage_year": 1975}) == 1975
    from backend.services import etsy_toegang as t
    t._cache.clear()
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: "klant@x.nl")
    monkeypatch.setattr("backend.services.billing.is_owner_email", lambda e: False)
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "ultra")
    assert settings.etsy_open_voor_ultra is False
    assert t.etsy_toegang("ultra-klant") is False


def test_titel_begint_met_letter_of_cijfer():
    assert etsy.etsy_titel("(1029) White Ralph Lauren Hoodie - Men XL - Very Good") == "White Ralph Lauren Hoodie - Men XL - Very Good"
    assert etsy.etsy_titel("  *** Vintage jas ") == "Vintage jas"
    assert etsy.etsy_titel("501 Levi's") == "501 Levi's"
    assert len(etsy.etsy_titel("woord " * 60)) <= 140


def test_titel_wordt_schoon_verstuurd(monkeypatch):
    calls = []
    verzonden = {}
    handler = _nep_etsy(calls)

    def vang(req):
        if req.method == "POST" and req.url.path.endswith("/shops/99/listings"):
            verzonden["body"] = req.content.decode()
        return handler(req)

    echt = httpx.AsyncClient
    monkeypatch.setattr(etsy.httpx, "AsyncClient", lambda **kw: echt(transport=httpx.MockTransport(vang), **kw))
    asyncio.run(etsy.EtsyPlatform().create_listing({**ITEM, "title": "(1029) Vintage 1990 jas"}, _creds()))
    assert "title=Vintage+1990+jas" in verzonden["body"]


def test_testverkoper_krijgt_etsy_zonder_plan(monkeypatch):
    from backend.services import etsy_toegang as t
    t._cache.clear()
    monkeypatch.setattr(settings, "etsy_open_voor_ultra", False)
    monkeypatch.setattr(settings, "etsy_testgebruikers", "Test@Winkel.nl, ander@x.nl")
    monkeypatch.setattr("backend.services.billing.is_owner_email", lambda e: False)
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "light")
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: " test@winkel.nl ")
    assert t.etsy_toegang("tester") is True
    t._cache.clear()
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: "iemand@x.nl")
    assert t.etsy_toegang("iemand") is False
