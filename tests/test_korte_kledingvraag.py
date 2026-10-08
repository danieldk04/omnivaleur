"""Kleding krijgt eerst een korte rubriekvraag (Daniel, 08-10-2026: AI-tegoed sparen).

De volledige vraag stuurt alle 469 rubrieken mee (~9.000 tokens per product).
Herkenbare kleding, schoenen en sieraden krijgen eerst alleen die vijf takken.
Alleen bij twijfel of "past nergens" volgt alsnog de volledige vraag, zodat de
uitkomst nooit slechter wordt dan voorheen.
"""
import asyncio

import pytest

from backend.api import imports as imp


@pytest.fixture
def vragen(monkeypatch):
    gesteld = []
    antwoorden = []

    async def nep(client, prompt):
        gesteld.append(prompt)
        return antwoorden.pop(0)

    monkeypatch.setattr(imp, "_haiku_classificatie", nep)
    return gesteld, antwoorden


def _vraag(titel):
    return asyncio.run(imp._classify_with_claude(titel, None, None))


def test_kleding_heeft_genoeg_aan_de_korte_vraag(vragen):
    gesteld, antwoorden = vragen
    antwoorden.append('{"gender":"kinderen","category":"babykleding","confidence":"high"}')
    assert _vraag("Babypakje / romper Noppies maat 62") == {
        "gender": "kinderen", "category": "babykleding"}
    assert len(gesteld) == 1
    assert "boeken" not in gesteld[0] and "babykleding" in gesteld[0]


def test_de_korte_vraag_is_minstens_vijf_keer_kleiner(vragen):
    gesteld, antwoorden = vragen
    antwoorden += ['{"gender":"none","category":"none","confidence":"high"}',
                   '{"gender":"heren","category":"heren t-shirts","confidence":"high"}']
    _vraag("T-shirt maat L")
    kort, volledig = gesteld
    assert len(kort) * 5 < len(volledig)


def test_past_nergens_in_de_korte_vraag_dan_de_volledige(vragen):
    gesteld, antwoorden = vragen
    antwoorden += ['{"gender":"none","category":"none","confidence":"high"}',
                   '{"gender":"fietsen","category":"fietsen kinderfietsen","confidence":"high"}']
    _vraag("Kinderfiets maat 16 inch")  # "fiets" wijst meteen naar de volledige vraag
    assert len(gesteld) == 1 and "boeken" in gesteld[0]
    gesteld.clear(); antwoorden.clear()
    antwoorden += ['{"gender":"none","category":"none","confidence":"high"}',
                   '{"gender":"heren","category":"heren t-shirts","confidence":"high"}']
    uit = _vraag("Shirt maat M")
    assert len(gesteld) == 2
    assert uit == {"gender": "heren", "category": "heren t-shirts"}


def test_twijfel_of_rubriek_buiten_kleding_telt_niet(vragen):
    gesteld, antwoorden = vragen
    antwoorden += ['{"gender":"wonen","category":"wonen plaids en woondekens","confidence":"high"}',
                   '{"gender":"heren","category":"heren truien","confidence":"high"}']
    assert _vraag("Trui maat L")["category"] == "heren truien"
    assert len(gesteld) == 2
    gesteld.clear()
    antwoorden += ['{"gender":"heren","category":"heren truien","confidence":"low"}',
                   '{"gender":"heren","category":"heren truien","confidence":"high"}']
    _vraag("Trui maat L")
    assert len(gesteld) == 2


def test_een_storing_in_de_korte_vraag_valt_terug_op_de_volledige(vragen, monkeypatch):
    gesteld = []

    async def nep(client, prompt):
        gesteld.append(prompt)
        if len(gesteld) == 1:
            raise RuntimeError("429")
        return '{"gender":"heren","category":"heren truien","confidence":"high"}'

    monkeypatch.setattr(imp, "_haiku_classificatie", nep)
    assert _vraag("Trui maat L")["category"] == "heren truien"
    assert len(gesteld) == 2


@pytest.mark.parametrize("titel", ["Perzisch tapijtje 127/68", "Lego set 60110",
                                   "Gibson gitaar", "Granny woondeken", "Iets"])
def test_andere_takken_gaan_meteen_naar_de_volledige_vraag(titel):
    assert not imp._alleen_kledingtakken(titel, None)


@pytest.mark.parametrize("titel", ["Schoenen | Regenlaarzen Bergstein schoenmaat 27",
                                   "Longsleeve Noppies maat 44/50", "Zilveren ring 925",
                                   "Ralph Lauren polo heren XL"])
def test_kleding_en_sieraden_gaan_naar_de_korte_vraag(titel):
    assert imp._alleen_kledingtakken(titel, None)
