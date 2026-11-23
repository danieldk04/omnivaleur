"""Een herplaatsing in een bekende betalende rubriek wordt niet eens klaargezet.

GEMETEN 23-11-2026, Mieneke (Voordeelsieraden, 09e089ec). Haar antieke sieraden
(Marktplaats-rubriek 1826/13) kosten op 2dehands geld. De uitgifte nam elke
herplaatsing daar terecht terug, maar pas nadat de ronde hem had klaargezet: de
oudste advertenties (precies die rubriek) kwamen elke ronde eerst aan de beurt,
vulden de dagruimte (21-11: 32 van 52, 23-11: 40 van 53) en stonden in het scherm
als rode "Herplaatsen mislukt" met een knop die hetzelfde antwoord gaf.

Draaien: python3 -m pytest tests/test_herplaatsen_betaalde_rubriek_planner.py -q
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.api import jobs as J
from backend.services import crosslist
from backend.services import photo_mirror  # noqa: F401
from backend.services import relist as R

OUD = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
ITEM = {"id": "i1", "user_id": "u1", "title": "Antieke ketting", "description": "Mooi stuk.",
        "price": 100.0, "photo_urls": ["https://img.omnivaleur.com/u/1.jpg"], "sku": "IMP-1",
        "category": "sieraden antiek"}
LISTING = {"id": "l1", "item_id": "i1", "platform": "2dehands", "status": "active",
           "platform_listing_id": "m1", "platform_listing_url": "https://www.2dehands.be/m1",
           "listed_at": OUD, "created_at": OUD, "last_refreshed_at": None, "refresh_count": 0,
           "reserved": False, "error_message": None}


class _DB:
    def __init__(self):
        self.ingevoegd = []
        self.bijgewerkt = []

    def table(self, naam):
        db = self

        class Q:
            op = "select"
            def __getattr__(self, _n):
                return lambda *a, **k: self
            def insert(self, rij, **_k): self.op = "insert"; db.ingevoegd.append((naam, rij)); self.rij = rij; return self
            def update(self, rij, *_a, **_k): self.op = "update"; db.bijgewerkt.append((naam, rij)); return self
            def delete(self, *_a, **_k): self.op = "delete"; return self
            def single(self): return self
            def maybe_single(self): return self
            def execute(self):
                if self.op == "insert":
                    return SimpleNamespace(data=[self.rij], count=0)
                if self.op != "select":
                    return SimpleNamespace(data=[{}], count=0)
                data = {"items": [dict(ITEM)], "listings": [dict(LISTING)]}.get(naam, [])
                return SimpleNamespace(data=data, count=0)
        return Q()


@pytest.fixture
def opzet(monkeypatch):
    async def vertaling(item, platform):
        return dict(item)

    async def geen_kenmerken(*_a, **_k):
        return {}

    async def nooit_zakelijk(*_a, **_k):
        return False
    from backend.services import mp_enrich
    monkeypatch.setattr(crosslist, "localize_item_for_platform", vertaling)
    monkeypatch.setattr(crosslist, "slotteksten_van", lambda uid: ("", ""))
    monkeypatch.setattr(mp_enrich, "advertentie_kenmerken", geen_kenmerken)
    monkeypatch.setattr(mp_enrich, "kenmerken_via_zoeken", geen_kenmerken)
    monkeypatch.setattr(R, "zakelijk_vervangen_kan_niet", nooit_zakelijk)
    db = _DB()
    monkeypatch.setattr(R, "get_db", lambda: db)
    J._BETAALD_CACHE.clear()
    R._BETAALD_GEWEIGERD.clear()
    return db


def _plan(**kw):
    return asyncio.run(R.refresh_listing("i1", "2dehands", "u1", "relist", **kw))


def _opdrachten(db):
    return [r for t, r in db.ingevoegd if t == "jobs"]


def test_bekende_betaalde_rubriek_zet_niets_klaar(opzet, monkeypatch):
    monkeypatch.setattr(J, "_betaalde_rubriek_bekend", lambda *a: True)
    with pytest.raises(R.RefreshError) as fout:
        _plan(eigen_quotum=True)
    assert str(fout.value) == J.HERPLAATSING_BETAALDE_RUBRIEK
    assert _opdrachten(opzet) == []          # geen verwijdering, dus niets offline
    # De advertentie zelf blijft actief en krijgt alleen de uitleg.
    assert ("listings", {"error_message": J.HERPLAATSING_BETAALDE_RUBRIEK}) in opzet.bijgewerkt
    assert not any(r.get("status") == "relisting" for _t, r in opzet.bijgewerkt)


def test_zelfde_artikel_wordt_niet_opnieuw_opgehaald(opzet, monkeypatch):
    aantal = []
    monkeypatch.setattr(J, "_betaalde_rubriek_bekend", lambda *a: aantal.append(1) or True)
    for _ in range(3):
        with pytest.raises(R.RefreshError):
            _plan(eigen_quotum=True)
    assert len(aantal) == 1                   # 1x gevraagd, daarna uit het geheugen


def test_rubriek_die_niet_geld_kost_gaat_gewoon_door(opzet, monkeypatch):
    monkeypatch.setattr(J, "_betaalde_rubriek_bekend", lambda *a: False)
    uit = _plan(eigen_quotum=True)
    assert uit["status"] == "queued"
    acties = [r["action"] for r in _opdrachten(opzet)]
    assert acties == ["delete", "create"]


def test_fout_in_de_controle_laat_de_herplaatsing_niet_sneuvelen(opzet, monkeypatch):
    def stuk(*_a):
        raise RuntimeError("database weg")
    monkeypatch.setattr(J, "_betaalde_rubriek_bekend", stuk)
    assert _plan(eigen_quotum=True)["status"] == "queued"


def test_handmatig_geeft_het_dagquotum_terug(opzet, monkeypatch):
    monkeypatch.setattr(J, "_betaalde_rubriek_bekend", lambda *a: True)
    teruggegeven = []
    monkeypatch.setattr(R, "_check_and_increment_quota", lambda *a, **k: None)
    monkeypatch.setattr(R, "rollback_refresh", lambda rb, uid: teruggegeven.append(uid))
    with pytest.raises(R.RefreshError):
        _plan()                               # handmatige knop: eigen_quotum=False
    assert teruggegeven == ["u1"]
    assert _opdrachten(opzet) == []
