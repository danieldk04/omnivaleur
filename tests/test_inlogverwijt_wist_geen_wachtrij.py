"""Een "je bent niet ingelogd" mag nooit meer een hele wachtrij opruimen.

WAT ER GEBEURDE (14-09-2026, Egbert Brouwer / Papa's Plectrums). Om 18:14 stonden
288 zoekertjes klaar met hun juiste Marktplaats-rubriek erin. Zijn extensie
meldde "niet ingelogd" bij 2dehands en binnen vier seconden waren ze alle 288
geannuleerd. Daniel weet vrij zeker dat hij gewoon ingelogd was, en de
geschiedenis geeft hem gelijk: de oude controle beschuldigde deze man 27 keer
ten onrechte tussen 22-08 en 09-09, en de nieuwe had tot die dag nog nooit
aangeslagen terwijl er 201 zoekertjes van hem doorheen gingen.

Wie er ook gelijk heeft: dit oordeel komt uit een meting die wij van buitenaf
niet kunnen natrekken, en zo'n meting hoort geen voorraad op te ruimen. Het
kanaal gaat nu twintig minuten op pauze en er sneuvelt één opdracht, die de
uitleg draagt.
"""
import importlib.util
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402

VOOR_DE_PAUZE = "b085b90c"      # de versie die zijn 288 zoekertjes opruimde
USER = "bcdf9aa4-314d-49a2-9573-8818ad61073d"
VERWIJT = (
    "You are not signed in to 2dehands (2dehands.be) in this browser, so nothing was "
    "published. We checked twice: once in the background and once in a tab on "
    "2dehands (2dehands.be) itself, and the site refused both times (HTTP 401)."
)


class _Vraag:
    def __init__(self, db, tabel):
        self.db, self.tabel, self.f, self.wijziging = db, tabel, {}, None

    def update(self, waarden):
        self.wijziging = waarden
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def in_(self, k, v):
        self.f[k] = list(v)
        return self

    @property
    def not_(self):
        return self

    def __getattr__(self, _n):
        return lambda *_a, **_kw: self

    def execute(self):
        return type("R", (), {"data": self.db.antwoord(self)})()


class _DB:
    def __init__(self, jobs):
        self.jobs = jobs

    def table(self, naam):
        return _Vraag(self, naam)

    def antwoord(self, v):
        if v.tabel != "jobs":
            return []
        if v.wijziging is not None:
            doel = v.f.get("id")
            for j in self.jobs:
                if doel is None:
                    raakt = True
                elif isinstance(doel, list):
                    raakt = j["id"] in doel
                else:
                    raakt = j["id"] == doel
                if raakt and j["status"] == v.f.get("status", j["status"]):
                    j.update(v.wijziging)
            return []
        if v.f.get("status") == "pending":
            return [j for j in self.jobs if j["status"] == "pending"]
        if v.f.get("status") == "cancelled":
            klaar = [j for j in self.jobs if j["status"] == "cancelled"]
            return sorted(klaar, key=lambda j: j.get("done_at") or "", reverse=True)
        return []


def _rij(n=5):
    return [{"id": f"j{i}", "user_id": USER, "item_id": f"i{i}", "platform": "2dehands",
             "action": "create", "status": "pending", "created_at": f"2026-09-14T17:0{i}:00",
             "done_at": None, "result": None, "payload": {"title": f"gitaartje {i}"}}
            for i in range(n)]


def _stop(module, db, monkeypatch, reden=VERWIJT):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(module, "_kanaal_kansloos", lambda *a, **kw: False)
    monkeypatch.setattr(module, "_reden_zonder_vals_verwijt",
                        lambda _db, _u, _p, r, *a, **kw: r)
    verzoek = type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.327"}})()
    return module.stop_platform({"platform": "2dehands", "reason": reden}, verzoek, USER)


def _oude_module():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_PAUZE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_pauzeer_op_inlogverwijt" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_pauze.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_pauze", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def test_een_inlogverwijt_kost_een_opdracht_en_niet_de_hele_rij(monkeypatch):
    jobs = _rij(5)
    uit = _stop(J, _DB(jobs), monkeypatch)
    assert uit["cancelled"] == 1 and uit.get("paused") is True
    assert sum(1 for j in jobs if j["status"] == "pending") == 4
    weg = [j for j in jobs if j["status"] == "cancelled"]
    assert len(weg) == 1 and weg[0]["id"] == "j0", "de oudste draagt de uitleg"
    assert VERWIJT in (weg[0]["result"] or {}).get("error", "")

    # Zoals het was: alle vijf weg. Dit is wat er met zijn 288 gebeurde.
    oud = _oude_module()
    oude_jobs = _rij(5)
    _stop(oud, _DB(oude_jobs), monkeypatch)
    assert all(j["status"] == "cancelled" for j in oude_jobs), (
        "de oude versie ruimde de hele wachtrij op"
    )


def test_na_het_verwijt_ligt_het_kanaal_twintig_minuten_stil_en_daarna_niet_meer():
    nu = datetime.now(timezone.utc)
    net = [{"status": "cancelled", "done_at": nu.isoformat(),
            "result": {"cancelled": J._PAUZE_STEMPEL}}]
    oud = [{"status": "cancelled", "done_at": (nu - timedelta(minutes=21)).isoformat(),
            "result": {"cancelled": J._PAUZE_STEMPEL}}]
    anders = [{"status": "cancelled", "done_at": nu.isoformat(),
               "result": {"cancelled": "by user"}}]
    assert J._inlog_pauze_actief(_DB(net), USER, "2dehands", nu) is True
    assert J._inlog_pauze_actief(_DB(oud), USER, "2dehands", nu) is False, (
        "na de pauze gaat er vanzelf weer een opdracht de deur uit")
    assert J._inlog_pauze_actief(_DB(anders), USER, "2dehands", nu) is False
    assert J._inlog_pauze_actief(_DB([]), USER, "2dehands", nu) is False


def test_een_echte_formulierfout_stopt_de_rij_nog_steeds_wel(monkeypatch):
    """De pauze geldt alleen voor het inlogverwijt, niet voor de rest."""
    jobs = _rij(4)
    formulier = "The 2dehands (2dehands.be) listing form never opened: the page never reported back."
    monkeypatch.setattr(J, "_stop_wachtrij", lambda *a, **kw: 4)
    uit = _stop(J, _DB(jobs), monkeypatch, reden=formulier)
    assert uit["cancelled"] == 4 and "paused" not in uit
