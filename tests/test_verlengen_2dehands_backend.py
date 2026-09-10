"""De serverkant van automatisch verlengen op 2dehands (10-09-2026).

Twee dingen die de oude code NIET deed en die geld of advertenties kosten als
ze fout gaan:

1. `extend_expiring_2dehands` zet een 'extend'-opdracht klaar en NOOIT een
   'delete'. Verlengen is weghalen noch opnieuw plaatsen (zie
   docs/kennisbank.md "herplaatsen-verliest-advertenties"). Een verkocht of
   uitgezet zoekertje wordt met rust gelaten.
2. `complete_job` schuift `listed_at` alleen mee mét bewijs dat de vervaldatum
   echt ~4 weken verder ligt, en zet de advertentierij NOOIT op 'delisted' of
   'relisting' (zie "succes-nooit-uit-uitsluitingslijst").

De voor-proef staat in tests/verlengen-2dehands-test.js (commit a3d3083c): daar
kende de code 'extend' niet en zou de opdracht naar het plaatsformulier zijn
gegaan.

Draaien:  python3 -m pytest tests/test_verlengen_2dehands_backend.py -q
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services import crosslist as cl          # noqa: E402
from backend.api import jobs as jobsapi               # noqa: E402


# ── Een minimale Supabase-bouwer ────────────────────────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.eqs, self.ins = {}, {}
        self.gtes, self.ltes = {}, {}
        self.op = "select"
        self.velden = None
        self.rijen_in = None
        self._desc = False
        self._n = None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def insert(self, rows):
        self.op = "insert"
        self.rijen_in = rows if isinstance(rows, list) else [rows]
        return self
    def eq(self, k, v): self.eqs[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def gte(self, k, v): self.gtes[k] = v; return self
    def lte(self, k, v): self.ltes[k] = v; return self
    def order(self, _k, desc=False, **_kw): self._desc = desc; return self
    def limit(self, n): self._n = n; return self

    def _match(self, r):
        return (all(r.get(k) == v for k, v in self.eqs.items())
                and all(r.get(k) in v for k, v in self.ins.items())
                and all(str(r.get(k) or "") >= str(v) for k, v in self.gtes.items())
                and all(str(r.get(k) or "") <= str(v) for k, v in self.ltes.items()))

    def execute(self):
        bron = getattr(self.db, self.tabel)
        if self.op == "insert":
            for r in self.rijen_in:
                r.setdefault("id", f"{self.tabel}-{len(bron) + 1}")
                r.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                bron.append(dict(r))
            return type("R", (), {"data": list(self.rijen_in)})()
        rijen = [r for r in bron if self._match(r)]
        rijen.sort(key=lambda r: str(r.get("created_at") or r.get("listed_at") or ""),
                   reverse=self._desc)
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
            return type("R", (), {"data": rijen})()
        if self._n:
            rijen = rijen[: self._n]
        return type("R", (), {"data": rijen})()


class _DB:
    def __init__(self, **tabellen):
        self.listings = tabellen.get("listings", [])
        self.jobs = tabellen.get("jobs", [])
        self.items = tabellen.get("items", [])
    def table(self, naam): return _Q(self, naam)


@pytest.fixture(autouse=True)
def _harnas(monkeypatch):
    async def direct(fn, *_a, **_k):
        return fn()
    monkeypatch.setattr(cl, "naast_de_lus", direct)
    monkeypatch.setattr(jobsapi, "naast_de_lus", direct)
    import backend.services.instellingen as inst
    monkeypatch.setattr(inst, "lees", lambda uid: {"auto_relist": _AUTO.get(uid, True)})


_AUTO: dict = {}


def _oud(dagen):
    return (datetime.now(timezone.utc) - timedelta(days=dagen)).isoformat()


def _draai_inplan(db):
    import backend.database as bd
    bd_get = bd.get_db
    cl.get_db = lambda: db
    try:
        asyncio.run(cl.extend_expiring_2dehands())
    finally:
        cl.get_db = bd_get


# ── 1. Een bijna verlopen zoekertje → precies één 'extend', nul 'delete' ────

def test_bijna_verlopen_zoekertje_krijgt_een_extend_en_geen_delete():
    db = _DB(
        listings=[{"id": "L1", "item_id": "it1", "platform": "2dehands",
                   "status": "active", "listed_at": _oud(26),
                   "platform_listing_id": "m2431571489",
                   "platform_listing_url": "https://www.2dehands.be/v/x/m2431571489"}],
        items=[{"id": "it1", "user_id": "u1"}],
    )
    _draai_inplan(db)

    assert len(db.jobs) == 1, "er hoort precies één opdracht te komen"
    job = db.jobs[0]
    assert job["action"] == "extend"
    assert job["platform"] == "2dehands"
    assert job["item_id"] == "it1"
    assert job["payload"]["_listing_row_id"] == "L1"
    assert not any(j["action"] == "delete" for j in db.jobs), "NOOIT weghalen bij verlengen"
    # de advertentierij is niet aangeraakt
    assert db.listings[0]["status"] == "active"


# ── 2. Nog te jong of te oud → niets ──────────────────────────────────────

def test_buiten_het_venster_gebeurt_er_niets():
    db = _DB(
        listings=[
            {"id": "L_jong", "item_id": "a", "platform": "2dehands",
             "status": "active", "listed_at": _oud(5)},
            {"id": "L_oud", "item_id": "b", "platform": "2dehands",
             "status": "active", "listed_at": _oud(120)},
        ],
        items=[{"id": "a", "user_id": "u1"}, {"id": "b", "user_id": "u1"}],
    )
    _draai_inplan(db)
    assert db.jobs == []


# ── 3. Verkocht of auto_relist uit → met rust laten ──────────────────────

def test_verkocht_zoekertje_wordt_niet_verlengd():
    db = _DB(
        listings=[
            {"id": "L1", "item_id": "it1", "platform": "2dehands",
             "status": "active", "listed_at": _oud(26)},
            {"id": "Lv", "item_id": "it1", "platform": "vinted", "status": "sold"},
        ],
        items=[{"id": "it1", "user_id": "u1"}],
    )
    _draai_inplan(db)
    assert db.jobs == []


def test_auto_relist_uit_betekent_geen_verlenging():
    _AUTO["u2"] = False
    db = _DB(
        listings=[{"id": "L1", "item_id": "it1", "platform": "2dehands",
                   "status": "active", "listed_at": _oud(26)}],
        items=[{"id": "it1", "user_id": "u2"}],
    )
    _draai_inplan(db)
    assert db.jobs == []
    _AUTO.pop("u2", None)


# ── 4. Geen tweede opdracht als er al een loopt ──────────────────────────

def test_geen_dubbele_extend_opdracht():
    db = _DB(
        listings=[{"id": "L1", "item_id": "it1", "platform": "2dehands",
                   "status": "active", "listed_at": _oud(26)}],
        items=[{"id": "it1", "user_id": "u1"}],
        jobs=[{"id": "bestaand", "user_id": "u1", "item_id": "it1", "platform": "2dehands",
               "action": "extend", "status": "pending",
               "created_at": datetime.now(timezone.utc).isoformat()}],
    )
    _draai_inplan(db)
    assert len(db.jobs) == 1, "de bestaande opdracht blijft de enige"


# ── 5. complete_job: alleen mét bewijs schuift listed_at, nooit de status ─

def _voltooi(db, job, body):
    import backend.database as bd
    bd_get = bd.get_db
    jobsapi.get_db = lambda: db
    monkey_heartbeat = getattr(jobsapi, "_record_extension_heartbeat")
    jobsapi._record_extension_heartbeat = lambda *a, **k: None
    try:
        return asyncio.run(jobsapi.complete_job(job["id"], body, user_id=job["user_id"]))
    finally:
        jobsapi.get_db = bd_get
        jobsapi._record_extension_heartbeat = monkey_heartbeat


def test_complete_job_schuift_listed_at_alleen_met_bewijs():
    oud = _oud(27)
    db = _DB(
        listings=[{"id": "L1", "item_id": "it1", "platform": "2dehands",
                   "status": "active", "listed_at": oud}],
        jobs=[{"id": "j1", "user_id": "u1", "item_id": "it1", "platform": "2dehands",
               "action": "extend", "status": "claimed",
               "payload": {"_listing_row_id": "L1"}}],
    )
    _voltooi(db, db.jobs[0],
             {"verlengd": True, "note": "extended",
              "old_close": "2026-09-13T12:47:37Z", "new_close": "2026-10-11T12:47:37Z"})

    rij = db.listings[0]
    assert rij["listed_at"] != oud, "listed_at hoort mee te schuiven"
    assert rij["status"] == "active", "de status blijft active — nooit delisted/relisting"


def test_complete_job_zonder_bewijs_laat_listed_at_staan():
    oud = _oud(27)
    db = _DB(
        listings=[{"id": "L1", "item_id": "it1", "platform": "2dehands",
                   "status": "active", "listed_at": oud}],
        jobs=[{"id": "j1", "user_id": "u1", "item_id": "it1", "platform": "2dehands",
               "action": "extend", "status": "claimed",
               "payload": {"_listing_row_id": "L1"}}],
    )
    # "niet in het verlengvenster" — geen verlengd:true, geen new_close
    _voltooi(db, db.jobs[0], {"note": "not_in_extend_window"})

    rij = db.listings[0]
    assert rij["listed_at"] == oud, "zonder bewijs verandert er niets"
    assert rij["status"] == "active"
