"""Bieden toestaan voor veel artikelen in één keer.

WAAROM DIT ER IS (07-10-2026, Goudlief)
Bieden stond alleen per artikel in het bewerkscherm; zij importeert duizenden
Shopify-producten. /api/items/bulk-bidding zet bid_percentage voor een selectie
of voor de hele voorraad, en altijd alleen binnen het eigen account.
"""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api import items as items_api  # noqa: E402


class _Vraag:
    def __init__(self, log):
        self.log, self.stappen = log, []

    def __getattr__(self, naam):
        def stap(*a, **kw):
            self.stappen.append((naam, a))
            return self
        return stap


class _Db:
    def __init__(self):
        self.log = []

    def table(self, naam):
        v = _Vraag(self.log)
        v.stappen.append(("table", (naam,)))
        self.log.append(v)
        return v


def _zet(monkeypatch, alle_ids=()):
    db = _Db()
    monkeypatch.setattr(items_api, "get_db", lambda: db)
    monkeypatch.setattr(items_api, "fetch_all", lambda f: [{"id": i} for i in alle_ids])

    class _Uit:
        def __init__(self, n):
            self.data = [{}] * n

    def uitvoeren(v):
        ids = next(a[1] for n, a in v.stappen if n == "in_")
        return _Uit(len(ids))
    monkeypatch.setattr(items_api, "execute_with_retry", uitvoeren)
    return db


def _doe(body):
    return asyncio.run(items_api.bulk_bidding(body, user_id="eigenaar"))


def test_selectie_krijgt_percentage_binnen_eigen_account(monkeypatch):
    db = _zet(monkeypatch)
    uit = _doe({"percentage": 70, "ids": ["a", "b"]})
    assert uit == {"updated": 2, "percentage": 70}
    stappen = db.log[0].stappen
    assert ("update", ({"bid_percentage": 70},)) in stappen
    assert ("eq", ("user_id", "eigenaar")) in stappen


def test_nul_zet_bieden_uit(monkeypatch):
    db = _zet(monkeypatch)
    assert _doe({"percentage": 0, "ids": ["a"]})["percentage"] is None
    assert ("update", ({"bid_percentage": None},)) in db.log[0].stappen


def test_hele_voorraad(monkeypatch):
    _zet(monkeypatch, alle_ids=[f"i{n}" for n in range(450)])
    assert _doe({"percentage": 60, "all_items": True})["updated"] == 450


@pytest.mark.parametrize("body", [
    {"percentage": 120, "ids": ["a"]},
    {"percentage": "zeventig", "ids": ["a"]},
    {"percentage": 70},
])
def test_onzin_wordt_geweigerd(monkeypatch, body):
    _zet(monkeypatch)
    with pytest.raises(HTTPException):
        _doe(body)
