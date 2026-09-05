"""Toon (dejuistetoon), 05-09-2026.

Zijn "Grand Foulard Groot 264/128 cm" — een kleed van ruim twee en een halve
meter — stond in het dashboard onder "sieraden damestassen". Was hij zo
gepubliceerd, dan had Marktplaats hem onder Sieraden, Tassen en Uiterlijk gezet,
waar niemand naar woontextiel zoekt.

Het mechanisme is aanwijsbaar en niet geraden: de classificatieprompt in
backend/api/imports.py zegt over de sieraden-tak "Pick it for anything worn or
carried as an accessory", en een foulard is in gewoon Nederlands een sjaal. Het
woord "grand" ervoor maakt er juist een grote lap woontextiel van.

De keyword-terugval kon het ook niet rechtzetten: die gaf voor deze titel niets
terug, dus wat het model zei bleef staan.

Draaien: python -m pytest tests/test_grand_foulard_is_geen_sjaal.py
"""
import asyncio

import pytest

from backend.api import imports as imp


# ---------------------------------------------------------------- herkenning

@pytest.mark.parametrize("titel", [
    "Grand Foulard Groot 264/128 cm",
    "Grandfoulard woonkleed 174/125 cm",
    "Mooie grand foulards, twee stuks",
    "GRAND FOULARD bankkleed",
])
def test_een_grand_foulard_wordt_herkend(titel):
    assert imp._is_grand_foulard(titel) is True


@pytest.mark.parametrize("titel", [
    "Zijden foulard sjaal Hermes",       # losse foulard: dit is wél een sjaal
    "Foulard plaid zeilschepen dorp",
    "Grand Prix poster",
    "Vintage handgeknoopt tapijt 87/47cm",
])
def test_een_losse_foulard_blijft_met_rust(titel):
    assert imp._is_grand_foulard(titel) is False


# ------------------------------------------------------- de keyword-terugval

def test_terugval_gaf_niets_terug_en_geeft_nu_woontextiel():
    """Zonder API-antwoord viel de import terug op de woordenlijst. Die kende
    'grand foulard' niet, gaf niets terug, en dus bleef de foute keuze staan."""
    uit = imp._infer_attributes("Grand Foulard Groot 264/128 cm", "")
    assert uit.get("gender") == "wonen"
    assert uit.get("category") == "wonen plaids en woondekens"


def test_een_gewone_sjaal_wordt_niet_naar_de_woontak_getrokken():
    uit = imp._infer_attributes("Zijden foulard sjaal", "")
    assert uit.get("category") != "wonen plaids en woondekens"


# ------------------------------------------------------------- de correctie

def _smart(titel, wat_het_model_zegt, monkeypatch):
    async def nep(*_a, **_k):
        return dict(wat_het_model_zegt)
    monkeypatch.setattr(imp, "_classify_with_claude", nep)
    return asyncio.run(imp._infer_attributes_smart(titel, "", None))


def test_sieraden_wordt_teruggezet_naar_woontextiel(monkeypatch):
    """VOOR-EN-NA. Precies wat er bij Toon gebeurde: het model zei sieraden."""
    uit = _smart("Grand Foulard Groot 264/128 cm",
                 {"gender": "sieraden", "category": "sieraden damestassen"},
                 monkeypatch)
    assert uit["category"] == "wonen plaids en woondekens"
    assert uit["gender"] == "wonen"


def test_zonder_de_correctie_bleef_sieraden_staan(monkeypatch):
    """De tegenproef: haal de herkenning weg en de oude uitkomst komt terug."""
    monkeypatch.setattr(imp, "_is_grand_foulard", lambda *_a, **_k: False)
    uit = _smart("Grand Foulard Groot 264/128 cm",
                 {"gender": "sieraden", "category": "sieraden damestassen"},
                 monkeypatch)
    assert uit["category"] == "sieraden damestassen"


def test_een_keuze_binnen_de_woontak_blijft_staan(monkeypatch):
    """Tapijten of plaids is een kwestie van smaak, geen fout. Daar blijven we
    vanaf, anders herschrijven we advertenties die al goed staan."""
    uit = _smart("Soepele grand foulard kleed uit Thailand 240/203 cm",
                 {"gender": "wonen", "category": "wonen tapijten en kleden"},
                 monkeypatch)
    assert uit["category"] == "wonen tapijten en kleden"


def test_een_sjaal_wordt_niet_verplaatst(monkeypatch):
    uit = _smart("Zijden foulard sjaal Hermes",
                 {"gender": "sieraden", "category": "sieraden accessoires"},
                 monkeypatch)
    assert uit["category"] == "sieraden accessoires"


def test_de_gekozen_rubriek_bestaat_in_de_taxonomie():
    assert "wonen plaids en woondekens" in imp._TAXONOMY["wonen"]
