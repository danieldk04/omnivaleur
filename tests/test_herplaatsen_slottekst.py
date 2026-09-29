"""Herplaatsen zet de vaste slottekst van de verkoper onder de advertentie.

GEMETEN 29-09-2026, Zilverwebsite. Van de eerste 26 herplaatsingen op Marktplaats
kwamen er 26 online zonder de vaste tekst onder de advertentie. refresh_listing
zette de vertaalde tekst rechtstreeks in de plaatsopdracht; alleen publiceren en
de reddingsronde voegden de slottekst toe. Het ging alleen goed als de tekst in
het dashboard hem al bevatte, en bij aangevulde teksten (uit de webshop) is dat
niet zo.

Draaien: python3 -m pytest tests/test_herplaatsen_slottekst.py
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.services import crosslist
from backend.services import photo_mirror  # noqa: F401
from backend.services import relist as R

SLOT = "Wordt zorgvuldig ingepakt en GRATIS verzonden.\n\nPassie voor antiek zilver."
TEKST = "Zilveren geboortelepel met Caritas als bekroning.\n\nGewicht: 48,6 gram."
OUD = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()

ITEM = {"id": "i1", "user_id": "u1", "title": "Zilveren geboortelepel", "description": TEKST,
        "price": 100.0, "photo_urls": ["https://img.omnivaleur.com/u/1.jpg"], "sku": "IMP-1"}
LISTING = {"id": "l1", "item_id": "i1", "platform": "marktplaats", "status": "active",
           "platform_listing_id": "m1", "platform_listing_url": "https://www.marktplaats.nl/m1",
           "listed_at": OUD, "created_at": OUD, "last_refreshed_at": None, "refresh_count": 0,
           "reserved": False}


class _DB:
    """Een database die op elke vraag het bekende antwoord geeft en schrijfacties onthoudt."""
    def __init__(self, item):
        self.item = item
        self.ingevoegd = []

    def table(self, naam):
        db = self

        class Q:
            op = "select"
            def __getattr__(self, _n):
                return lambda *a, **k: self
            def insert(self, rij, **_k): self.op = "insert"; db.ingevoegd.append((naam, rij)); self.rij = rij; return self
            def update(self, *_a, **_k): self.op = "update"; return self
            def delete(self, *_a, **_k): self.op = "delete"; return self
            def single(self): return self
            def maybe_single(self): return self
            def execute(self):
                if self.op == "insert":
                    return SimpleNamespace(data=[self.rij], count=0)
                if self.op != "select":
                    return SimpleNamespace(data=[{}], count=0)
                data = {"items": [db.item], "listings": [LISTING]}.get(naam, [])
                return SimpleNamespace(data=data, count=0)
        return Q()


@pytest.fixture
def opzet(monkeypatch):
    async def vertaling(item, platform):
        return dict(item)
    monkeypatch.setattr(crosslist, "localize_item_for_platform", vertaling)
    monkeypatch.setattr(crosslist, "slottekst_van", lambda uid: SLOT)

    def maak(item=None):
        db = _DB(dict(item or ITEM))
        monkeypatch.setattr(R, "get_db", lambda: db)
        return db
    return maak


def _create(db):
    return next(r for t, r in db.ingevoegd if t == "jobs" and r.get("action") == "create")


def test_helper_zet_slottekst_onder_marktplaats(opzet):
    opzet()
    uit = R._met_slottekst({"title": "t", "description": TEKST}, "marktplaats", "u1")
    assert uit["description"].endswith(SLOT)
    assert uit["description"].startswith(TEKST)


def test_helper_zet_hem_niet_dubbel(opzet):
    opzet()
    al = TEKST + "\n\n" + SLOT
    assert R._met_slottekst({"title": "t", "description": al}, "marktplaats", "u1")["description"] == al


def test_helper_ebay_zonder_slottekst(opzet):
    opzet()
    uit = R._met_slottekst({"title": "t", "description": TEKST + "\n\n" + SLOT}, "ebay", "u1")
    assert "zorgvuldig" not in uit["description"]


def test_helper_haalt_webadressen_uit_marktplaats_maar_niet_uit_vinted(opzet):
    opzet()
    tekst = "Zie www.zilverwebsite.nl voor meer."
    assert "zilverwebsite.nl" not in R._met_slottekst({"title": "t", "description": tekst}, "marktplaats", "u1")["description"]


def test_herplaatsing_draagt_de_slottekst_mee(opzet):
    """De echte refresh_listing, tot en met de opdracht die naar de extensie gaat."""
    db = opzet()
    asyncio.run(R.refresh_listing("i1", "marktplaats", "u1", "relist"))
    beschrijving = _create(db)["payload"]["description"]
    assert beschrijving.startswith(TEKST)
    assert SLOT in beschrijving
