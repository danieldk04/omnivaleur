"""Het hele verkoopcircuit over alle kanalen (09-10-2026, Daniel: "iemand verkoopt op
de ene marketplace en dat dat goed werkt op de andere").

Eén artikel staat op alle zeven kanalen. Per kanaal één verkoop, door de ECHTE
handle_item_sold, de echte verwijderopdracht voor de extensie
(_enqueue_extension_delete) en de echte afmelding via de server (_delist_one,
met de echte WooCommercePlatform tegen een nagebootste winkel). Alleen eBay en
Shopify zelf zijn nagebootst; hun eigen afmelding heeft eigen proeven.

Wat er moet gebeuren:
  * het kanaal van de verkoop krijgt 'sold' en wordt met rust gelaten;
  * Marktplaats, 2dehands, Vinted en Facebook krijgen één verwijderopdracht
    voor de extensie;
  * eBay en Shopify worden via hun eigen koppeling afgemeld;
  * WooCommerce gaat op uitverkocht, het product blijft bestaan;
  * dezelfde verkoop een tweede keer melden maakt niets dubbel.
"""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.platforms import woocommerce as w  # noqa: E402
import backend.platforms as plats  # noqa: E402
from backend.services import crosslist as cl  # noqa: E402
from backend.services import shopify_voorraad as sv  # noqa: E402
from backend.services import tweelingen  # noqa: E402
from backend.services import woocommerce_voorraad as wv  # noqa: E402
from tests.test_woocommerce import _DB, FakeWoo, _product  # noqa: E402

EXTENSIE = ["marktplaats", "2dehands", "vinted", "facebook"]
SERVER = ["ebay", "shopify", "woocommerce"]
ALLE = EXTENSIE + SERVER


class _Koppeling:
    """eBay of Shopify: onthoudt wat er afgemeld werd."""

    def __init__(self, naam, log):
        self.naam, self.log = naam, log

    async def delete_listing(self, pid, creds):
        self.log.append((self.naam, pid))
        return True


def _situatie(stuks_in_winkel=1):
    listings = []
    for i, p in enumerate(ALLE):
        rij = {"id": f"l-{p}", "item_id": "i1", "platform": p, "status": "active",
               "platform_listing_id": "101" if p == "woocommerce" else f"{p}-{i}",
               "platform_listing_url": f"https://{p}.example/{i}", "listed_at": "2026-10-01T10:00:00"}
        if p == "ebay":
            rij["platform_offer_id"] = "offer-1"
        listings.append(rij)
    creds = [{"user_id": "u1", "platform": p, "access_token": "ck_x" if p == "woocommerce" else "t",
              "refresh_token": "cs_x", "extra_data": {"api_root": "https://mikkis.nl/wp-json/"}}
             for p in SERVER]
    db = _DB(items=[{"id": "i1", "user_id": "u1", "title": "Jottum winterjas", "sku": "MK-101"}],
             listings=listings, platform_credentials=creds, jobs=[], sync_events=[])
    return db, FakeWoo([_product(stuks=stuks_in_winkel)])


def _verkoop(monkeypatch, db, winkel, kanaal):
    afgemeld = []

    async def _naast(fn, *_a, **_k): return fn()

    for m in (cl, sv, wv):
        monkeypatch.setattr(m, "naast_de_lus", _naast, raising=False)
    monkeypatch.setattr(cl, "get_db", lambda: db)
    monkeypatch.setattr(cl, "_nooit_online", lambda *_a: False)
    monkeypatch.setattr(cl, "_last_listed_title", lambda *_a: "Jottum winterjas")
    monkeypatch.setattr(tweelingen, "familie_ids", lambda _db, _it: ["i1"])

    async def _geen_shopify_voorraad(*_a): return None
    monkeypatch.setattr(sv, "na_verkoop", _geen_shopify_voorraad)
    monkeypatch.setattr(wv, "client_uit", lambda _c: winkel)
    monkeypatch.setattr(w, "client_uit", lambda _c: winkel)
    register = dict(plats.PLATFORM_REGISTRY)
    register["ebay"] = _Koppeling("ebay", afgemeld)
    register["shopify"] = _Koppeling("shopify", afgemeld)
    monkeypatch.setattr(cl, "get_platform", lambda naam: register[naam])
    asyncio.run(cl.handle_item_sold("i1", kanaal, sold_price=45.0, bewijs=cl.BEWIJS_BESTELLING))
    return afgemeld


def _status(db, p):
    return next(l["status"] for l in db.t["listings"] if l["platform"] == p)


def _verwijderopdrachten(db):
    return sorted(j["platform"] for j in db.t["jobs"] if j.get("action") == "delete")


@pytest.mark.parametrize("kanaal", ALLE)
def test_verkoop_op_een_kanaal_haalt_het_overal_anders_weg(monkeypatch, kanaal):
    # Bij een verkoop in de winkel heeft WooCommerce de voorraad al op 0 gezet.
    db, winkel = _situatie(stuks_in_winkel=0 if kanaal == "woocommerce" else 1)
    afgemeld = _verkoop(monkeypatch, db, winkel, kanaal)

    assert _status(db, kanaal) == "sold"
    assert _verwijderopdrachten(db) == sorted(p for p in EXTENSIE if p != kanaal), \
        "elk ander extensiekanaal precies één verwijderopdracht"
    assert sorted(n for n, _ in afgemeld) == sorted(p for p in ("ebay", "shopify") if p != kanaal)
    if ("ebay", "offer-1") not in afgemeld and kanaal != "ebay":
        raise AssertionError("eBay wordt afgemeld op zijn offer-nummer")
    p = winkel.p["101"]
    assert p["stock_status"] == "outofstock" and p["status"] == "publish", \
        "WooCommerce op uitverkocht, nooit gewist"
    for andere in SERVER:
        if andere != kanaal:
            assert _status(db, andere) == "delisted"


@pytest.mark.parametrize("kanaal", ALLE)
def test_dezelfde_verkoop_twee_keer_gemeld_maakt_niets_dubbel(monkeypatch, kanaal):
    db, winkel = _situatie(stuks_in_winkel=0 if kanaal == "woocommerce" else 1)
    _verkoop(monkeypatch, db, winkel, kanaal)
    tweede = _verkoop(monkeypatch, db, winkel, kanaal)
    assert _verwijderopdrachten(db) == sorted(p for p in EXTENSIE if p != kanaal), \
        "geen tweede verwijderopdracht"
    assert tweede == [], "eBay en Shopify zijn al afgemeld; niet nog eens"
    assert sum(1 for l in db.t["listings"] if l["status"] == "sold") == 1


def test_verkoop_zonder_bewijs_meldt_nergens_iets_af(monkeypatch):
    db, winkel = _situatie()
    afgemeld = []

    async def _naast(fn, *_a, **_k): return fn()
    for m in (cl, sv, wv):
        monkeypatch.setattr(m, "naast_de_lus", _naast, raising=False)
    monkeypatch.setattr(cl, "get_db", lambda: db)

    async def _vraag(*_a): afgemeld.append("vraag")
    monkeypatch.setattr(cl, "_vraag_het_de_verkoper", _vraag)
    asyncio.run(cl.handle_item_sold("i1", "woocommerce", bewijs=None))
    assert afgemeld == ["vraag"] and _verwijderopdrachten(db) == []
    assert winkel.p["101"]["stock_status"] == "instock"
