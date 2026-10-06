"""Vinted-herplaatsen staat standaard uit (voorwaarden Vinted 05-10-2026, par. 6).

Draait de echte refresh_listing: zonder expliciete aanzet weigert hij 'relist' op
Vinted, voordat er iets uit de database gelezen of weggeschreven wordt.
"""
import asyncio

import pytest

from backend.services import instellingen, relist


def _draai(user, platform="vinted", strategy="relist"):
    return asyncio.run(relist.refresh_listing("item-1", platform, user, strategy))


def test_standaard_uit():
    assert instellingen._schoon({})["vinted_herplaatsen"] is False
    assert instellingen._schoon({"vinted_herplaatsen": True})["vinted_herplaatsen"] is True


def test_vinted_relist_geweigerd_zonder_aanzet(monkeypatch):
    monkeypatch.setattr(instellingen, "lees", lambda u: instellingen._schoon({}))
    monkeypatch.setattr(relist, "get_db", lambda: (_ for _ in ()).throw(AssertionError("database aangeraakt")))
    with pytest.raises(relist.RefreshError, match="switched off"):
        _draai("u1")


def test_andere_kanalen_en_content_niet_geweigerd(monkeypatch):
    monkeypatch.setattr(instellingen, "lees", lambda u: instellingen._schoon({}))
    bereikt = []
    monkeypatch.setattr(relist, "get_db", lambda: bereikt.append(1) or (_ for _ in ()).throw(RuntimeError("db")))
    for platform, strategy in (("vinted", "content"), ("marktplaats", "relist")):
        with pytest.raises(RuntimeError, match="db"):
            _draai("u1", platform, strategy)
    assert len(bereikt) == 2


def test_vinted_wacht_langer_en_koelt_langer():
    assert relist.VINTED_DELAY_MIN_MINUTES >= 360
    assert relist.VINTED_DELAY_MAX_MINUTES <= 1440
    assert relist._cooldown_days("vinted") == 28
