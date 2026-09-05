"""Waarom Amanda dezelfde advertentie elke dag opnieuw online zag komen.

WAAROM DIT ER IS (05-09-2026, Amanda Haas)
"Hij blijft dezelfde advertenties er opnieuw opzetten." Nagemeten in haar
account: haar "AH hamster knuffel kok nieuw" stond met drie identieke
Marktplaats-advertenties tegelijk online (m2439045744, m2439067409,
m2439186265), elke dag kwam er eentje bij. In totaal drie artikelen met zes
overtollige advertenties, en zestien advertentierijen die dat elke zes uur
opnieuw zouden doen. Dat is precies het dubbel plaatsen waar Marktplaats
accounts voor blokkeert.

Het mechanisme, in drie stappen:

1. Herplaatsen zet de BESTAANDE rij op 'relisting' en laat het oude
   advertentienummer erop staan.
2. Kwam de nieuwe advertentie binnen, dan zocht `_rond_publicatie_af` een rij
   met dat nieuwe nummer (bestaat niet) of een rij zonder nummer (bestaat niet,
   want de oude rij hééft er een). Dus zette hij er een NIEUWE rij naast, en de
   oude bleef eeuwig op 'relisting' staan.
3. De reddingsronde leest 'relisting' als "halverwege blijven steken" en zette
   er elke zes uur weer een plaatsing voor klaar. Advertentie erbij. Elke ronde.

Elke test hieronder bewaakt één schakel. Ze falen alle vier op de oude code.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api          # noqa: E402
from backend.services import relist as rl    # noqa: E402


# ── Een minimale nabootsing van de Supabase-bouwer ───────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters = {}, {}
        self.op, self.velden, self.rijen_in = None, None, None

    def select(self, *_a, **_k):
        self.op = "select"; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def insert(self, rijen):
        self.op = "insert"
        self.rijen_in = rijen if isinstance(rijen, list) else [rijen]
        return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def in_(self, k, v):
        self.in_filters[k] = list(v); return self

    def lt(self, *_a):
        self.filters["__nooit__"] = object(); return self   # niets is "oud"

    def order(self, *_a, **_k):
        return self

    def limit(self, _n):
        return self

    def single(self):
        return self

    def _bron(self):
        return getattr(self.db, self.tabel)

    def _rijen(self):
        return [r for r in self._bron()
                if all(r.get(k) == v for k, v in self.filters.items())
                and all(r.get(k) in v for k, v in self.in_filters.items())]

    def execute(self):
        if self.op == "insert":
            for r in self.rijen_in:
                r.setdefault("id", f"{self.tabel}-{len(self._bron()) + 1}")
                self._bron().append(dict(r))
            return type("R", (), {"data": list(self.rijen_in)})()
        rijen = self._rijen()
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        if self.op == "select" and self.tabel == "items":
            return type("R", (), {"data": rijen[0] if rijen else None})()
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, listings=None, jobs=None, items=None):
        self.listings = listings or []
        self.jobs = jobs or []
        self.items = items or []

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture(autouse=True)
def _geen_echte_database(monkeypatch):
    async def direct(fn, *_a, **_k):
        return fn()
    monkeypatch.setattr(api, "naast_de_lus", direct)
    monkeypatch.setattr(rl, "naast_de_lus", direct)


def _uur_geleden(n):
    return (datetime.now(timezone.utc) - timedelta(hours=n)).isoformat()


# ── 1. De afronding werkt de rij bij die hij vervangt ────────────────────────

def test_geslaagde_herplaatsing_werkt_de_oude_rij_bij():
    """Zonder deze regel komt er een tweede rij bij en blijft de oude hangen."""
    db = _DB(listings=[
        {"id": "oud", "item_id": "it1", "platform": "marktplaats",
         "status": "relisting", "platform_listing_id": "m2399107387"},
    ])
    job = {"id": "j1", "item_id": "it1", "platform": "marktplaats",
           "payload": {"_vervangt_listing_id": "oud"}}
    asyncio.run(api._rond_publicatie_af(
        db, job, {"platform_listing_id": "m2439045744",
                  "platform_listing_url": "https://www.marktplaats.nl/x"}))

    assert len(db.listings) == 1, "er mag geen tweede advertentierij bijkomen"
    rij = db.listings[0]
    assert rij["id"] == "oud"
    assert rij["status"] == "active"
    assert rij["platform_listing_id"] == "m2439045744"


def test_zonder_merkteken_telt_de_enige_wachtende_rij():
    """Opdrachten die al in de wachtrij stonden hebben het merkteken nog niet."""
    db = _DB(listings=[
        {"id": "oud", "item_id": "it1", "platform": "marktplaats",
         "status": "relisting", "platform_listing_id": "m1"},
    ])
    job = {"id": "j1", "item_id": "it1", "platform": "marktplaats", "payload": {}}
    asyncio.run(api._rond_publicatie_af(
        db, job, {"platform_listing_id": "m2", "platform_listing_url": "u"}))
    assert len(db.listings) == 1
    assert db.listings[0]["platform_listing_id"] == "m2"


def test_bij_twee_wachtende_rijen_wordt_er_niet_gegokt():
    """Twee herplaatsingen tegelijk: dan liever een rij erbij dan de verkeerde
    advertentie overschrijven — een advertentie kwijtraken is erger."""
    db = _DB(listings=[
        {"id": "a", "item_id": "it1", "platform": "marktplaats",
         "status": "relisting", "platform_listing_id": "m1"},
        {"id": "b", "item_id": "it1", "platform": "marktplaats",
         "status": "relisting", "platform_listing_id": "m2"},
    ])
    job = {"id": "j1", "item_id": "it1", "platform": "marktplaats", "payload": {}}
    asyncio.run(api._rond_publicatie_af(
        db, job, {"platform_listing_id": "m3", "platform_listing_url": "u"}))
    assert len(db.listings) == 3
    assert {r["status"] for r in db.listings if r["id"] in ("a", "b")} == {"relisting"}


def test_een_lopende_advertentie_wordt_nooit_overschreven():
    """Alleen een rij die écht op zijn herplaatsing wacht mag worden bijgewerkt."""
    db = _DB(listings=[
        {"id": "live", "item_id": "it1", "platform": "marktplaats",
         "status": "active", "platform_listing_id": "m1"},
    ])
    job = {"id": "j1", "item_id": "it1", "platform": "marktplaats",
           "payload": {"_vervangt_listing_id": "live"}}
    asyncio.run(api._rond_publicatie_af(
        db, job, {"platform_listing_id": "m2", "platform_listing_url": "u"}))
    assert len(db.listings) == 2, "de lopende advertentie hoort te blijven staan"
    assert db.listings[0]["platform_listing_id"] == "m1"


# ── 2. De reddingsronde zet geen advertentie naast een geslaagde herplaatsing ─

def test_reddingsronde_sluit_een_al_geslaagde_herplaatsing_af():
    """Dit is de lus zelf: elke ronde een advertentie erbij."""
    db = _DB(
        listings=[
            {"id": "oud", "item_id": "it1", "platform": "marktplaats",
             "status": "relisting", "platform_listing_id": "m2399107387",
             "last_refreshed_at": _uur_geleden(30)},
            {"id": "nieuw", "item_id": "it1", "platform": "marktplaats",
             "status": "active", "platform_listing_id": "m2439045744",
             "listed_at": _uur_geleden(6)},
        ],
        jobs=[{"id": "d1", "item_id": "it1", "platform": "marktplaats",
               "action": "delete", "status": "done", "created_at": _uur_geleden(31)}],
        items=[{"id": "it1", "user_id": "u1", "title": "AH hamster knuffel kok nieuw"}],
    )
    uit = asyncio.run(rl.herstel_vastgelopen_werk_met_db(db)) if hasattr(
        rl, "herstel_vastgelopen_werk_met_db") else None
    if uit is None:
        import backend.database as bd
        oude = bd.get_db
        bd.get_db = lambda: db
        rl.get_db = lambda: db
        try:
            uit = asyncio.run(rl.herstel_vastgelopen_werk())
        finally:
            bd.get_db = oude

    nieuwe_plaatsingen = [j for j in db.jobs if j.get("action") == "create"]
    assert not nieuwe_plaatsingen, "er mag geen extra advertentie klaargezet worden"
    assert db.listings[0]["status"] == "delisted"
    assert uit.get("afgesloten") == 1


def test_reddingsronde_helpt_een_echt_vastgelopen_herplaatsing_nog_steeds():
    """De rem mag geen advertentie laten verdwijnen die er echt niet meer is."""
    db = _DB(
        listings=[
            {"id": "oud", "item_id": "it1", "platform": "marktplaats",
             "status": "relisting", "platform_listing_id": "m1",
             "last_refreshed_at": _uur_geleden(30)},
        ],
        jobs=[{"id": "d1", "item_id": "it1", "platform": "marktplaats",
               "action": "delete", "status": "done", "created_at": _uur_geleden(31)}],
        items=[{"id": "it1", "user_id": "u1", "title": "Vintage tafellamp",
                "description": "mooi", "price": 12.5, "photo_urls": ["p"]}],
    )
    import backend.database as bd
    oude = bd.get_db
    bd.get_db = lambda: db
    rl.get_db = lambda: db

    async def _lok(item, platform):
        return dict(item)
    import backend.services.crosslist as cl
    oude_lok, oude_slot, oude_met = cl.localize_item_for_platform, cl.slottekst_van, cl._met_slot
    cl.localize_item_for_platform = _lok
    cl.slottekst_van = lambda _u: ""
    cl._met_slot = lambda tekst, _s: tekst
    try:
        uit = asyncio.run(rl.herstel_vastgelopen_werk())
    finally:
        bd.get_db = oude
        cl.localize_item_for_platform = oude_lok
        cl.slottekst_van = oude_slot
        cl._met_slot = oude_met

    plaatsingen = [j for j in db.jobs if j.get("action") == "create"]
    assert len(plaatsingen) == 1, "een écht vastgelopen herplaatsing hoort geholpen te worden"
    assert plaatsingen[0]["payload"]["_vervangt_listing_id"] == "oud"
    assert uit.get("hersteld") == 1
