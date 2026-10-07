"""Shopify-producten met alleen een barcode en geen foto wachten niet op import.

WAAROM DIT ER IS (07-10-2026, Goudlief)
Hij verkoopt via bol en zet daarvoor producten in Shopify met alleen de EAN als
naam; bol vult foto en tekst aan. Op Marktplaats wil hij ze niet ("die ga ik
uiteraard niet op een marktplaats zetten"). Toch stonden ze klaar om te
importeren, en "Import all" maakte er 245 lege artikelen van.
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


JOB = {"id": "j1", "user_id": "u1", "platform": "shopify", "action": "scan"}


def _status(db, nummer):
    return next(c["status"] for c in db.import_candidates
                if str(c["platform_listing_id"]) == nummer)


def test_barcode_zonder_foto_begint_genegeerd():
    db = _DB(items=[], listings=[])
    api._store_scan_results(db, JOB, [
        # Letterlijk uit zijn winkel: titel = barcode, geen afbeelding.
        {"platform_listing_id": "10738468979015", "title": "8718946299939", "price": 29.95},
        {"platform_listing_id": "2", "title": "Zon sleutelhanger", "price": 15.99,
         "photo_url": "https://cdn.shopify.com/a.jpg"},
        # Barcode als naam maar wel een foto: dan beslist hij zelf.
        {"platform_listing_id": "3", "title": "8711113036627", "price": 56.99,
         "photo_url": "https://cdn.shopify.com/b.jpg"},
        # Een kort nummer is geen EAN.
        {"platform_listing_id": "4", "title": "605385", "price": 5},
    ])
    assert _status(db, "10738468979015") == "ignored"
    assert _status(db, "2") == "pending"
    assert _status(db, "3") == "pending"
    assert _status(db, "4") == "pending"


def test_alleen_shopify():
    assert not api._alleen_barcode("marktplaats", "8718946299939", [])
    assert api._alleen_barcode("shopify", " 8718946299939 ", [])


def test_eerdere_keuze_van_de_verkoper_wint():
    db = _DB(items=[], listings=[])
    db.import_candidates.append({"user_id": "u1", "platform": "shopify",
                                 "platform_listing_id": "9", "status": "pending"})
    db.import_candidates[0]["status"] = "imported"
    api._store_scan_results(db, JOB, [
        {"platform_listing_id": "9", "title": "8718946299939", "price": 1}])
    assert db.import_candidates[-1]["status"] == "imported"
