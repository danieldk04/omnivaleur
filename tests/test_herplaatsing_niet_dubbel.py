"""Geen tweede herplaatsing naast een lopende, en de nieuwste actieve rij eerst.

02-11-2026: 10 artikelen stonden twee keer live op Marktplaats. Twee herplaatsingen
van één rij liepen tegelijk (77539a54: beide verwijderden m2440809548), en
refresh_listing koos zonder volgorde een rij, ook een oude die al weg was.

Draaien:  python3 -m pytest tests/test_herplaatsing_niet_dubbel.py -q
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.services import relist as R


class _DB:
    def __init__(self, lopend):
        self.lopend = lopend
        self.volgorde = []

    def table(self, naam):
        db = self

        class Q:
            def select(self, *_a): return self
            def eq(self, *_a): return self
            def in_(self, *_a): return self
            def limit(self, *_a): return self

            def order(self, kolom, **kw):
                db.volgorde.append((naam, kolom, kw.get("desc")))
                return self

            def execute(self):
                rijen = {"items": [{"id": "i1", "user_id": "u", "title": "Zilveren ring",
                                    "description": "x", "photo_urls": ["a", "b"], "price": 30}],
                         "listings": [{"id": "l1", "item_id": "i1", "platform": "marktplaats",
                                       "status": "active", "platform_listing_id": "m1",
                                       "platform_listing_url": None}],
                         "jobs": db.lopend}[naam]
                return types.SimpleNamespace(data=rijen)
        return Q()


def _draai(db, monkeypatch):
    monkeypatch.setattr(R, "get_db", lambda: db)

    async def _nooit_zakelijk(*_a, **_k):
        return False
    monkeypatch.setattr(R, "zakelijk_vervangen_kan_niet", _nooit_zakelijk)
    return asyncio.run(R.refresh_listing("i1", "marktplaats", "u", "relist"))


def test_lopende_herplaatsing_blokkeert_een_tweede(monkeypatch):
    db = _DB(lopend=[{"id": "j1"}])
    with pytest.raises(R.RefreshError, match="already in progress"):
        _draai(db, monkeypatch)


def test_nieuwste_actieve_rij_eerst(monkeypatch):
    db = _DB(lopend=[{"id": "j1"}])
    with pytest.raises(R.RefreshError):
        _draai(db, monkeypatch)
    assert ("listings", "listed_at", True) in db.volgorde
