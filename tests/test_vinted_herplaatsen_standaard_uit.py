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


# ---- Via de echte API-routes: elk pad dat Vinted kan herplaatsen ----------

def _klant(monkeypatch, toegestaan):
    from fastapi.testclient import TestClient
    from backend.api import deps
    from backend.main import app
    app.dependency_overrides[deps.get_current_user] = lambda: "u1"
    app.dependency_overrides[deps.require_active_subscription] = lambda: "u1"
    monkeypatch.setattr(instellingen, "lees",
                        lambda u: instellingen._schoon({"vinted_herplaatsen": toegestaan}))
    geraakt = []

    def _db():
        geraakt.append(1)
        raise RuntimeError("db")
    monkeypatch.setattr(relist, "get_db", _db)
    from backend.api import jobs
    monkeypatch.setattr(jobs, "get_db", _db)
    return TestClient(app, raise_server_exceptions=False), geraakt, app


@pytest.mark.parametrize("pad,body", [
    ("/api/listings/refresh", {"item_id": "i", "platform": "vinted", "strategy": "relist"}),
    ("/api/jobs/relist-retry", {"item_id": "i", "platform": "vinted"}),
])
def test_routes_weigeren_vinted_relist_als_uit(monkeypatch, pad, body):
    klant, geraakt, app = _klant(monkeypatch, False)
    try:
        r = klant.post(pad, json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code in (400, 429), r.text
    assert "switched off" in r.text
    assert geraakt == [], "database aangeraakt: er had niets mogen gebeuren"


def test_routes_laten_vinted_relist_door_als_aan(monkeypatch):
    klant, geraakt, app = _klant(monkeypatch, True)
    try:
        r = klant.post("/api/listings/refresh",
                       json={"item_id": "i", "platform": "vinted", "strategy": "relist"})
    finally:
        app.dependency_overrides.clear()
    assert "switched off" not in r.text
    assert geraakt, "met schakelaar aan moet hij gewoon verder tot de database"


def test_instelling_onleesbaar_blijft_uit(monkeypatch):
    def stuk(u):
        raise RuntimeError("db weg")
    monkeypatch.setattr(instellingen, "lees", stuk)
    assert instellingen.vinted_herplaatsen_toegestaan("u1") is False
