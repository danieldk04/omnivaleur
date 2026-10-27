"""Voordeelsieraden (Mieneke, 27-10-2026): "de import heeft de artikelnummers
vanuit Shopify niet meegenomen".

Nagemeten: 536 Shopify-producten kwamen als nieuw artikel binnen, alle 536 met een
eigen IMP-nummer, terwijl elk product in Shopify een eigen nummer ("25-013.41")
droeg. De scan las dat nummer wel (en koppelde er 769 bestaande artikelen mee),
maar de tabel met kandidaten heeft er geen kolom voor, dus bij het importeren was
het weg. Nu wordt het bij het importeren bij Shopify opgehaald.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import imports as imp  # noqa: E402


class _Q:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, _):
        return lambda *a, **k: self

    def execute(self):
        return self


class _DB:
    def __init__(self, bezet):
        self.bezet = bezet

    def table(self, naam):
        if naam == "platform_credentials":
            return _Q([{"user_id": "u1", "access_token": "t", "extra_data": {}}])
        return _Q([{"sku": s} for s in self.bezet])


class _Antwoord:
    def __init__(self, producten):
        self.producten = producten
        self.headers = {}

    def raise_for_status(self):
        pass

    def json(self):
        return {"products": self.producten}


def _zet_shopify(monkeypatch, producten):
    import httpx
    from backend.platforms import shopify

    async def creds(_):
        return "winkel.myshopify.com", "tok"

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, *a, **k):
            return _Antwoord(producten)

    monkeypatch.setattr(shopify, "_shop_creds", creds)
    monkeypatch.setattr(httpx, "AsyncClient", Client)


def _kand(pid):
    return {"platform": "shopify", "platform_listing_id": pid, "title": f"Ring {pid}", "price": 10}


def _prod(pid, sku):
    return {"id": int(pid), "variants": [{"sku": sku}]}


def test_item_neemt_het_nummer_van_de_kandidaat_over():
    c = {**_kand("1"), "sku": "25-013.41"}
    assert imp._item_data_from_candidate(c)["sku"] == "25-013.41"
    assert imp._item_data_from_candidate(_kand("1"))["sku"] is None


def test_nummer_wordt_bij_shopify_opgehaald(monkeypatch):
    _zet_shopify(monkeypatch, [_prod("1", "25-013.41"), _prod("2", "24-004.9")])
    cands = [_kand("1"), _kand("2")]
    asyncio.run(imp.shopify_nummers_aanvullen(_DB([]), "u1", cands))
    assert [imp._item_data_from_candidate(c)["sku"] for c in cands] == ["25-013.41", "24-004.9"]


def test_bezet_of_dubbel_nummer_blijft_een_imp_nummer(monkeypatch):
    _zet_shopify(monkeypatch, [_prod("1", "A-1"), _prod("2", "B-2"), _prod("3", "B-2")])
    cands = [_kand("1"), _kand("2"), _kand("3")]
    asyncio.run(imp.shopify_nummers_aanvullen(_DB(["A-1"]), "u1", cands))
    assert [c.get("sku") for c in cands] == [None, None, None]


def test_storing_bij_shopify_laat_de_import_doorgaan(monkeypatch):
    from backend.platforms import shopify

    async def stuk(_):
        raise RuntimeError("shopify plat")

    monkeypatch.setattr(shopify, "_shop_creds", stuk)
    c = _kand("1")
    asyncio.run(imp.shopify_nummers_aanvullen(_DB([]), "u1", [c]))
    assert c.get("sku") is None
