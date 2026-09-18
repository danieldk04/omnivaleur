"""Zoeken op SKU moet de héle Shopify-catalogus aflopen, niet de eerste 2.200.

WAAROM DIT ER IS (18-09-2026, gemeten op Daniels winkel).

_find_shopify_product_id_by_sku vraagt 250 producten per pagina op. De
vervolg-URL die Shopify in de Link-kop meegeeft draagt alleen `page_info`, en de
code gooide de rest van de parameters weg. Shopify viel daardoor vanaf pagina 2
terug op zijn standaard van 50 per pagina: veertig rondes haalden 2.200 producten
op in plaats van 10.000, en daarna kwam er "niet gevonden" uit voor een product
dat er wél stond (SKU 1370, aangemaakt om 16:15:48).

Dat antwoord is duur. Het wordt gebruikt om een verkocht artikel uit de winkel te
halen als het productnummer ontbreekt; een verkeerde "niet gevonden" laat het dus
gewoon te koop staan.
"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402


class _Antwoord:
    def __init__(self, producten, volgende=None):
        self._producten = producten
        self.headers = ({"Link": f'<{volgende}>; rel="next"'} if volgende else {})

    def json(self):
        return {"products": self._producten}

    def raise_for_status(self):
        return None


def _nep_shopify(monkeypatch, paginas):
    """paginas: lijst van (producten, volgende_url). Onthoudt elke opgevraagde URL."""
    gevraagd = []

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None, **kw):
            gevraagd.append((url, params))
            producten, volgende = paginas[len(gevraagd) - 1]
            return _Antwoord(producten, volgende)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _Client())
    import backend.config as cfg
    monkeypatch.setattr(cfg.settings, "shopify_store", "test-shop.myshopify.com")

    async def token():
        return "tok"
    import backend.platforms.shopify_importer as si
    monkeypatch.setattr(si, "_get_token", token)
    return gevraagd


def test_de_tweede_pagina_vraagt_opnieuw_250_producten(monkeypatch):
    volgende = ("https://test-shop.myshopify.com/admin/api/2024-10/products.json"
                "?page_info=xyz123")
    gevraagd = _nep_shopify(monkeypatch, [
        ([{"id": 1, "variants": [{"sku": "0001"}]}], volgende),
        ([{"id": 2, "variants": [{"sku": "1370"}]}], None),
    ])

    gevonden = asyncio.run(cl._find_shopify_product_id_by_sku("1370"))

    assert gevonden == "2"
    tweede_url = gevraagd[1][0]
    q = parse_qs(urlparse(tweede_url).query)
    assert q["page_info"] == ["xyz123"], "de cursor moet mee"
    assert q["limit"] == ["250"], "zonder limit valt Shopify terug op 50 per pagina"


def test_zonder_volgende_pagina_stopt_het_gewoon(monkeypatch):
    _nep_shopify(monkeypatch, [([{"id": 1, "variants": [{"sku": "0001"}]}], None)])

    assert asyncio.run(cl._find_shopify_product_id_by_sku("1370")) is None
