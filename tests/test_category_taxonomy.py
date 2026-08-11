"""Elke categorie in het dashboard moet op élk platform een bestemming hebben.

Het dropdown-menu in frontend/app.html is de bron van waarheid. Staat een sleutel
daar wél maar niet in de Marktplaats-map, de Vinted-hints, de eBay-hints of de
import-taxonomie, dan wordt zo'n artikel stil verkeerd geplaatst (Marktplaats valt
terug op damesjeans). Deze test vangt dat af zodra er een categorie bijkomt.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _frontend_categories() -> dict[str, list[str]]:
    src = _read("frontend/app.html")
    start = src.index("const CATEGORIES = {")
    end = src.index("\n};", start)
    block = src[start:end]
    groups: dict[str, list[str]] = {}
    current = None
    for line in block.splitlines():
        m = re.match(r"\s*([a-z]+):\s*\[", line)
        if m:
            current = m.group(1)
            groups[current] = []
        if current:
            groups[current].extend(re.findall(r'\["([^"]+)"\s*,\s*"[^"]*"\]', line))
    return {g: keys for g, keys in groups.items() if keys}


CLOTHING_GROUPS = ("dames", "heren", "kinderen", "unisex")


@pytest.fixture(scope="module")
def categories():
    cats = _frontend_categories()
    assert set(CLOTHING_GROUPS).issubset(cats), cats.keys()
    return cats


@pytest.fixture(scope="module")
def all_keys(categories):
    return [k for keys in categories.values() for k in keys]


def _js_keys(rel: str, marker: str) -> set[str]:
    src = _read(rel)
    start = src.index(marker)
    return set(re.findall(r'^\s*"([^"]+)":', src[start:], flags=re.M))


def test_every_category_has_a_marktplaats_target(all_keys):
    mp = _js_keys("extension/background.js", "const MP_CATEGORIES = {")
    missing = [k for k in all_keys if k not in mp]
    assert not missing, f"geen Marktplaats-categorie voor: {missing}"


def test_every_category_has_vinted_hints(all_keys):
    vinted = _js_keys("extension/content/vinted.js", "const CAT_HINTS = {")
    missing = [k for k in all_keys if k not in vinted]
    assert not missing, f"geen Vinted-hints voor: {missing}"


def test_every_category_has_an_ebay_hint(all_keys):
    ebay = set(re.findall(
        r'"([^"]+)":\s*"',
        _read("backend/platforms/ebay.py").split("_EBAY_CATEGORY_HINTS = {")[1].split("\n}")[0],
    ))
    missing = [k for k in all_keys if k not in ebay]
    assert not missing, f"geen eBay-hint voor: {missing}"


def test_clothing_categories_match_the_import_taxonomy(categories):
    from backend.api.imports import _TAXONOMY

    for group in CLOTHING_GROUPS:
        assert sorted(_TAXONOMY[group]) == sorted(categories[group]), group


def test_every_category_gets_an_english_shopify_type(all_keys):
    from backend.platforms.shopify_importer import _english_type_from_category

    missing = [k for k in all_keys if not _english_type_from_category(k)]
    assert not missing, f"geen Engels producttype voor: {missing}"


@pytest.mark.parametrize("title,expected", [
    ("B'Twin Cycling Suit - Men XL", "heren wielrenkleding"),
    ("Rapha wielrenshirt heren", "heren wielrenkleding"),
    ("Nike trainingspak dames", "trainingspakken"),
    ("Salomon skibroek heren", "heren skikleding"),
    ("Ajax voetbalshirt kinderen", "kinderen voetbalkleding"),
    ("Nike sportshirt kinderen", "kinderen sportkleding"),
    ("Speedo zwembroek men", "heren zwembroeken"),
    ("Levi's 501 jeans men", "heren jeans"),
])
def test_sport_items_are_recognised(title, expected):
    from backend.api.imports import _infer_attributes

    got = _infer_attributes(title, "")
    assert got.get("category") == expected
