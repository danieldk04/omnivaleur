"""De herplaatslus: waarom hetzelfde artikel dagelijks opnieuw geplaatst werd.

WAAROM DIT ER IS (01-09-2026, Daniel over (1288) en (1314))
Twee artikelen waren op Marktplaats "voor mijn gevoel al super vaak gerelist",
terwijl ze allang verkocht waren. Nagemeten in de database: (1288) had zes
Marktplaats-rijen en 27 opdrachten, (1314) vijf rijen en zes herplaatsingen in
vier dagen — bij een instelling van 30 dagen.

Twee fouten grepen in elkaar:

1. Elke herplaatsing zet er een nieuwe advertentierij bij (de oude blijft staan
   als archief). Een verwijderopdracht werkte vervolgens ÉLKE rij van dat artikel
   op dat kanaal bij. Mislukte de verwijdering, dan gingen ze dus allemaal terug
   op 'actief' — inclusief de rij van juni, mét de datum van juni. Die was
   daarmee meteen weer over zijn termijn en werd de volgende ronde opnieuw
   opgepakt. Dat is de lus.

2. Was de advertentie al van Marktplaats af toen de extensie hem kwam weghalen,
   dan gold dat als "doel bereikt" en plaatste stap twee gewoon een nieuwe. Dat
   is precies wat er gebeurt bij een verkocht artikel: de verkoper haalt de
   advertentie zelf weg. Wij zetten hem dan opnieuw te koop — en merkten de
   verkoop nooit op.

Elke regel hieronder bewaakt één van die twee.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402


# ── Een minimale nabootsing van de Supabase-bouwer ───────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.in_filters, self.gte = {}, {}, None
        self.op, self.velden = None, None

    def select(self, *_a, **_k):
        self.op = "select"; return self

    def update(self, velden):
        self.op, self.velden = "update", velden; return self

    def eq(self, k, v):
        self.filters[k] = v; return self

    def in_(self, k, v):
        self.in_filters[k] = list(v); return self

    def gte(self, k, v):
        self.gte = (k, v); return self

    def limit(self, _n):
        return self

    def _rijen(self):
        bron = self.db.listings if self.tabel == "listings" else self.db.jobs
        uit = [r for r in bron
               if all(r.get(k) == v for k, v in self.filters.items())
               and all(r.get(k) in v for k, v in self.in_filters.items())]
        if self.gte:
            k, v = self.gte
            uit = [r for r in uit if str(r.get(k) or "") >= str(v)]
        return uit

    def execute(self):
        rijen = self._rijen()
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, listings, jobs=None):
        self.listings, self.jobs = listings, jobs or []

    def table(self, naam):
        return _Q(self, naam)


@pytest.fixture(autouse=True)
def _geen_echte_database(monkeypatch):
    """`naast_de_lus` zet werk in een aparte thread; hier draait alles gewoon."""
    async def direct(fn, *_a, **_k):
        return fn()
    monkeypatch.setattr(api, "naast_de_lus", direct)
    monkeypatch.setattr(api, "execute_with_retry", lambda q, *a, **k: q.execute())


def _dagen_geleden(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


def _verwijderopdracht(rij_id=None, nummer=None, platform="marktplaats"):
    payload = {}
    if rij_id:
        payload["_refresh_rollback"] = {"listing_id": rij_id}
    if nummer:
        payload["platform_listing_id"] = nummer
    return {"id": "job-1", "item_id": "it1", "platform": platform,
            "action": "delete", "payload": payload,
            "created_at": _dagen_geleden(0)}


# ── 1. Een verwijdering raakt alleen de advertentie die hij te pakken had ────

def test_de_opdracht_wijst_zijn_eigen_rij_aan():
    db = _DB([
        {"id": "oud", "item_id": "it1", "platform": "marktplaats",
         "status": "delisted", "listed_at": _dagen_geleden(65)},
        {"id": "nieuw", "item_id": "it1", "platform": "marktplaats",
         "status": "active", "listed_at": _dagen_geleden(31)},
    ])
    doelen = api._verwijderdoelen(db, _verwijderopdracht(rij_id="nieuw"))
    assert [d["id"] for d in doelen] == ["nieuw"]


def test_zonder_rij_id_telt_het_advertentienummer():
    db = _DB([
        {"id": "a", "item_id": "it1", "platform": "marktplaats",
         "status": "delisted", "platform_listing_id": "m1", "listed_at": _dagen_geleden(60)},
        {"id": "b", "item_id": "it1", "platform": "marktplaats",
         "status": "active", "platform_listing_id": "m2", "listed_at": _dagen_geleden(31)},
    ])
    doelen = api._verwijderdoelen(db, _verwijderopdracht(nummer="m2"))
    assert [d["id"] for d in doelen] == ["b"]


def test_zonder_enig_aanknopingspunt_blijven_de_eindstatussen_ongemoeid():
    """De terugval mag nooit een afgemelde of verkochte advertentie oppakken —
    dat is precies hoe de rij van juni telkens weer tot leven kwam."""
    db = _DB([
        {"id": "juni", "item_id": "it1", "platform": "marktplaats",
         "status": "delisted", "listed_at": _dagen_geleden(65)},
        {"id": "verkocht", "item_id": "it1", "platform": "marktplaats",
         "status": "sold", "listed_at": _dagen_geleden(40)},
        {"id": "gevraagd", "item_id": "it1", "platform": "marktplaats",
         "status": "sold_unconfirmed", "listed_at": _dagen_geleden(10)},
        {"id": "levend", "item_id": "it1", "platform": "marktplaats",
         "status": "active", "listed_at": _dagen_geleden(31)},
    ])
    doelen = api._verwijderdoelen(db, _verwijderopdracht())
    assert [d["id"] for d in doelen] == ["levend"]


def test_een_mislukte_verwijdering_zet_niet_alles_terug_op_actief():
    """De echte lus: één mislukte verwijdering zette vijf oude rijen terug op
    'actief' met hun oude datum, en die waren daarmee meteen weer aan de beurt."""
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text(encoding="utf-8")
    blok = bron.split('elif job and job["action"] == "delete":', 1)[1][:1600]
    assert "_verwijderdoelen(db, job)" in blok, "de mislukte verwijdering pakt weer alle rijen"
    assert '.eq("item_id", job["item_id"]).eq("platform", job["platform"])' not in blok


def test_een_geslaagde_verwijdering_meldt_alleen_zijn_eigen_advertentie_af():
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text(encoding="utf-8")
    blok = bron.split('elif job["action"] == "delete":', 1)[1][:2200]
    assert 'for rij in await naast_de_lus(lambda: _verwijderdoelen(db, job)):' in blok
    assert '.update({"status": "delisted"}).eq("item_id"' not in blok


# ── 2. "Hij was al weg" is geen geslaagde verwijdering ───────────────────────

def _al_weg(db, job):
    return asyncio.run(api._al_weg_voor_wij_er_waren(db, job))


def test_een_jonge_verdwenen_advertentie_wordt_een_verkoopvraag():
    """Marktplaats gooit een gratis advertentie pas na dertig dagen zelf weg. Is
    hij eerder verdwenen, dan heeft iemand hem weggehaald."""
    db = _DB(
        [{"id": "l1", "item_id": "it1", "platform": "marktplaats",
          "status": "active", "listed_at": _dagen_geleden(2)}],
        [{"id": "create-1", "item_id": "it1", "platform": "marktplaats",
          "action": "create", "status": "pending", "created_at": _dagen_geleden(0)}],
    )
    assert _al_weg(db, _verwijderopdracht(rij_id="l1")) is True
    assert db.listings[0]["status"] == "sold_unconfirmed"
    assert "te jong om vanzelf te verlopen" in db.listings[0]["error_message"]
    # En vooral: er komt géén nieuwe advertentie voor een verkocht artikel.
    assert db.jobs[0]["status"] == "cancelled"


def test_een_oude_verdwenen_advertentie_wordt_gewoon_herplaatst():
    """Ouder dan de termijn van Marktplaats: verlopen is dan de waarschijnlijke
    verklaring, en herplaatsen is precies waar het automatisme voor bestaat."""
    db = _DB(
        [{"id": "l1", "item_id": "it1", "platform": "marktplaats",
          "status": "active", "listed_at": _dagen_geleden(40)}],
        [{"id": "create-1", "item_id": "it1", "platform": "marktplaats",
          "action": "create", "status": "pending", "created_at": _dagen_geleden(0)}],
    )
    assert _al_weg(db, _verwijderopdracht(rij_id="l1")) is False
    assert db.listings[0]["status"] == "active"
    assert db.jobs[0]["status"] == "pending"


def test_zonder_plaatsingsdatum_wordt_er_niets_geconcludeerd():
    """Geen datum betekent geen leeftijd, en dus geen grond voor een verkoopvraag."""
    db = _DB([{"id": "l1", "item_id": "it1", "platform": "marktplaats",
               "status": "active", "listed_at": None}])
    assert _al_weg(db, _verwijderopdracht(rij_id="l1")) is False
    assert db.listings[0]["status"] == "active"


def test_vinted_valt_hier_buiten():
    """Op Vinted verloopt niets vanzelf; die heeft zijn eigen verkoopherkenning
    (is_closed) en mag hier niet doorheen glippen."""
    db = _DB([{"id": "l1", "item_id": "it1", "platform": "vinted",
               "status": "active", "listed_at": _dagen_geleden(2)}])
    assert _al_weg(db, _verwijderopdracht(rij_id="l1", platform="vinted")) is False


def test_een_al_bevestigde_verkoop_wordt_niet_opnieuw_bevraagd():
    db = _DB([{"id": "l1", "item_id": "it1", "platform": "marktplaats",
               "status": "sold", "listed_at": _dagen_geleden(2)}])
    assert _al_weg(db, _verwijderopdracht(rij_id="l1")) is False
    assert db.listings[0]["status"] == "sold"


def test_de_grens_ligt_onder_de_termijn_van_marktplaats():
    """Marktplaats gooit na dertig dagen weg; onze grens moet daaronder liggen,
    anders noemen we een verlopen advertentie een verkoop."""
    assert api.ZELF_VERLOPEN_NA_DAGEN < 30


def test_de_verwijdering_vraagt_het_pas_bij_een_al_afwezige_advertentie():
    """Alleen op het merkteken dat de extensie zet als de advertentie er al niet
    meer was. Bij een échte verwijdering door ons klopt afwezigheid gewoon."""
    bron = (ROOT / "backend" / "api" / "jobs.py").read_text(encoding="utf-8")
    assert 'if body.get("note") == "already_absent" and await _al_weg_voor_wij_er_waren(db, job):' in bron
    assert 'note: "already_absent"' in (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
