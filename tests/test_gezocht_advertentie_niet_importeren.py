"""Een "Gezocht"-advertentie is geen voorraad en wacht dus niet op import.

WAAROM DIT ER IS (14-10-2026, onboarding)
Op Marktplaats en 2dehands kun je ook een advertentie zetten voor iets wat je
ZOEKT. De scan zag die als gewone advertentie. Anton (12-10) had "Pokémon
kaarten gezocht" klaarstaan, rambene (13-10) "gezocht penplotter" en "Gezocht:
XY-penplotter"; "Import all" maakte er artikelen van die daarna als te koop op
Vinted zouden gaan. Zo'n rij begint als genegeerd, niet als weg: "Show the
ignored again" haalt hem terug.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from backend.api import jobs as api  # noqa: E402
from tests.test_gescande_advertentie_al_gekoppeld import _DB  # noqa: E402


@pytest.fixture(autouse=True)
def _lokale_helpers(monkeypatch):
    monkeypatch.setattr(api, "fetch_all", lambda q: q().execute().data or [])
    monkeypatch.setattr(api, "fetch_all_in",
                        lambda q, _kolom, _waarden: q().execute().data or [])


def _status(db, nummer):
    return next(c["status"] for c in db.import_candidates
                if str(c["platform_listing_id"]) == nummer)


def test_gezocht_begint_genegeerd():
    job = {"id": "j1", "user_id": "u1", "platform": "2dehands", "action": "scan"}
    db = _DB(items=[], listings=[])
    api._store_scan_results(db, job, [
        # Letterlijk uit de scans van 12-10 en 13-10.
        {"platform_listing_id": "m1", "title": "gezocht penplotter", "price": 0},
        {"platform_listing_id": "m2", "price": 0,
         "title": "Gezocht: XY-penplotter / flatbed plotter – Roland DXY"},
        {"platform_listing_id": "m3", "title": "Pokémon kaarten gezocht", "price": 0},
        {"platform_listing_id": "m8", "price": 0,
         "title": "Pokémon Kaarten Gezocht | Inkoop 75–85%  | RamsesTCG"},
        {"platform_listing_id": "m4", "title": "GEVRAAGD: Vespa PX onderdelen", "price": 0},
        # Gewone voorraad blijft gewoon klaarstaan.
        {"platform_listing_id": "m5", "title": "vespa px neuskap", "price": 25},
        {"platform_listing_id": "m6", "title": "Lego 10179 Millennium Falcon, zeer gezocht", "price": 900},
        {"platform_listing_id": "m7", "title": "Veel gezocht model Nike Air Max 90", "price": 60},
    ])
    for nr in ("m1", "m2", "m3", "m4", "m8"):
        assert _status(db, nr) == "ignored", nr
    for nr in ("m5", "m6", "m7"):
        assert _status(db, nr) == "pending", nr


def test_alleen_marktplaats_en_2dehands():
    assert api._zoekertje("marktplaats", "Gezocht: oude radio")
    assert api._zoekertje("2dehands", "gevraagd fiets")
    assert not api._zoekertje("vinted", "Gezocht: oude radio")
    assert not api._zoekertje("shopify", "Gezocht")
