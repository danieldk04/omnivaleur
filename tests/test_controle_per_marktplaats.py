"""Het dashboard toont per marktplaats wanneer er voor het laatst is nagekeken (15-11-2026).

De nagebouwde database filtert echt op user_id en platform, zoals Supabase: een
nep die altijd alles teruggeeft verstopt precies de fouten waar dit om draait
(zie de kennisbank, "nep-database-geeft-alle-kolommen").
Op de vorige commit bestond backend/services/controle.py niet en gaf
/extension-status geen `gecontroleerd` terug.
"""
import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import backend.api.jobs as J
from backend.services import controle

U, ANDER = "user-a", "user-b"


class _Q:
    def __init__(self, db):
        self.db, self.filters, self.op, self.row = db, {}, None, None

    def select(self, *a): self.op = "select"; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def limit(self, *a): return self
    def upsert(self, row, on_conflict=None): self.op, self.row = "upsert", row; return self

    def execute(self):
        if self.db.stuk:
            raise RuntimeError("database weg")
        if self.op == "upsert":
            self.db.rijen[(self.row["user_id"], self.row["platform"])] = self.row["extra_data"]
            return type("R", (), {"data": []})()
        sleutel = (self.filters.get("user_id"), self.filters.get("platform"))
        extra = self.db.rijen.get(sleutel)
        return type("R", (), {"data": [{"extra_data": extra}] if extra is not None else []})()


class _Db:
    def __init__(self): self.rijen, self.stuk = {}, False
    def table(self, naam):
        assert naam == "platform_credentials"
        return _Q(self)


@pytest.fixture(autouse=True)
def _schone_cache():
    controle._cache.clear()
    yield
    controle._cache.clear()


def test_een_controle_wordt_bewaard_en_teruggelezen():
    db = _Db()
    assert controle.zet(U, "marktplaats", db) is True
    assert list(controle.lees(U, db)) == ["marktplaats"]
    assert (U, "_controle") in db.rijen


def test_twee_kanalen_overschrijven_elkaar_niet():
    db = _Db()
    controle.zet(U, "marktplaats", db, nu=datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc))
    controle.zet(U, "vinted", db, nu=datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc))
    # Vers lezen uit de database, niet uit de cache.
    controle._cache.clear()
    uit = controle.lees(U, db)
    assert set(uit) == {"marktplaats", "vinted"}
    assert uit["marktplaats"].startswith("2026-11-15T10:00")


def test_andere_verkoper_ziet_niets_van_deze():
    db = _Db()
    controle.zet(U, "2dehands", db)
    controle._cache.clear()
    assert controle.lees(ANDER, db) == {}


def test_onbekend_kanaal_wordt_geweigerd_en_niet_bewaard():
    db = _Db()
    assert controle.zet(U, "bol", db) is False
    assert controle.zet(U, "_settings", db) is False
    assert db.rijen == {}


def test_een_kapotte_tijd_in_de_rij_verdwijnt():
    db = _Db()
    db.rijen[(U, "_controle")] = {"marktplaats": "gisteren", "vinted": 5, "bol": "2026-11-15T10:00:00+00:00",
                                  "2dehands": "2026-11-15T10:00:00Z"}
    assert set(controle.lees(U, db)) == {"2dehands"}


def test_een_storing_geeft_een_lege_lijst_en_slooptgeen_pagina():
    db = _Db()
    db.stuk = True
    assert controle.lees(U, db) == {}
    assert controle.zet(U, "vinted", db) is False


def test_het_eindpunt_bewaart_en_weigert_onbekend(monkeypatch):
    db = _Db()
    monkeypatch.setattr(controle, "get_db", lambda: db)
    assert asyncio.run(J.meld_platform_controle({"platform": "marktplaats"}, user_id=U)) == {"ok": True}
    assert (U, "_controle") in db.rijen
    with pytest.raises(HTTPException) as fout:
        asyncio.run(J.meld_platform_controle({"platform": "bol"}, user_id=U))
    assert fout.value.status_code == 422
    with pytest.raises(HTTPException):
        asyncio.run(J.meld_platform_controle({}, user_id=U))


class _StatusQ:
    def __init__(self, db, naam): self.db, self.naam, self.f = db, naam, {}
    def select(self, *a): return self
    def eq(self, k, v): self.f[k] = v; return self
    def in_(self, *a): return self
    def limit(self, *a): return self
    def order(self, *a, **k): return self
    def gte(self, *a): return self

    def execute(self):
        if self.naam == "extension_heartbeat":
            return type("R", (), {"data": [{"last_seen": datetime.now(timezone.utc).isoformat(),
                                            "ext_version": "1.0.421"}]})()
        if self.naam == "platform_credentials":
            extra = self.db.rijen.get((self.f.get("user_id"), self.f.get("platform")))
            return type("R", (), {"data": [{"extra_data": extra}] if extra is not None else []})()
        return type("R", (), {"data": []})()


class _StatusDb(_Db):
    def table(self, naam): return _StatusQ(self, naam)


def test_extension_status_geeft_de_controletijden_mee(monkeypatch):
    db = _StatusDb()
    db.rijen[(U, "_controle")] = {"marktplaats": "2026-11-15T10:00:00+00:00"}
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(controle, "get_db", lambda: db)
    uit = J.extension_status(user_id=U)
    assert uit["online"] is True
    assert uit["gecontroleerd"] == {"marktplaats": "2026-11-15T10:00:00+00:00"}
    # Een andere verkoper krijgt de tijden van deze niet te zien.
    controle._cache.clear()
    assert J.extension_status(user_id=ANDER)["gecontroleerd"] == {}


def test_een_afgeronde_scan_gebruikt_de_database_van_de_aanroep():
    """Op 15-11 gebruikte de stempel in complete_job de echte database, ook in
    tests met een nagebouwde: dat deed echte netwerkvragen (de volledige set
    duurde 13 minuten in plaats van 3) en kon een rij in productie zetten."""
    import inspect
    assert 'controle.zet(user_id, job.get("platform"), db)' in inspect.getsource(J.complete_job)
