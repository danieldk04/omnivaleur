"""Een loafer is een instapper, geen veterschoen — en zeker geen hak.

Daniel, 18-09-2026: "art 1369 zijn loafers maar wordt nu herkend als formal
shoes". Dat artikel (Suitsupply loafers, maat 43) kwam binnen als "heren formele
schoenen". Op Marktplaats maakt dat niets uit, want daar delen alle herenschoenen
categorie 642, maar op Vinted en eBay wel: "heren formele schoenen" zoekt daar op
formal/dress/oxford shoes, terwijl Vinted een eigen rubriek Loafers heeft die
onder "heren schoenen" wordt gezocht.

Bij dames was het erger: loafers gingen naar "hakken". Een loafer heeft geen hak.
"""
import pytest

from backend.api.imports import _TAXONOMY, _infer_attributes


@pytest.mark.parametrize("titel,verwacht", [
    ("(1369) Brown Suitsupply Loafers - Men 43 - Very Good", "heren schoenen"),
    ("Heren penny loafers bruin suède maat 43", "heren schoenen"),
    ("Mocassins heren donkerblauw", "heren schoenen"),
    ("Heren instappers zwart leer", "heren schoenen"),
    ("Boat shoes heren maat 44", "heren schoenen"),
])
def test_herenloafers_gaan_naar_gewone_schoenen(titel, verwacht):
    assert _infer_attributes(titel, "").get("category") == verwacht


@pytest.mark.parametrize("titel", [
    "Dames loafers zwart maat 39",
    "Dames mocassins beige",
])
def test_damesloafers_worden_geen_hakken(titel):
    uit = _infer_attributes(titel, "")
    assert uit.get("category") == "schoenen dames", uit
    assert uit.get("category") != "hakken"


@pytest.mark.parametrize("titel,verwacht", [
    ("Heren oxford veterschoenen zwart maat 43", "heren formele schoenen"),
    ("Brogues heren cognac leer", "heren formele schoenen"),
    ("Derby nette schoen heren", "heren formele schoenen"),
])
def test_echte_nette_schoenen_blijven_formeel(titel, verwacht):
    """De reparatie mag de categorie niet leeghalen: veterschoenen horen er wél."""
    assert _infer_attributes(titel, "").get("category") == verwacht


def test_de_gekozen_sleutels_bestaan_echt():
    """Een sleutel die niet in de taxonomie staat wordt door de extensie niet
    herkend en valt terug op damesjeans."""
    for sleutel in ("heren schoenen", "heren formele schoenen"):
        assert sleutel in _TAXONOMY["heren"], sleutel
    assert "schoenen dames" in _TAXONOMY["dames"]
