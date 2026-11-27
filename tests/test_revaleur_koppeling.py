"""Omnivaleur-kant van de Revaleur-koppeling: alleen een ondertekende verkoopmelding, op artikelnummer."""
import asyncio
import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from backend.api import revaleur_koppeling as k


def _req(body, geheim="g", kopgeheim=None):
    sig = hmac.new((kopgeheim or geheim).encode(), body, hashlib.sha256).hexdigest()

    class R:
        headers = {"X-Revaleur-Signature": sig}
        async def body(self): return body
    return R()


class _Db:
    def __init__(self, rijen): self.rijen = rijen; self.filt = {}
    def table(self, _): return self
    def select(self, *_): return self
    def eq(self, k_, v): self.filt[k_] = v; return self
    def limit(self, _): return self
    def execute(self): return SimpleNamespace(data=[r for r in self.rijen if all(r.get(a) == b for a, b in self.filt.items())])


@pytest.fixture
def opzet(monkeypatch):
    monkeypatch.setattr(k.settings, "revaleur_koppeling_geheim", "g")
    monkeypatch.setattr(k, "get_db", lambda: _Db([{"id": "item-1", "sku": "42", "user_id": k.settings.revaleur_user_id}]))
    verkocht = []

    async def sold(item_id, platform, sold_price=None, bewijs=None, **kw): verkocht.append((item_id, platform, sold_price, bewijs))
    monkeypatch.setattr(k, "handle_item_sold", sold)
    return verkocht


def test_geldige_melding_meldt_artikel_af(opzet):
    body = json.dumps({"sku": "42", "bestelling": 1001, "prijs": 30}).encode()
    assert asyncio.run(k.verkocht(_req(body))) == {"gevonden": True}
    assert opzet == [("item-1", "revaleur", 30, "bestelling")]


def test_verkeerde_handtekening_doet_niets(opzet):
    body = json.dumps({"sku": "42"}).encode()
    with pytest.raises(k.HTTPException) as e:
        asyncio.run(k.verkocht(_req(body, kopgeheim="fout")))
    assert e.value.status_code == 401 and opzet == []


def test_zonder_geheim_wordt_alles_geweigerd(opzet, monkeypatch):
    monkeypatch.setattr(k.settings, "revaleur_koppeling_geheim", "")
    with pytest.raises(k.HTTPException):
        asyncio.run(k.verkocht(_req(b'{"sku":"42"}', geheim="")))
    assert opzet == []


def test_onbekende_sku_geeft_geen_fout_terug_en_boekt_niets(opzet):
    assert asyncio.run(k.verkocht(_req(json.dumps({"sku": "nope"}).encode()))) == {"gevonden": False}
    assert opzet == []


def test_verkoop_elders_wordt_aan_revaleur_gemeld_op_sku(monkeypatch):
    monkeypatch.setattr(k.settings, "revaleur_koppeling_geheim", "g")
    monkeypatch.setattr(k.settings, "revaleur_api_url", "https://api.revaleur.test")
    posts = []

    class C:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, content=None, headers=None):
            posts.append((url, content, headers)); return SimpleNamespace(status_code=200)
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", C)
    db = _Db([{"id": "item-1", "sku": "42", "user_id": k.settings.revaleur_user_id},
              {"id": "item-2", "sku": "7", "user_id": "iemand-anders"}])
    assert asyncio.run(k.meld_aan_revaleur(db, "item-1", "marktplaats")) is True
    url, body, kop = posts[0]
    assert url == "https://api.revaleur.test/api/revaleur/koppeling/afmelden" and json.loads(body) == {"sku": "42"}
    assert kop["X-Revaleur-Signature"] == hmac.new(b"g", body, hashlib.sha256).hexdigest()
    assert asyncio.run(k.meld_aan_revaleur(_Db(db.rijen), "item-2", "vinted")) is False      # niet van Revaleur
    assert asyncio.run(k.meld_aan_revaleur(_Db(db.rijen), "item-1", "revaleur")) is False    # komt van Revaleur zelf
    assert len(posts) == 1
    monkeypatch.setattr(k.settings, "revaleur_api_url", "")
    assert asyncio.run(k.meld_aan_revaleur(_Db(db.rijen), "item-1", "vinted")) is False      # niet ingesteld = stil
