"""Verkleedkleding is een eigen categorie, en een Vlaams "kleed" is een jurk.

Toon & Lynn (De Juiste Toon, 30-08-2026): een kleed werd bij ons een tas, en
lederhosen kwamen als korte broek of jeans op Marktplaats terecht omdat er geen
kostuum-categorie bestond.
"""
import re
from pathlib import Path

import pytest

from backend.api.imports import _TAXONOMY, _infer_attributes

WORTEL = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("titel,verwacht", [
    ("Originele Beierse lederhosen heren maat 52", "heren verkleedkleding"),
    ("Dirndl jurk dames Oktoberfest", "verkleedkleding"),
    ("Carnavalspak unisex", "unisex verkleedkleding"),
    ("Tiroler hoedje dames klederdracht", "verkleedkleding"),
])
def test_verkleedkleding_wordt_herkend(titel, verwacht):
    assert _infer_attributes(titel, "").get("category") == verwacht


def test_lederhose_wordt_geen_korte_broek():
    """Dit was de klacht: een lederhose eindigde als broektype en daarna als
    spijkerbroek op Marktplaats."""
    uit = _infer_attributes("Lederhosen heren bruin suède", "")
    assert uit.get("category") not in ("heren shorts", "heren jeans", "heren chinos")


@pytest.mark.parametrize("titel", [
    "Vintage kleed dames maat 38",
    "Zwart kleedje dames",
    "Perzisch kleed 200x300 dames",
])
def test_kleed_wordt_nooit_geraden(titel):
    """In Vlaanderen is een kleed een jurk, in Nederland een vloerkleed. Wij weten
    niet welke de verkoper bedoelt, dus vullen we niets in — een leeg veld vraagt
    om aandacht, een fout veld niet."""
    assert _infer_attributes(titel, "").get("category") is None


def test_het_model_krijgt_beide_betekenissen_mee():
    bron = (WORTEL / "backend/api/imports.py").read_text()
    assert "In Flemish" in bron and "means a RUG" in bron


def test_de_categorie_staat_in_alle_lijsten():
    """Ontbreekt hij ergens, dan valt het artikel stil terug op damesjeans."""
    for sleutel, groep in (("verkleedkleding", "dames"),
                           ("heren verkleedkleding", "heren"),
                           ("unisex verkleedkleding", "unisex")):
        assert sleutel in _TAXONOMY[groep]
    mp = (WORTEL / "extension/background.js").read_text()
    assert '"verkleedkleding":        { cat1: 621,  cat3: 623' in mp
    assert '"heren verkleedkleding":  { cat1: 1776, cat3: 2031' in mp


def test_marktplaats_ids_horen_bij_carnavalskleding():
    """623 en 2031 zijn de echte type-id's uit de categorieboom van Marktplaats
    (Kleding | Dames respectievelijk Kleding | Heren), niet gegokt."""
    mp = (WORTEL / "extension/background.js").read_text()
    regel = [r for r in mp.splitlines() if '"verkleedkleding"' in r][0]
    assert "Carnavalskleding en Feestkleding" in regel
