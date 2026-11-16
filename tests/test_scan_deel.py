"""Eerste batch van een lopende scan vooruit sturen (Daniel, 16-11-2026).

Bij 257 advertenties duurde een scan minuten en kwam er pas na afloop iets binnen.
Het eindpunt slaat alleen kandidaten op (nooit items) en alleen voor een lopende
Marktplaats- of 2dehands-scan van de klant zelf.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api import jobs as J  # noqa: E402


class _Q:
    def __init__(self, rijen): self.rijen = rijen
    def select(self, *_a, **_k): return self
    def eq(self, k, v): self.rijen = [r for r in self.rijen if r.get(k) == v]; return self
    def limit(self, _n): return self
    def execute(self): return type("A", (), {"data": self.rijen})()


class _DB:
    def __init__(self, jobs): self.jobs = jobs
    def table(self, naam): return _Q(list(self.jobs))


@pytest.fixture
def omgeving(monkeypatch):
    opgeslagen = []
    job = {"id": "j1", "user_id": "u1", "action": "scan", "platform": "marktplaats", "status": "claimed"}
    db = _DB([job])
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(J, "_store_scan_results", lambda d, j, l: opgeslagen.append(l))
    return job, opgeslagen


def _roep(body, user="u1", job_id="j1"):
    return asyncio.run(J.scan_deel(job_id, body, user))


def test_lopende_scan_slaat_kandidaten_op(omgeving):
    job, opgeslagen = omgeving
    uit = _roep({"listings": [{"platform_listing_id": str(i)} for i in range(20)]})
    assert uit["opgeslagen"] == 20 and len(opgeslagen[0]) == 20


def test_maximaal_zestig(omgeving):
    job, opgeslagen = omgeving
    _roep({"listings": [{"platform_listing_id": str(i)} for i in range(100)]})
    assert len(opgeslagen[0]) == 60


def test_andermans_scan_is_niet_te_vinden(omgeving):
    with pytest.raises(J.HTTPException) as e:
        _roep({"listings": [{"platform_listing_id": "1"}]}, user="ander")
    assert e.value.status_code == 404


def test_afgeronde_scan_slaat_niets_meer_op(omgeving):
    job, opgeslagen = omgeving
    job["status"] = "done"
    assert _roep({"listings": [{"platform_listing_id": "1"}]})["opgeslagen"] == 0 and not opgeslagen


@pytest.mark.parametrize("actie,platform", [("create", "marktplaats"), ("scan", "vinted")])
def test_alleen_marktplaats_of_2dehands_scan(omgeving, actie, platform):
    job, _ = omgeving
    job.update(action=actie, platform=platform)
    with pytest.raises(J.HTTPException) as e:
        _roep({"listings": [{"platform_listing_id": "1"}]})
    assert e.value.status_code == 400


def test_lege_lijst_doet_niets(omgeving):
    job, opgeslagen = omgeving
    assert _roep({"listings": []})["opgeslagen"] == 0 and not opgeslagen
