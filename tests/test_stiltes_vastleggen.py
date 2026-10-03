"""De server legt vast wanneer een extensie weg was (03-10-2026, Egbert).

Elke proef draait de echte _record_extension_heartbeat met een nagebouwde database.
Op c2157f7b bestond dit niet: de oude code schrijft nooit een stilte weg.
"""
import subprocess
from datetime import datetime, timedelta, timezone

import backend.api.jobs as J

U = "bcdf9aa4-test"
T0 = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


class _Q:
    def __init__(self, db, naam):
        self.db, self.naam, self.op, self.data = db, naam, None, None

    def select(self, *a): self.op = "select"; return self
    def eq(self, *a): return self
    def limit(self, *a): return self
    def upsert(self, row): self.op, self.data = "upsert", row; return self
    def insert(self, row): self.op, self.data = "insert", row; return self

    def execute(self):
        if self.naam == "extension_stiltes" and self.db.stiltes_tabel_mist:
            raise RuntimeError("relation does not exist")
        if self.op == "insert":
            self.db.stiltes.append(self.data)
        elif self.op == "upsert":
            self.db.heartbeat = self.data
        elif self.op == "select":
            return type("R", (), {"data": [{"last_seen": self.db.heartbeat["last_seen"]}]
                                  if self.db.heartbeat else []})()
        return type("R", (), {"data": []})()


class _Db:
    def __init__(self, heartbeat=None, stiltes_tabel_mist=False):
        self.heartbeat, self.stiltes, self.stiltes_tabel_mist = heartbeat, [], stiltes_tabel_mist

    def table(self, naam): return _Q(self, naam)


def _poll(db, minuten, monkeypatch):
    nu = T0 + timedelta(minutes=minuten)

    class _Dt(datetime):
        @classmethod
        def now(cls, tz=None): return nu
    monkeypatch.setattr(J, "datetime", _Dt)
    J._record_extension_heartbeat(db, U, "UA", "1.0.364")


def _schoon():
    J._LAATST_GEZIEN.clear()
    J._STILTES_UIT_TOT[0] = 0.0


def test_een_stilte_van_veertig_minuten_wordt_vastgelegd(monkeypatch):
    _schoon(); db = _Db()
    _poll(db, 0, monkeypatch); _poll(db, 1, monkeypatch)
    assert db.stiltes == []
    _poll(db, 41, monkeypatch)
    assert len(db.stiltes) == 1 and db.stiltes[0]["minuten"] == 40.0
    assert db.stiltes[0]["stil_van"].startswith("2026-10-03T15:01")


def test_na_een_herstart_van_de_server_telt_de_stilte_uit_de_heartbeat(monkeypatch):
    _schoon()
    db = _Db(heartbeat={"last_seen": T0.isoformat()})
    _poll(db, 20, monkeypatch)
    assert len(db.stiltes) == 1 and db.stiltes[0]["minuten"] == 20.0


def test_gewoon_pollen_legt_niets_vast(monkeypatch):
    _schoon(); db = _Db()
    for m in range(0, 10):
        _poll(db, m, monkeypatch)
    assert db.stiltes == []


def test_ontbrekende_tabel_breekt_de_aanwezigheidsstempel_niet(monkeypatch):
    _schoon(); db = _Db(stiltes_tabel_mist=True)
    _poll(db, 0, monkeypatch); _poll(db, 30, monkeypatch)
    assert db.heartbeat["last_seen"].startswith("2026-10-03T15:30")


def test_de_oude_code_legt_nooit_een_stilte_vast():
    oud = subprocess.run(["git", "show", "c2157f7b:backend/api/jobs.py"],
                         capture_output=True, text=True).stdout
    assert "extension_stiltes" not in oud
