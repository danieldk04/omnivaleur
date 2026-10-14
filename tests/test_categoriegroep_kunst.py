"""Kunstrubrieken vielen in het beheeroverzicht onder "Kleding" (Delftsblaeu, 14-10-2026:
278 etsen en gravures telden als kleding)."""
from backend.api.beheer import _categoriegroep


def test_kunst_is_geen_kleding():
    assert _categoriegroep("kunst etsen en gravures") == "Kunst"
    assert _categoriegroep("kunst schilderijen modern") == "Kunst"


def test_kleding_blijft_kleding():
    assert _categoriegroep("heren t-shirts") == "Kleding"
