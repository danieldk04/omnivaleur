"""Wat er in de wachtrij staat is een kopie; de advertentie moet het echte zijn.

WAAROM (10-09-2026, Egbert Brouwer / Papa's Plectrums). Hij zette 561 zoekertjes
klaar voor 2dehands. Een opdracht draagt een kopie van het artikel zoals het op
het moment van klikken was, en bij een bulk is dat urenlang geleden: zijn rij was
na twee uur nog 402 lang. Corrigeert hij in die tijd in het dashboard de staat
van zijn goederen — precies wat hij moest doen, want alles stond op "Zo goed als
nieuw" — dan verandert dat aan de wachtende opdrachten niets, en gaat elke
volgende advertentie tóch met de oude staat online. Voor hem is dat niet te
onderscheiden van "hij luistert niet naar wat ik instel".

Deze proef draait de ECHTE uitgifte (`get_pending_jobs`) met een opdracht die de
oude staat draagt en een artikel dat inmiddels is rechtgezet.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402

NU = datetime.now(timezone.utc)
ITEM = "11111111-1111-1111-1111-111111111111"


def _db(artikel, opdracht):
    class _B:
        def __init__(self, tabel):
            self.tabel, self.soort, self.filters = tabel, "select", {}
            self.niet_leeg = None

        def select(self, *a, **kw): self.soort = "select"; return self
        def update(self, v): self.soort = "update"; return self
        def eq(self, k, v): self.filters[k] = v; return self
        def neq(self, k, v): return self
        def in_(self, k, v): self.filters[k] = list(v); return self

        def __getattr__(self, _n):
            return lambda *a, **kw: self

        @property
        def not_(self):
            buiten = self

            class _N:
                def is_(self, kolom, _w):
                    buiten.niet_leeg = kolom
                    return buiten
            return _N()

        def execute(self):
            data = []
            if self.tabel == "jobs" and self.soort == "select":
                if self.filters.get("status") == "claimed" or self.niet_leeg:
                    data = []
                elif self.filters.get("action") == "delete":
                    data = []
                elif self.filters.get("status") == "pending":
                    data = [opdracht]
            elif self.tabel == "items":
                # Het artikel zoals het NU in het dashboard staat.
                data = [artikel]
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
    monkeypatch.setattr(J, "_kopie_staat_stil", lambda *_a, **_kw: None)
    return J.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.317"}})(),
        platform="2dehands", user_id="u1")


def _opdracht(payload):
    return {"id": "j1", "user_id": "u1", "item_id": ITEM, "platform": "2dehands",
            "action": "create", "status": "pending", "payload": payload,
            "created_at": (NU - timedelta(hours=2)).isoformat(), "scheduled_for": None}


def test_de_rechtgezette_staat_gaat_mee_de_deur_uit(monkeypatch):
    artikel = {"id": ITEM, "user_id": "u1", "title": "Plectrum", "sku": None,
               "brand": "Dunlop", "condition": "new", "size": None,
               "color": None, "material": None, "price": 1.95}
    uit = _uitgifte(monkeypatch, _db(artikel, _opdracht(
        {"title": "Plectrum", "price": 1.95, "condition": "good", "brand": None})))
    assert len(uit) == 1
    assert uit[0]["payload"]["condition"] == "new", (
        "de opdracht ging met de oude, onjuiste staat de deur uit")
    assert uit[0]["payload"]["brand"] == "Dunlop", "een leeg kenmerk werd niet aangevuld"


def test_een_leeg_veld_in_het_artikel_maakt_de_opdracht_niet_armer(monkeypatch):
    """Anders zou een opdracht met gegevens die van de advertentiepagina komen
    (herplaatsen) juist worden uitgekleed."""
    artikel = {"id": ITEM, "user_id": "u1", "title": "Plectrum", "sku": None,
               "brand": None, "condition": "", "size": "  ", "color": None,
               "material": None, "price": 1.95}
    uit = _uitgifte(monkeypatch, _db(artikel, _opdracht(
        {"title": "Plectrum", "price": 1.95, "condition": "new",
         "brand": "Dunlop", "size": "M"})))
    assert uit[0]["payload"]["condition"] == "new"
    assert uit[0]["payload"]["brand"] == "Dunlop"
    assert uit[0]["payload"]["size"] == "M"


def test_de_vorige_versie_stuurde_de_oude_staat_mee(monkeypatch):
    """Voor-en-na, met een vast commitnummer in plaats van HEAD."""
    import importlib.util
    import subprocess
    import tempfile
    bron = subprocess.run(["git", "show", "af816f80:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_UIT_HET_ARTIKEL" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as m:
        pad = Path(m) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)

    artikel = {"id": ITEM, "user_id": "u1", "title": "Plectrum", "sku": None,
               "brand": "Dunlop", "condition": "new", "size": None,
               "color": None, "material": None, "price": 1.95}
    db = _db(artikel, _opdracht(
        {"title": "Plectrum", "price": 1.95, "condition": "good", "brand": None}))
    monkeypatch.setattr(oud, "get_db", lambda: db)
    monkeypatch.setattr(oud, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(oud, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(oud, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(oud, "_zet_kleur_goed", lambda rijen: None)
    monkeypatch.setattr(oud, "_kopie_staat_stil", lambda *_a, **_kw: None)
    uit = oud.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.317"}})(),
        platform="2dehands", user_id="u1")
    assert uit[0]["payload"]["condition"] == "good", (
        "de oude versie ververste al — dan bewijst deze proef niets")
