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
    "Vintage kleed 200x300",
    "Perzisch kleed handgeknoopt",
    "Berber vloerkleed wol",
    "Groot tapijt beige",
])
def test_kleed_zonder_kledingsignaal_is_een_vloerkleed(titel):
    """Bevestigd door De Juiste Toon (30-08-2026): met "kleed" bedoelden zij
    vloerkleden. Zonder kledingsignaal is dat in Nederland de betekenis."""
    uit = _infer_attributes(titel, "")
    assert uit.get("category") == "wonen tapijten en kleden"
    assert uit.get("gender") == "wonen"


@pytest.mark.parametrize("titel", [
    "Vintage kleed dames maat 38",
    "Zwart kleedje dames",
])
def test_met_kledingsignaal_beslist_het_model(titel):
    """Staat er "dames" bij, dan raden we niets: dan kan het toch een jurk zijn
    (Vlaams) en beslist het model op de rest van de tekst."""
    assert _infer_attributes(titel, "").get("category") != "wonen tapijten en kleden"


def test_tafelkleed_is_geen_vloerkleed():
    """Waar het hier om gaat is dat een tafelkleed niet op de vloer belandt.

    Tot 05-09-2026 bleef de rubriek daarvoor leeg: "tafelkleed" is één woord en
    viel dus buiten de kleden-lijst, en verder ving niets het op. Sinds De Juiste
    Toon met 21 artikelen zonder rubriek bleef zitten (zie
    tests/test_woontextiel_zonder_rubriek.py) krijgt hij zijn eigen rubriek. Dat
    is wat deze proef altijd al wilde: níét op de vloer."""
    uit = _infer_attributes("Linnen tafelkleed wit", "")
    assert uit.get("category") != "wonen tapijten en kleden"
    assert uit.get("category") == "wonen tafelkleden"


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
