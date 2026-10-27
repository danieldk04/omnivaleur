"""Een herplaatsing in een rubriek die al geld bleek te kosten gaat niet door.

WAAROM (27-10-2026, da176583). Op 26-10 om 15:57 weigerde Marktplaats twee
herplaatsingen in "Ladders en Trappen" en "Isolatie en Afdichting": betaalde
rubriek. Om 18:55 zette de herplaatsronde voor twee andere artikelen in diezelfde
rubrieken een nieuwe herplaatsing klaar; de extensie haalde vanochtend de oude
advertenties weg en de nieuwe strandden weer op de betaalpagina. De rem hoort
vóór de verwijdering, in de echte uitgifte.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as J  # noqa: E402
from tests.test_mislukte_herplaatsing_zichtbaar import _EchteDB  # noqa: E402

BETAALD = ('Marktplaats (marktplaats.nl) charges for adverts in "Doe-het-zelf en Verbouw '
           'Ladders en Trappen": the site says this is a paid category, and it now puts every '
           'next advert there on an order to be paid instead of publishing it.')


@pytest.fixture(autouse=True)
def _lege_cache():
    getattr(J, "_BETAALD_CACHE", {}).clear()


def _uitgifte(monkeypatch, rubriek_van_de_weigering):
    VERWIJDER = {"id": "delete-1", "user_id": "u1", "item_id": "it1",
                 "platform": "marktplaats", "action": "delete", "status": "pending",
                 "created_at": "2026-10-26T18:55:00+00:00",
                 "payload": {"_refresh_rollback": {"listing_id": "rij-1", "day": "2026-10-26"},
                             "platform_listing_id": "m1"}}
    PLAATS = {"id": "create-1", "user_id": "u1", "item_id": "it1",
              "platform": "marktplaats", "action": "create", "status": "pending",
              "created_at": "2026-10-26T18:55:01+00:00",
              "scheduled_for": "2020-01-01T00:00:00+00:00",
              "payload": {"price": 25, "category": "klussen ladders en trappen",
                          "_vervangt_listing_id": "rij-1"}}
    WEIGERING = {"status": "error", "created_at": "2026-10-25T20:17:00+00:00",
                 "done_at": "2026-10-26T15:58:00+00:00", "result": {"error": BETAALD},
                 "category": rubriek_van_de_weigering, "mp_category": None,
                 "fout": BETAALD}

    def antwoorden(b):
        f = b.filters
        if b.tabel == "jobs" and f.get("action") == "create" and f.get("status") == "error":
            return [WEIGERING]
        if b.tabel == "jobs" and f.get("action") == "create" and isinstance(f.get("status"), list):
            return [WEIGERING]
        if b.tabel == "jobs" and f.get("action") == "create" and f.get("status") == "pending":
            return [PLAATS]
        if b.tabel == "jobs" and f.get("action") == "delete":
            return [VERWIJDER]
        if b.tabel == "jobs" and f.get("status") == "pending":
            return [VERWIJDER, PLAATS]
        if b.tabel == "listings" and f.get("id") == "rij-1":
            return [{"id": "rij-1", "status": "relisting", "listed_at": None,
                     "platform_listing_id": "m1"}]
        if b.tabel == "items":
            return [{"id": "it1", "user_id": "u1", "title": "Aluminium ladder",
                     "sku": None, "brand": None, "price": 25}]
        return []

    db = _EchteDB(antwoorden)
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    import backend.services.relist as R
    monkeypatch.setattr(R, "rollback_refresh", lambda rb, uid: None)

    class _Verzoek:
        headers = {"x-omnivaleur-ext": "1.0.404", "user-agent": "test"}

    uit = J.get_pending_jobs(_Verzoek(), platform="marktplaats", user_id="u1")
    return db, uit


def test_bekende_betaalde_rubriek_haalt_de_advertentie_niet_weg(monkeypatch):
    db, uit = _uitgifte(monkeypatch, "klussen ladders en trappen")
    assert "delete-1" not in [j["id"] for j in uit], "de oude advertentie moet blijven staan"
    terug = [r for r in db.log if r["tabel"] == "listings" and r["soort"] == "update"]
    assert terug and terug[0]["velden"]["status"] == "active"
    assert "charges for adverts" in terug[0]["velden"]["error_message"]


def test_een_andere_rubriek_gaat_gewoon_door(monkeypatch):
    db, uit = _uitgifte(monkeypatch, "klussen isolatie en afdichting")
    assert "delete-1" in [j["id"] for j in uit]
    assert not [r for r in db.log if r["tabel"] == "listings" and r["soort"] == "update"]
