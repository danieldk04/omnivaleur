"""Vervangen bij een zakelijk Marktplaats- of 2dehands-account kan niet, dus niet aanbieden.

GEMETEN 17-09-2026, Johan Kist (zakelijk Marktplaats). Hij kreeg bij publiceren de
vraag "Replace that advert?" en klikte drie keer OK. Elke keer mislukte de
verwijdering op het lege persoonlijke overzicht van een zakelijk account, en de
plaatsing werd terecht overgeslagen. Resultaat: rode meldingen, niets veranderd.

Twee schakels:
1. _verkoper_soort zag Johan niet als zakelijk: die keek alleen naar advertenties
   die WIJ plaatsten, en al zijn advertenties waren geïmporteerd. Live nagemeten:
   oud "None", nieuw "TRADER" (zie de notitie van 17-09-2026 in docs/team-notes.md).
2. refresh_listing weigert nu vervangen bij een zakelijk account, vóór er iets
   wordt opgehaald of weggehaald.
"""
import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J        # noqa: E402
from backend.services import relist as R  # noqa: E402


class _DB:
    """Items en één actieve advertentie; al het andere mag niet gevraagd worden."""
    def __init__(self):
        self.gevraagd = []

    def table(self, naam):
        db = self

        class Q:
            def select(self, *_a): return self
            def eq(self, *_a): return self
            def in_(self, *_a): return self
            def not_(self): return self
            def limit(self, *_a): return self

            def execute(self):
                db.gevraagd.append(naam)
                rijen = {"items": [{"id": "i1", "user_id": "u", "title": "Martin D35 1979",
                                    "description": "x", "photo_urls": ["a", "b"], "price": 3300}],
                         "listings": [{"id": "l1", "item_id": "i1", "platform": "marktplaats",
                                       "status": "active", "platform_listing_id": "1528596781",
                                       "platform_listing_url": None}]}.get(naam)
                if rijen is None:
                    raise AssertionError(f"na de weigering mag {naam} niet meer gevraagd worden")
                return types.SimpleNamespace(data=rijen)
        return Q()


@pytest.fixture
def db(monkeypatch):
    d = _DB()
    monkeypatch.setattr(R, "get_db", lambda: d)
    return d


def test_zakelijk_account_krijgt_geen_vervanging(db, monkeypatch):
    monkeypatch.setattr(J, "_verkoper_soort", lambda _db, _u, p: "TRADER")
    with pytest.raises(R.RefreshError) as fout:
        asyncio.run(R.refresh_listing("i1", "marktplaats", "u", "relist"))
    assert "business account" in str(fout.value) and "Nothing was changed" in str(fout.value)
    assert set(db.gevraagd) <= {"items", "listings"}     # geen opdracht, geen oogst, geen quotum


@pytest.mark.parametrize("soort", ["CONSUMER", None])
def test_particulier_of_onbekend_gaat_voorbij_de_nieuwe_rem(db, monkeypatch, soort):
    monkeypatch.setattr(J, "_verkoper_soort", lambda _db, _u, p: soort)
    assert asyncio.run(R.zakelijk_account(db, "u", "marktplaats")) is False


def test_vinted_en_een_storing_blokkeren_nooit(db, monkeypatch):
    def kapot(*_a):
        raise RuntimeError("netwerk weg")
    monkeypatch.setattr(J, "_verkoper_soort", kapot)
    assert asyncio.run(R.zakelijk_account(db, "u", "marktplaats")) is False
    assert asyncio.run(R.zakelijk_account(db, "u", "vinted")) is False


def test_verkoper_soort_herkent_geimporteerde_advertentie_met_lettertje(monkeypatch):
    """Johans nummer staat als 1528596781 bij ons en als a1528596781 in de zoek-API."""
    J._VERKOPERSOORT.clear()

    class DB:
        def table(self, naam):
            class Q:
                def select(self, *_a): return self
                def eq(self, *_a): return self
                def in_(self, *_a): return self
                def limit(self, *_a): return self
                def order(self, *_a, **_k): return self

                @property
                def not_(self): return self

                def is_(self, *_a): return self

                def execute(self):
                    return types.SimpleNamespace(data={
                        "jobs": [],
                        "items": [{"id": "i1", "title": "Martin D35 1979"}],
                        "listings": [{"item_id": "i1", "platform_listing_id": "1528596781"}],
                    }[naam])
            return Q()

    class Antwoord:
        def __init__(self, data=None, text=""):
            self._data, self.text = data, text

        def json(self):
            return self._data

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url, params=None, headers=None):
            if params:
                return Antwoord({"listings": [{"itemId": "a1528596781", "vipUrl": "/v/x/a1528596781"}]})
            return Antwoord(text='..."sellerType":"TRADER"...')

    import httpx
    monkeypatch.setattr(httpx, "Client", Client)
    assert J._verkoper_soort(DB(), "johan", "marktplaats") == "TRADER"
    J._VERKOPERSOORT.clear()
