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


def test_kralenarmband_wordt_geen_blanco_armband():
    bladen = [(1, ("Craft Supplies & Tools", "Jewelry Making", "Bracelet Blanks")),
              (2, ("Jewelry", "Bracelets", "Chain Bracelets")),
              (3, ("Jewelry", "Bracelets", "Beaded Bracelets")),
              (4, ("Jewelry", "Necklaces", "Beaded Necklaces"))]
    item = {"title": "Vintage 2-strand blood coral bracelet with gold clasp", "category": "Armbanden",
            "material": "bloedkoraal, goud"}
    assert etsy.kies_taxonomie(bladen, item) == 3


def test_sectie_antiek_of_vintage_naar_soort():
    secties = [{"shop_section_id": 1, "title": "Armbanden"}, {"shop_section_id": 2, "title": "Antieke Armbanden"},
               {"shop_section_id": 3, "title": "Vintage Armbanden"}, {"shop_section_id": 4, "title": "Vintage Kettingen"}]
    it = {"title": "Bloedkoraal bracelet", "category": "Armbanden"}
    assert etsy.kies_sectie(secties, it, 1980) == 3
    assert etsy.kies_sectie(secties, it, 1900) == 2
    assert etsy.kies_sectie(secties, {"title": "Vintage ring", "category": "ringen"}, 1980) is None


def test_tags_en_materialen_zijn_etsy_proof():
    assert etsy._etsy_woorden(["Antieke Armband!", "x" * 25, "antieke armband", "14k goud"], 13, 20) == ["antieke armband", "14k goud"]


def test_plaatsen_met_sku_vertaling_rank_en_zonder_slottekst(monkeypatch):
    calls, bodies = [], {}
    handler = _nep_etsy(calls)

    def vang(req):
        p, m = req.url.path, req.method
        if p == "/v3/application/shops/99" and m == "GET":
            return httpx.Response(200, json={"languages": ["nl", "en"]})
        if p.endswith("/sections"):
            return httpx.Response(200, json={"results": [{"shop_section_id": 31, "title": "Vintage Armbanden"}]})
        if p.endswith("/inventory") and m == "GET":
            return httpx.Response(200, json={"products": [{"offerings": [{"price": {"amount": 2500, "divisor": 100}, "quantity": 1}]}]})
        if p.endswith("/inventory") and m == "PUT":
            bodies["inv"] = json.loads(req.content)
            return httpx.Response(200, json={})
        if "/translations/" in p:
            bodies["vert"] = (p, req.content.decode())
            return httpx.Response(201, json={})
        if p.endswith("/shops/99/listings") and m == "POST":
            bodies["lst"] = req.content.decode()
        if p.endswith("/images"):
            bodies.setdefault("img", []).append(req.content)
        return handler(req)

    echt = httpx.AsyncClient
    monkeypatch.setattr(etsy.httpx, "AsyncClient", lambda **kw: echt(transport=httpx.MockTransport(vang), **kw))
    monkeypatch.setattr(etsy, "genereer_etsy_velden", lambda i, t: {
        "tags": {x: ["vintage"] for x in t}, "materials": ["goud"], "alt_text": {x: "alt " + x for x in t}})
    item = {**ITEM, "sku": "24-027.12", "price_markup_pct": 25, "category": "Armbanden", "title": "Vintage 1990 armband",
            "_etsy_teksten": {"nl": {"title": "Armband NL", "description": "nl tekst"},
                              "en": {"title": "Bracelet EN", "description": "en text"}}}
    item["title"] = "Vintage 1990 jas"; item["category"] = "jas"
    res = asyncio.run(etsy.EtsyPlatform().create_listing(item, _creds()))
    assert res["state"] == "active"
    assert "title=Armband+NL" in bodies["lst"] and "price=25.0" in bodies["lst"] and "should_auto_renew=true" in bodies["lst"]
    assert "shop_section_id" not in bodies["lst"]  # jas: geen sectiematch
    assert bodies["inv"]["products"][0]["sku"] == "24-027.12"
    assert bodies["inv"]["products"][0]["offerings"][0]["readiness_state_id"] == 6
    assert bodies["vert"][0].endswith("/translations/en") and "Bracelet+EN" in bodies["vert"][1]
    assert b'name="rank"' in bodies["img"][0] and b"alt nl" in bodies["img"][0]


def test_materialen_zonder_koppelteken_tags_met():
    assert etsy._etsy_woorden(["rose-goud", "14k"], 13, 45, koppelteken=False) == ["rose goud", "14k"]
    assert etsy._etsy_woorden(["rose-goud"], 13, 20) == ["rose-goud"]


def test_vertaling_valt_terug_op_winkelcode_en_us(monkeypatch):
    calls, gezien = [], []
    handler = _nep_etsy(calls)

    def vang(req):
        p, m = req.url.path, req.method
        if p == "/v3/application/shops/99" and m == "GET":
            return httpx.Response(200, json={"languages": ["nl", "en-US"]})
        if "/translations/" in p:
            gezien.append(p.rsplit("/", 1)[1])
            return httpx.Response(400 if p.endswith("/en") else 201, json={"error": "x"})
        return handler(req)

    echt = httpx.AsyncClient
    monkeypatch.setattr(etsy.httpx, "AsyncClient", lambda **kw: echt(transport=httpx.MockTransport(vang), **kw))
    monkeypatch.setattr(etsy, "genereer_etsy_velden", lambda i, t: {"tags": {x: [] for x in t}, "materials": [], "alt_text": {}})
    item = {**ITEM, "_etsy_teksten": {"nl": {"title": "NL", "description": "n"}, "en": {"title": "EN", "description": "e"}}}
    res = asyncio.run(etsy.EtsyPlatform().create_listing(item, _creds()))
    assert gezien == ["en", "en-US"] and "waarschuwingen" not in res


def test_drie_betalende_vrienden_geven_etsy_zonder_ultra(monkeypatch):
    from backend.services import etsy_toegang as t
    monkeypatch.setattr(settings, "etsy_open_voor_ultra", True)
    monkeypatch.setattr("backend.services.referral_mail.email_van", lambda u: "klant@x.nl")
    monkeypatch.setattr("backend.services.billing.is_owner_email", lambda e: False)
    monkeypatch.setattr("backend.services.light.plan_van_gebruiker", lambda u: "pro")
    for n, verwacht in ((2, False), (3, True), (5, True)):
        t._cache.clear()
        monkeypatch.setattr("backend.services.vriendenvoordeel.betalende_vrienden", lambda u, n=n: n)
        assert t.etsy_toegang("u1") is verwacht
    # Etsy zelf blijft dicht zolang de vlag uit staat, ook met genoeg vrienden.
    t._cache.clear()
    monkeypatch.setattr(settings, "etsy_open_voor_ultra", False)
    assert t.etsy_toegang("u1") is False
