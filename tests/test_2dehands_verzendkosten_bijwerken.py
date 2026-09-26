"""Verzendkosten van een zoekertje dat al op 2dehands staat: wie krijgt dit werk?

Zie tests/2dehands-verzendkosten-bijwerken-test.js voor wat de extensie doet en
wat er live is nagemeten. Hier: de uitgifte. Een kopie onder 1.0.354 zou het
hele plaatsformulier opnieuw invullen (1.0.353) of de opdracht als mislukt melden
(ouder), dus die krijgt dit werk nooit. En mislukt de laatste, dan wacht de rest:
bij Egbert stonden er 116 klaar.
"""
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import backend.api.jobs as J

ROOT = Path(__file__).resolve().parents[1]
USER = "bcdf9aa4-314d-49a2-9573-8818ad61073d"


def _tijd(minuten_geleden: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten_geleden)).isoformat()


def _bijwerking(jid="j1"):
    return {"id": jid, "user_id": USER, "item_id": "it1", "platform": "2dehands",
            "action": "content_refresh", "status": "pending", "created_at": _tijd(5),
            "claimed_at": None, "done_at": None, "scheduled_for": None,
            "payload": {"platform_listing_id": "m2446754373", "_verzending_bijwerken": True,
                        "verzending": {"soort": "zelf", "cents": 495}}}


def _db(wachtend, afgerond=()):
    class _Vraag:
        def __init__(self, t):
            self.t, self.soort, self.f = t, "select", {}

        def select(self, *a, **k):
            return self

        def update(self, v):
            self.soort = "update"
            return self

        def eq(self, k, v):
            self.f[k] = v
            return self

        def in_(self, k, v):
            self.f[k] = list(v)
            return self

        def __getattr__(self, _n):
            return lambda *a, **k: self

        @property
        def not_(self):
            return self

        def execute(self):
            data = []
            if self.t == "jobs" and self.soort == "select":
                status = self.f.get("status")
                if status == "pending":
                    data = list(wachtend)
                elif isinstance(status, list) and "error" in status:
                    data = list(afgerond)
                elif "id" in self.f:
                    ids = self.f["id"] if isinstance(self.f["id"], list) else [self.f["id"]]
                    data = [j for j in wachtend if j["id"] in ids]
            elif self.t == "items":
                data = [{"id": "it1", "user_id": USER, "title": "t", "sku": None, "brand": None}]
            return type("R", (), {"data": data})()

    return type("Db", (), {"table": lambda self, n: _Vraag(n)})()


def _uitgifte(monkeypatch, db, versie):
    monkeypatch.setattr(J, "get_db", lambda: db)
    for naam in ("_record_extension_heartbeat", "_recover_stale_claims"):
        monkeypatch.setattr(J, naam, lambda *a, **k: None)
    monkeypatch.setattr(J, "_gepubliceerde_extensieversie", lambda: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda r: None)
    monkeypatch.setattr(J, "_zet_taal_goed", lambda db, js: list(js))
    monkeypatch.setattr(J, "_haal_links_eruit", lambda db, js: 0)
    return J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": versie}})(),
        platform="2dehands", user_id=USER)


@pytest.mark.parametrize("versie,uitgedeeld", [
    ("1.0.352", False),   # kent geen wijzigadres voor 2dehands
    ("1.0.353", False),   # zou het plaatsformulier opnieuw invullen
    ("1.0.354", True),
])
def test_alleen_naar_een_kopie_die_het_kan(monkeypatch, versie, uitgedeeld):
    uit = _uitgifte(monkeypatch, _db([_bijwerking()]), versie)
    assert bool(uit) == uitgedeeld, f"{versie}: {uit}"
    if uitgedeeld:
        assert uit[0]["payload"]["verzending"] == {"soort": "zelf", "cents": 495}


def test_na_een_mislukking_wacht_de_rest(monkeypatch):
    afgerond = [
        {"status": "done", "created_at": _tijd(60), "claimed_at": _tijd(30), "done_at": _tijd(29)},
        {"status": "error", "created_at": _tijd(60), "claimed_at": _tijd(20), "done_at": _tijd(19)},
    ]
    assert _uitgifte(monkeypatch, _db([_bijwerking()], afgerond), "1.0.354") == []


def test_telt_wat_het_laatst_afliep_niet_wat_het_laatst_klaarstond(monkeypatch):
    """Een reeks wordt in één seconde aangemaakt en loopt daarna een voor een af."""
    zelfde = _tijd(60)
    afgerond = [
        {"status": "error", "created_at": zelfde, "claimed_at": _tijd(40), "done_at": _tijd(39)},
        {"status": "done", "created_at": zelfde, "claimed_at": _tijd(10), "done_at": _tijd(9)},
    ]
    assert len(_uitgifte(monkeypatch, _db([_bijwerking()], afgerond), "1.0.354")) == 1


def test_de_noodrem_raakt_geen_plaatsingen(monkeypatch):
    plaatsing = {**_bijwerking("p1"), "action": "create",
                 "payload": {"title": "Patch", "price": 11.95, "verzending": {"soort": "onbekend"}}}
    afgerond = [{"status": "error", "created_at": _tijd(9), "claimed_at": _tijd(9), "done_at": _tijd(8)}]
    uit = _uitgifte(monkeypatch, _db([plaatsing], afgerond), "1.0.354")
    assert [j["id"] for j in uit] == ["p1"]


def test_de_extensie_zelf():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is niet geïnstalleerd")
    r = subprocess.run([node, str(ROOT / "tests" / "2dehands-verzendkosten-bijwerken-test.js")],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


# ── na een plaatsing zonder eigen bedrag: alsnog bijwerken ───────────────────
class _Opname:
    """Onthoudt wat er in de jobs-tabel gezet wordt; 'al' = er wacht er al een."""

    def __init__(self, al=False):
        self.al, self.ingevoegd = al, []

    def table(self, _naam):
        opname = self

        class _V:
            def insert(self, rij):
                opname.ingevoegd.append(rij)
                return self

            def __getattr__(self, _n):
                return lambda *a, **k: self

            def execute(self):
                return type("R", (), {"data": [{"id": "x"}] if opname.al else []})()
        return _V()


def _plaatsing(verzending):
    return {"id": "p1", "user_id": USER, "item_id": "it1", "platform": "2dehands", "action": "create",
            "payload": {"title": "Metallica - Skulls - Rugpatch", "verzending": verzending}}


ANTWOORD = {"platform_listing_id": "m2446754373",
            "platform_listing_url": "https://www.2dehands.be/seller/view/m2446754373"}


def test_oude_kopie_plaatste_met_bpost_dan_komt_er_een_bijwerking():
    db = _Opname()
    J._verzending_alsnog_bijwerken(db, _plaatsing({"soort": "zelf", "cents": 495}), ANTWOORD)
    assert len(db.ingevoegd) == 1
    rij = db.ingevoegd[0]
    assert (rij["action"], rij["platform"], rij["status"]) == ("content_refresh", "2dehands", "pending")
    assert rij["payload"]["_verzending_bijwerken"] is True
    assert rij["payload"]["verzending"] == {"soort": "zelf", "cents": 495}
    assert rij["payload"]["platform_listing_id"] == "m2446754373"


def test_geen_bijwerking_als_het_bedrag_er_al_stond_of_niet_hoorde():
    for verzending, antwoord in (
        ({"soort": "zelf", "cents": 495}, {**ANTWOORD, "verzending_gezet": True}),
        ({"soort": "platform"}, ANTWOORD),
        ({"soort": "onbekend"}, ANTWOORD),
        ({"soort": "zelf", "cents": 495}, {}),              # geen zoekertje, niets bij te werken
    ):
        db = _Opname()
        J._verzending_alsnog_bijwerken(db, _plaatsing(verzending), antwoord)
        assert db.ingevoegd == [], (verzending, antwoord)
    db = _Opname(al=True)
    J._verzending_alsnog_bijwerken(db, _plaatsing({"soort": "zelf", "cents": 495}), ANTWOORD)
    assert db.ingevoegd == [], "er wacht er al een: geen tweede"
