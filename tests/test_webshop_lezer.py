"""Producten lezen uit een JouwWeb-winkel via de openbare pagina (echte pagina van 19-11-2026)."""
from pathlib import Path

import pytest

from backend.platforms.webshop_lezer import WinkelFout, lees_product, normaliseer

PAGINA = (Path(__file__).parent / "fixtures" / "jouwweb_productpagina.html").read_text()
URL = "https://www.brocantedepot.com/product/24969399/aardewerk-vergiet"


def test_echte_productpagina_wordt_gelezen():
    p = lees_product(PAGINA, URL)
    assert p["platform_listing_id"] == "24969399"
    assert p["title"] == "Aardewerk vergiet"
    assert p["price"] == 55.0
    assert p["sku"] == "261109"
    assert p["is_closed"] is False
    assert p["description"] == ("Prachtig vergiet van Frans aardewerk\n"
                                "13 cm hoog, 21 cm doorsnede aan de bovenkant")
    assert len(p["photo_urls"]) == 8 and p["photo_url"] == p["photo_urls"][0]


def test_geen_productpagina_geeft_none():
    assert lees_product("<html><body>Over ons</body></html>", "https://x.nl/over-ons") is None


def test_uitverkocht_wordt_herkend():
    html = PAGINA.replace("schema.org/InStock", "schema.org/OutOfStock")
    assert lees_product(html, URL)["is_closed"] is True


@pytest.mark.parametrize("adres,uit", [("brocantedepot.com", "https://brocantedepot.com"),
                                        ("https://www.x.nl/pad/?a=1", "https://www.x.nl")])
def test_adres_wordt_schoon(adres, uit):
    assert normaliseer(adres) == uit


@pytest.mark.parametrize("slecht", ["", "   ", "geenpunt"])
def test_slecht_adres_geeft_fout(slecht):
    with pytest.raises(WinkelFout):
        normaliseer(slecht)
