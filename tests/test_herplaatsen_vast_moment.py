"""Herplaatsen op een vaste dag en een vast uur (19-10-2026, Voordeelsieraden).

Mieneke vroeg of ze kan kiezen wanneer haar advertenties opnieuw online komen.
Wie een moment kiest, mag alleen binnen dat uur iets klaargezet krijgen, en op
die dag het werk van alle dagen tot de volgende gekozen dag; anders verlopen
zijn advertenties alsnog. Wie niets kiest merkt niets.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from backend.services import crosslist, instellingen, relist
from tests.test_herplaatsronde_ziet_alles import _DB, _advertentie

ZONDAG_20 = {"dagen": [6], "uur": 20}


def _draai(monkeypatch, *, vast_moment, open_nu=True, aantal=5, grens=25):
    nu = datetime.now(timezone.utc)
    paren = ([_advertentie(i, "mieneke", 35, nu) for i in range(aantal)] +
             [_advertentie(5000 + i, "jaap", 35, nu) for i in range(3)])
    db = _DB({"listings": [p[0] for p in paren], "items": [p[1] for p in paren], "jobs": []})

    async def niets(*_a, **_k): return None
    monkeypatch.setattr(crosslist, "get_db", lambda: db)
    monkeypatch.setattr(crosslist, "_echte_datums_ophalen", niets)
    monkeypatch.setattr(crosslist, "_mag_nog_werken", lambda _u: True)
    monkeypatch.setattr(crosslist, "_dagelijkse_relist_grens", lambda _db, _u: grens)
    monkeypatch.setattr(instellingen, "alle_relist_dagen", lambda: {"mieneke": 30, "jaap": 30})
    monkeypatch.setattr(instellingen, "alle_relist_momenten", lambda: {"mieneke": ZONDAG_20})
    monkeypatch.setattr(instellingen, "moment_staat_open", lambda m, _nu: open_nu)
    monkeypatch.setattr(instellingen, "lees", lambda u: {"auto_relist": True, "relist_dagen": 30})
    klaargezet = []

    async def opnemer(item_id, platform, user_id, strategy, **_k):
        klaargezet.append(user_id)
        return {"status": "queued"}
    monkeypatch.setattr(relist, "refresh_listing", opnemer)
    if vast_moment:
        asyncio.run(crosslist.relist_op_vast_moment())
    else:
        asyncio.run(crosslist.relist_expiring_marktplaats())
    return klaargezet


def test_gewone_ronde_laat_wie_een_moment_koos_met_rust(monkeypatch):
    klaargezet = _draai(monkeypatch, vast_moment=False)
    assert "mieneke" not in klaargezet
    assert klaargezet.count("jaap") == 3          # wie niets koos: zoals altijd


def test_binnen_het_uur_gaat_het_wel(monkeypatch):
    klaargezet = _draai(monkeypatch, vast_moment=True)
    assert klaargezet == ["mieneke"] * 5          # en alleen zij, niet jaap


def test_buiten_het_uur_gebeurt_niets(monkeypatch):
    assert _draai(monkeypatch, vast_moment=True, open_nu=False) == []


def test_een_keer_per_week_krijgt_het_werk_van_zeven_dagen(monkeypatch):
    # Grens 25 per dag, alleen zondag: 175 op zondag, niet 25.
    klaargezet = _draai(monkeypatch, vast_moment=True, aantal=200, grens=25)
    assert klaargezet.count("mieneke") == 175


def test_moment_valt_in_nederlandse_tijd():
    # Zondag 19-10... is maandag; neem zondag 18-10-2026 20:30 in Amsterdam (CEST, UTC+2).
    zondag_avond = datetime(2026, 10, 18, 18, 30, tzinfo=timezone.utc)
    assert instellingen.moment_staat_open(ZONDAG_20, zondag_avond)
    assert not instellingen.moment_staat_open(ZONDAG_20, zondag_avond - timedelta(hours=1))
    assert not instellingen.moment_staat_open(ZONDAG_20, zondag_avond + timedelta(days=1))
    assert not instellingen.moment_staat_open(None, zondag_avond)


def test_dagen_per_moment():
    assert instellingen.dagen_per_moment({"dagen": [6], "uur": 20}, 6) == 7
    assert instellingen.dagen_per_moment({"dagen": [0, 3], "uur": 9}, 0) == 3
    assert instellingen.dagen_per_moment({"dagen": [0, 3], "uur": 9}, 3) == 4
    assert instellingen.dagen_per_moment({"dagen": list(range(7)), "uur": 9}, 2) == 1


def test_ongeldig_moment_wordt_gewoon_altijd():
    s = instellingen.schoon_moment
    assert s(None) is None
    assert s({"dagen": [], "uur": 20}) is None    # nooit stil laten vallen
    assert s({"dagen": [6], "uur": 24}) is None
    assert s({"dagen": [9], "uur": 20}) is None
    assert s({"dagen": ["6", 6, 0], "uur": "20"}) == {"dagen": [0, 6], "uur": 20}
    assert instellingen._schoon({})["relist_moment"] is None
    assert instellingen._schoon({"relist_moment": ZONDAG_20})["relist_moment"] == ZONDAG_20
