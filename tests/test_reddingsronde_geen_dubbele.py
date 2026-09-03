"""Een herplaatsing waarvan het weghalen nooit lukte mag niet kaal opnieuw
worden geplaatst.

WAAROM DIT ER IS (03-09-2026, Toon / De Juiste Toon). Om 02:34 zette de
nachtronde voor drie kelims een verwijdering plus een plaatsing klaar. Toon
annuleerde ze zelf. De verwijdering liep dus nooit: de oude advertenties staan
gewoon nog op Marktplaats. Maar de advertentierij bleef op 'relisting' staan, en
om 17:44 zag de reddingsronde "relisting zonder plaatsopdracht" en zette voor
alle drie een kale plaatsopdracht klaar. Zodra zijn extensie die oppakt staat
elke kelim er twee keer op.

Hetzelfde patroon bij twee andere verkopers via de driedagenveger: verwijdering
én plaatsing verlopen, rij blijft 'relisting', reddingsronde plaatst kaal
opnieuw terwijl de oude advertentie live staat (gemeten: HTTP 200 op de oude
advertentie-URL, 03-09-2026).

De regel is nu: alleen als het weghalen aantoonbaar is afgerond ('done') komt er
een nieuwe plaatsing. Anders wordt de herplaatsing teruggenomen: advertentie
terug op 'active' met uitleg, plaatsopdrachten geannuleerd, verversbeurt
teruggegeven.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import jobs as api  # noqa: E402
from backend.services import relist  # noqa: E402
import backend.database as database  # noqa: E402


class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.filters, self.ins, self.lt_, self.gte_, self.lte_ = {}, {}, None, None, None
        self.op, self.velden, self.is_single = None, None, False
        self.desc = False

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, velden): self.op, self.velden = "update", velden; return self
    def insert(self, velden): self.op, self.velden = "insert", velden; return self
    def eq(self, k, v): self.filters[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def lt(self, k, v): self.lt_ = (k, v); return self
    def gte(self, k, v): self.gte_ = (k, v); return self
    def lte(self, k, v): self.lte_ = (k, v); return self
    def order(self, *_a, desc=False, **_k): self.desc = desc; return self
    def limit(self, _n): return self
    def single(self): self.is_single = True; return self

    def execute(self):
        bron = self.db.tabellen.setdefault(self.tabel, [])
        if self.op == "insert":
            rij = dict(self.velden, id=f"nieuw-{len(bron)}")
            bron.append(rij)
            self.db.ingevoegd.append(rij)
            return type("R", (), {"data": [rij]})()
        rijen = [r for r in bron if all(r.get(k) == v for k, v in self.filters.items())
                 and all(r.get(k) in v for k, v in self.ins.items())]
        for grens, oper in ((self.lt_, lambda a, b: a < b), (self.gte_, lambda a, b: a >= b),
                            (self.lte_, lambda a, b: a <= b)):
            if grens:
                k, v = grens
                rijen = [r for r in rijen if oper(str(r.get(k) or ""), str(v))]
        rijen.sort(key=lambda r: str(r.get("created_at") or ""), reverse=self.desc)
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        data = rijen[0] if self.is_single else rijen
        return type("R", (), {"data": data})()


class _DB:
    def __init__(self, listings, jobs, items):
        self.tabellen = {"listings": listings, "jobs": jobs, "items": items}
        self.ingevoegd = []

    def table(self, naam):
        return _Q(self, naam)


NU = datetime.now(timezone.utc)
ITEM = {"id": "item-1", "user_id": "toon", "title": "Kelim loper", "description": "x",
        "photo_urls": ["a"], "price": 10}
ROLLBACK = {"listing_id": "rij-1", "prior_last_refreshed_at": "2026-08-01T00:00:00+00:00",
            "prior_refresh_count": 2, "day": "2026-09-03"}


def _job(jid, actie, status, oud_uren=1, sched=False, rollback=False):
    t = (NU - timedelta(hours=oud_uren)).isoformat()
    return {"id": jid, "user_id": "toon", "item_id": "item-1", "platform": "marktplaats",
            "action": actie, "status": status, "created_at": t,
            "scheduled_for": (NU + timedelta(hours=2)).isoformat() if sched else None,
            "payload": {"_refresh_rollback": ROLLBACK} if rollback else {"title": "Kelim loper"},
            "result": None}


@pytest.fixture
def opzet(monkeypatch):
    def maak(jobs, status="relisting"):
        db = _DB([{"id": "rij-1", "item_id": "item-1", "platform": "marktplaats",
                   "status": status, "platform_listing_id": "m1", "listed_at": "2026-08-01T00:00:00+00:00",
                   "last_refreshed_at": NU.isoformat(), "refresh_count": 3, "error_message": None}],
                 jobs, [dict(ITEM)])
        monkeypatch.setattr(relist, "get_db", lambda: db)
        monkeypatch.setattr(database, "get_db", lambda: db)
        monkeypatch.setattr(api, "get_db", lambda: db)
        monkeypatch.setattr(api, "execute_with_retry", lambda q, *a, **k: q.execute())
        monkeypatch.setattr(relist, "_met_fabrikant", lambda item, platform, uid: dict(item))
        return db
    return maak


def _rij(db):
    return db.tabellen["listings"][0]


def _plaatsingen(db):
    return [j for j in db.ingevoegd if j.get("action") == "create"]


def test_toon_geannuleerde_verwijdering_wordt_niet_kaal_opnieuw_geplaatst(opzet):
    db = opzet([_job("d1", "delete", "cancelled", rollback=True),
                _job("c1", "create", "cancelled", sched=True)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert _plaatsingen(db) == [], "kale plaatsing naast een advertentie die nog online staat"
    assert _rij(db)["status"] == "active"
    assert "still live" in (_rij(db)["error_message"] or "")
    assert _rij(db)["last_refreshed_at"] == ROLLBACK["prior_last_refreshed_at"]


def test_reeds_klaargezette_kale_plaatsing_wordt_ingetrokken(opzet):
    """Toons echte toestand vanavond: de kale plaatsing stond al in de rij."""
    db = opzet([_job("d1", "delete", "cancelled", oud_uren=15, rollback=True),
                _job("c1", "create", "cancelled", oud_uren=15, sched=True),
                _job("c2", "create", "pending", oud_uren=1)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    kaal = next(j for j in db.tabellen["jobs"] if j["id"] == "c2")
    assert kaal["status"] == "cancelled"
    assert _rij(db)["status"] == "active"
    assert _plaatsingen(db) == []


def test_verlopen_verwijdering_zet_advertentie_terug_in_plaats_van_kaal_plaatsen(opzet):
    """Het patroon van de driedagenveger: verwijdering én plaatsing verlopen."""
    db = opzet([_job("d1", "delete", "error", oud_uren=24 * 9, rollback=True),
                _job("c1", "create", "error", oud_uren=24 * 9, sched=True)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert _plaatsingen(db) == []
    assert _rij(db)["status"] == "active"


def test_afgeronde_verwijdering_krijgt_wel_een_nieuwe_plaatsing(opzet):
    """De oude weg blijft: is de oude advertentie echt weg, dan moet er een nieuwe komen."""
    db = opzet([_job("d1", "delete", "done", rollback=True),
                _job("c1", "create", "error", sched=True)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert len(_plaatsingen(db)) == 1
    assert _rij(db)["status"] == "relisting"


def test_lopende_verwijdering_blijft_met_rust(opzet):
    db = opzet([_job("d1", "delete", "pending", rollback=True),
                _job("c1", "create", "pending", sched=True)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    assert _plaatsingen(db) == []
    assert _rij(db)["status"] == "relisting"
    assert all(j["status"] == "pending" for j in db.tabellen["jobs"])


def test_driedagenveger_neemt_verlopen_herplaatsing_terug(opzet):
    db = opzet([_job("d1", "delete", "pending", oud_uren=24 * 4, rollback=True),
                _job("c1", "create", "pending", oud_uren=24 * 4, sched=True)])
    asyncio.run(relist.herstel_vastgelopen_werk())
    statussen = {j["id"]: j["status"] for j in db.tabellen["jobs"] if j["id"] in ("d1", "c1")}
    assert statussen == {"d1": "cancelled", "c1": "cancelled"}
    assert _rij(db)["status"] == "active"
    assert _plaatsingen(db) == []


def test_annuleren_van_verwijdering_zet_advertentie_meteen_terug(opzet):
    db = opzet([_job("d1", "delete", "pending", rollback=True),
                _job("c1", "create", "pending", sched=True)])
    uit = api.cancel_job.__wrapped__("d1", "toon") if hasattr(api.cancel_job, "__wrapped__") \
        else api.cancel_job("d1", "toon")
    assert uit["status"] == "cancelled"
    statussen = {j["id"]: j["status"] for j in db.tabellen["jobs"]}
    assert statussen == {"d1": "cancelled", "c1": "cancelled"}
    assert _rij(db)["status"] == "active"
    assert _rij(db)["last_refreshed_at"] == ROLLBACK["prior_last_refreshed_at"]
