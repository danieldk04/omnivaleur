"""Een mislukte verwijdering maakt een nooit geplaatste advertentie niet live.

25-10-2026, klanten 31d28378 (Lyle & Scott-truien op Marktplaats) en 96e30080
(Perzisch tapijt op Vinted). De plaatsing mislukte, de rij stond op 'error'
zonder advertentienummer. Na de verkoop elders probeerde de verwijdering hem
weg te halen, vond niets, en fail_job zette de rij op 'active'. Daarna stond
hij in het dashboard als live en faalde elke volgende ronde opnieuw.

De foutmelding hieronder is letterlijk die uit productie.

Draaien:  python3 -m pytest tests/test_mislukte_verwijdering_maakt_niets_live.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.api import jobs

ECHT = (
    'Error: "Trui Lyle & Scott maat 110-116" cannot be found in your marktplaats listings '
    'overview, and we could not verify whether it is still online. Nothing was removed — check '
    'it by hand on marktplaats. | Advert page: no advert number [extensie 1.0.402]'
)
JOB = {"item_id": "i1", "action": "delete", "platform": "marktplaats", "payload": {}}


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.wijziging = db, tabel, None

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def execute(self):
        if self.wijziging is not None:
            self.db.wijzigingen.append((self.tabel, self.wijziging))
            return type("R", (), {"data": []})()
        if self.tabel == "jobs":
            return type("R", (), {"data": [JOB]})()
        if self.tabel == "listings":
            return type("R", (), {"data": [self.db.rij]})()
        return type("R", (), {"data": []})()

    def __getattr__(self, _naam):
        return lambda *a, **kw: self


class _Db:
    def __init__(self, rij):
        self.rij, self.wijzigingen = rij, []

    def table(self, naam):
        return _Vraag(self, naam)

    def rpc(self, *a, **kw):
        return _Vraag(self, "rpc")


def _faal(monkeypatch, rij):
    db = _Db(rij)
    monkeypatch.setattr(jobs, "get_db", lambda: db)
    monkeypatch.setattr(jobs, "_record_extension_heartbeat", lambda *a, **kw: None)
    jobs.fail_job("j1", {"error": ECHT}, user_id="31d28378")
    return [w for t, w in db.wijzigingen if t == "listings"]


@pytest.mark.parametrize("status", ["error", "pending"])
def test_nooit_geplaatste_rij_blijft_wat_hij_was(monkeypatch, status):
    rij = {"id": "l1", "status": status, "platform_listing_id": None, "listed_at": None}
    wijzigingen = _faal(monkeypatch, rij)
    assert wijzigingen, "de melding hoort wel bij de rij te komen"
    assert all(w.get("status") != "active" for w in wijzigingen), wijzigingen
    assert all(w.get("error_message") == ECHT for w in wijzigingen)


def test_een_echte_advertentie_blijft_actief_met_melding(monkeypatch):
    rij = {"id": "l1", "status": "active", "platform_listing_id": "m2456775173", "listed_at": None}
    wijzigingen = _faal(monkeypatch, rij)
    assert wijzigingen and wijzigingen[0]["status"] == "active"


def test_verkocht_wordt_niet_aangeraakt(monkeypatch):
    rij = {"id": "l1", "status": "sold", "platform_listing_id": None, "listed_at": None}
    assert _faal(monkeypatch, rij) == []
