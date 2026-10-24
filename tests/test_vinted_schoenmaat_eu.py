"""Kinderschoenen op Vinted: de opdracht draagt de maat als "EU 26" (24-10-2026, Janneke)."""
from backend.api.jobs import _vinted_schoenmaat_als_eu as eu


def _p(size, cat="kinderen schoenen"):
    return {"category": cat, "size": size, "title": "x"}


def test_hele_maat_krijgt_eu():
    assert eu(_p("26"))["size"] == "EU 26"


def test_halve_maat_met_punt_of_komma():
    assert eu(_p("25.5"))["size"] == "EU 25,5"
    assert eu(_p("25,5"))["size"] == "EU 25,5"


def test_andere_rubriek_of_maat_blijft_zoals_het_is():
    assert eu(_p("26", "sneakers dames"))["size"] == "26"
    assert eu(_p("98-104", "kinderen schoenen"))["size"] == "98-104"
    assert eu(_p("EU 26"))["size"] == "EU 26"
    assert eu(_p(None))["size"] is None


def test_oorspronkelijke_opdracht_blijft_onaangeroerd():
    p = _p("26")
    eu(p)
    assert p["size"] == "26"
