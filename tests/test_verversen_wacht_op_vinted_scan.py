"""Blijft een Vinted-verversing wachten zolang de leesronde daar bezig is?

WAAROM DIT ER IS (06-09-2026, Daniel)

"Ik kreeg net de melding op Vinted 'you are rate limited' bij de relist functie,
waardoor er een relist faalde." Nagemeten in zijn eigen opdrachten:

  06:49:11  Vinted-scan klaargezet (na twee mislukte publicaties van gisteren)
  06:50:07  scan geclaimd, loopt 365 advertenties af
  07:11:39  verversing geclaimd — MIDDEN in die scan
  07:11:58  "No tab with id" — het tabblad was weg, de advertentie bleef staan
  07:13:57  de scan meldt nog steeds vordering (342 van 365)

Twee stromen verzoeken naar dezelfde Vinted-sessie tegelijk. Vinted knijpt die
sessie dan af. De uitgifte houdt verversingen daarom tegen zolang er een Vinted
-scan loopt; publiceren waar de verkoper zelf op drukte gaat gewoon door.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402

NU = datetime.now(timezone.utc)


def _job(jid, actie, payload=None, ingepland=False, minuten_geleden=10):
    return {
        "id": jid,
        "user_id": "u1",
        "item_id": "item-" + jid,
        "platform": "vinted",
        "action": actie,
        "status": "pending",
        "payload": payload if payload is not None else {"price": 20},
        "created_at": (NU - timedelta(minutes=minuten_geleden)).isoformat(),
        "claimed_at": None,
        "done_at": None,
        "scheduled_for": (NU - timedelta(minutes=1)).isoformat() if ingepland else None,
    }


def _scan_in_de_lucht(seconden_geleden=20):
    """Zoals hij in de database stond toen het misging."""
    return {
        "action": "scan",
        "platform": "vinted",
        "claimed_at": (NU - timedelta(minutes=25)).isoformat(),
        "result": {"_progress": {
            "at": (NU - timedelta(seconds=seconden_geleden)).isoformat(),
            "stage": "enriching", "current": 342, "total": 365}},
    }


def _bouw_db(wachtrij, geclaimd):
    op_id = {j["id"]: j for j in wachtrij}

    class _B:
        def __init__(self, tabel):
            self.tabel, self.soort, self.filters = tabel, "select", {}
            self.niet_leeg = None
            self.ongelijk = {}

        def select(self, *a, **kw): self.soort = "select"; return self
        def update(self, v): self.soort = "update"; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def neq(self, k, v): self.ongelijk[k] = v; return self
        def in_(self, k, v): self.filters[k] = list(v); return self
        def lte(self, *a, **kw): return self
        def gte(self, *a, **kw): return self
        def or_(self, *a, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a, **kw): return self

        @property
        def not_(self):
            buiten = self

            class _Niet:
                def is_(self, kolom, waarde):
                    buiten.niet_leeg = kolom
                    return buiten
            return _Niet()

        def execute(self):
            data = []
            if self.tabel == "jobs" and self.soort == "select":
                if self.filters.get("status") == "claimed":
                    data = geclaimd
                elif self.niet_leeg == "claimed_at":
                    data = []                       # geen eerdere publicatie
                elif "id" in self.filters:
                    data = [op_id[i] for i in self.filters["id"] if i in op_id]
                elif self.filters.get("action") == "delete":
                    # de verwijdering die bij een herplaatsing hoort: gelukt
                    data = [{"status": "done", "payload": {}}]
                elif self.filters.get("status") == "pending":
                    rijen = [j for j in wachtrij if j["status"] == "pending"]
                    if "platform" in self.filters:
                        rijen = [j for j in rijen if j["platform"] == self.filters["platform"]]
                    if "platform" in self.ongelijk:
                        rijen = [j for j in rijen if j["platform"] != self.ongelijk["platform"]]
                    if "action" in self.filters:
                        rijen = [j for j in rijen if j["action"] in self.filters["action"]]
                    data = sorted(rijen, key=lambda j: j["created_at"])
            elif self.tabel == "items":
                data = [{"id": self.filters.get("id", "x"), "user_id": "u1",
                         "title": "t", "sku": None, "brand": None, "price": 20}]
            elif self.tabel == "listings":
                data = []
            return type("R", (), {"data": data})()

    class _Db:
        def table(self, naam): return _B(naam)

    return _Db()


def _uitgifte(monkeypatch, db):
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)
    monkeypatch.setattr(J, "_zet_taal_goed", lambda db, rijen: None)
    monkeypatch.setattr(J, "_herplaatsing_kansloos", lambda *a, **kw: None)
    return J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.306"}})(),
        platform="vinted", user_id="u1")


def test_verwijdering_van_een_verversing_wacht_op_de_scan(monkeypatch):
    """Precies Daniels geval: verversing klaar, scan bezig."""
    wachtrij = [_job("del1", "delete", payload={"_refresh_rollback": {"listing_id": "L1"}})]
    db = _bouw_db(wachtrij, geclaimd=[_scan_in_de_lucht()])
    assert _uitgifte(monkeypatch, db) == [], (
        "zolang de Vinted-scan loopt mag er geen verversing uitgedeeld worden")


def test_de_herplaatsing_zelf_wacht_ook(monkeypatch):
    """De tweede helft van een herplaatsing is een create met een tijdstip."""
    wachtrij = [_job("cre1", "create", ingepland=True)]
    db = _bouw_db(wachtrij, geclaimd=[_scan_in_de_lucht()])
    assert _uitgifte(monkeypatch, db) == [], (
        "ook de herplaatsing zelf hoort te wachten tot de scan klaar is")


def test_eigen_publicatie_gaat_gewoon_door(monkeypatch):
    """Een klik van de verkoper mag nooit stilvallen door een leesronde."""
    wachtrij = [_job("cre2", "create")]
    db = _bouw_db(wachtrij, geclaimd=[_scan_in_de_lucht()])
    uit = _uitgifte(monkeypatch, db)
    assert uit and uit[0]["id"] == "cre2", (
        f"publiceren waar iemand op drukte hoort door te gaan; gekregen: {uit}")


def test_zonder_scan_gaat_de_verversing_gewoon_door(monkeypatch):
    wachtrij = [_job("del2", "delete", payload={"_refresh_rollback": None})]
    db = _bouw_db(wachtrij, geclaimd=[])
    uit = _uitgifte(monkeypatch, db)
    assert uit and uit[0]["id"] == "del2", (
        f"er loopt geen scan, dus de verversing hoort meteen te gaan: {uit}")


def test_een_vastgelopen_scan_houdt_niets_tegen(monkeypatch):
    """Een scan die al minuten niets meldt is blijven hangen, geen blokkade."""
    wachtrij = [_job("del3", "delete", payload={"_refresh_rollback": None})]
    db = _bouw_db(wachtrij, geclaimd=[_scan_in_de_lucht(seconden_geleden=60 * 30)])
    uit = _uitgifte(monkeypatch, db)
    assert uit and uit[0]["id"] == "del3", (
        f"een dode scan mag het verversen niet dagenlang stilleggen: {uit}")


def test_marktplaats_verversen_blijft_ongemoeid(monkeypatch):
    """De rem is er voor Vinted; andere kanalen hebben hun eigen sessie."""
    mp = _job("delmp", "delete", payload={"_refresh_rollback": None})
    mp["platform"] = "marktplaats"
    db = _bouw_db([mp], geclaimd=[_scan_in_de_lucht()])
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)
    monkeypatch.setattr(J, "_zet_taal_goed", lambda db, rijen: None)
    monkeypatch.setattr(J, "_herplaatsing_kansloos", lambda *a, **kw: None)
    uit = J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.306"}})(),
        platform="marktplaats", user_id="u1")
    assert uit and uit[0]["id"] == "delmp", f"Marktplaats hoort door te gaan: {uit}"
