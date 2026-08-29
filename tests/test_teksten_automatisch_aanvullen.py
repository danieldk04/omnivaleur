"""Teksten die bij de import niet meekwamen worden vanzelf opgehaald.

De extensie kapt het verrijken na vier minuten af; alles daarna komt binnen
zonder omschrijving. Amanda Haas meldde dat op 29-08-2026. De reparatie mag niet
afhangen van een knop die de verkoper moet vinden.
"""
import asyncio
import types

import pytest

from backend.services import mp_enrich


class NepDb:
    """Alleen wat mp_enrich echt aanroept: items en platform_credentials."""

    def __init__(self, items, gekoppeld):
        self.items = items
        self.gekoppeld = gekoppeld

    def table(self, naam):
        return NepTabel(self, naam)


class NepTabel:
    def __init__(self, db, naam):
        self.db, self.naam = db, naam
        self.venster = None

    def select(self, *a, **kw):
        return self

    def or_(self, *a, **kw):
        return self

    def in_(self, *a, **kw):
        return self

    def range(self, start, eind):
        self.venster = (start, eind)
        return self

    def order(self, *a, **kw):
        return self

    def execute(self):
        rijen = (self.db.items if self.naam == "items"
                 else [{"user_id": u} for u in self.db.gekoppeld])
        if self.venster:  # fetch_all bladert; zonder venster blijft hij doorgaan
            start, eind = self.venster
            rijen = rijen[start:eind + 1]
        return types.SimpleNamespace(data=rijen)


@pytest.fixture(autouse=True)
def _geen_planner_state():
    mp_enrich._volgende_verkoper = 0


def _draai(db, monkeypatch, gedaan):
    monkeypatch.setattr("backend.database.get_db", lambda: db)

    async def nep_verrijk(_db, user_id, schrijf=True, maximaal=0, melden=None):
        gedaan.append((user_id, maximaal))
        return {"te_doen": 1, "omschrijving": 1, "prijs": 0}

    monkeypatch.setattr(mp_enrich, "verrijk", nep_verrijk)
    return asyncio.run(mp_enrich.vul_ontbrekende_teksten_aan())


def test_verkoper_zonder_teksten_wordt_bijgewerkt(monkeypatch):
    db = NepDb([{"user_id": "u1"}, {"user_id": "u1"}], {"u1"})
    gedaan = []
    uit = _draai(db, monkeypatch, gedaan)
    assert gedaan == [("u1", mp_enrich.AANVUL_PER_VERKOPER)]
    assert uit["verkoper"] == "u1"


def test_zonder_marktplaats_koppeling_gebeurt_er_niets(monkeypatch):
    """Zonder koppeling vinden we zijn advertenties niet — dan Marktplaats
    ook niet lastigvallen."""
    db = NepDb([{"user_id": "u9"}], set())
    gedaan = []
    uit = _draai(db, monkeypatch, gedaan)
    assert gedaan == []
    assert uit["verkopers"] == 0


def test_niets_te_doen(monkeypatch):
    db = NepDb([], {"u1"})
    gedaan = []
    uit = _draai(db, monkeypatch, gedaan)
    assert gedaan == []
    assert uit["reden"] == "niets te doen"


def test_verkopers_komen_om_de_beurt_aan_de_beurt(monkeypatch):
    """Eén verkoper met duizenden items mag de rest niet blokkeren."""
    db = NepDb([{"user_id": "groot"}] * 5 + [{"user_id": "klein"}],
               {"groot", "klein"})
    gedaan = []
    _draai(db, monkeypatch, gedaan)
    _draai(db, monkeypatch, gedaan)
    _draai(db, monkeypatch, gedaan)
    assert [u for u, _ in gedaan] == ["groot", "klein", "groot"]


def test_de_ronde_staat_in_de_planner():
    import inspect
    from backend import scheduler
    bron = inspect.getsource(scheduler.start_scheduler)
    assert "vul_ontbrekende_teksten_aan" in bron
    assert 'id="mp_teksten_aanvullen"' in bron
