"""Een leeg adresblok op 2dehands hoort de rij te pauzeren, niet te herhalen.

GEMETEN 10-09-2026, De Juiste Toon: "ik ben nu ook op tweedehands aan het
plaatsen, die komen niet door zoals die van mp wel doen".

Tussen 18:00 en 18:03 mislukten zes plaatsingen op 2dehands achter elkaar met
dezelfde reden: het adresblok op het formulier bleef leeg, dus weigerde de
extensie te plaatsen (`wachtOpPostcode` in extension/content/shared.js wacht er
acht seconden op). Er stonden er nog tien te wachten die allemaal op precies
dezelfde regel zouden vastlopen. Elke poging houdt zijn browser ruim twee
minuten bezig, en schrijvende opdrachten gaan één voor één: dat is een half uur
waarin er niets anders kan.

Waarom pauzeren en niet blijven proberen: het adres komt uit zijn account op die
site en verandert niet doordat wij het nog een keer proberen. Van zijn 458
zoekertjes op 2dehands staan er 402 op "Etten-Leur, Nederland", 37 op "Essen
+Deel Kalmthout, België" (de stand van zijn account) en de rest op acht
verschillende spellingen, waaronder één keer "Etten-Leur, Mauritanië" — het
adres wordt per zoekertje met de hand ingetypt.

De voor-proef haalt jobs.py uit commit 1c2fb488: daar bleven de tien wachtende
opdrachten gewoon staan.

Draaien:  python3 -m pytest tests/test_leeg_adres_stopt_de_rij.py -q
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as jobs_api  # noqa: E402

VOOR_DE_REPARATIE = "1c2fb488"      # vast nummer, nooit HEAD
USER_ID = "96e30080-ab81-47ac-8626-e8637f1e2a9e"
JOB_ID = "job-mislukt"
FOUT_VAN_DE_EXTENSIE = (
    "Error: Your postcode is still empty on the listing form, so nothing was "
    "published. Open your account settings on this marketplace, fill in your "
    "postcode once, and publish again — after that it fills itself."
)


# ── Een database die zich gedraagt als de echte ─────────────────────────────

class _Q:
    def __init__(self, db, tabel):
        self.db, self.tabel = db, tabel
        self.eqs, self.ins = {}, {}
        self.op, self.velden = "select", None
        self._n = None

    def select(self, *_a, **_k): self.op = "select"; return self
    def update(self, v): self.op, self.velden = "update", v; return self
    def insert(self, rows): self.op, self.velden = "insert", rows; return self
    def eq(self, k, v): self.eqs[k] = v; return self
    def in_(self, k, v): self.ins[k] = list(v); return self
    def gte(self, *_a, **_k): return self
    def order(self, *_a, **_k): return self
    def limit(self, n): self._n = n; return self

    def _match(self, r):
        return (all(r.get(k) == v for k, v in self.eqs.items())
                and all(r.get(k) in v for k, v in self.ins.items()))

    def execute(self):
        bron = getattr(self.db, self.tabel)
        rijen = [r for r in bron if self._match(r)]
        if self.op == "update":
            for r in rijen:
                r.update(self.velden)
        klasse = type("R", (), {"data": rijen[: self._n] if self._n else rijen})
        return klasse()


class _DB:
    def __init__(self, jobs, listings):
        self.jobs, self.listings = jobs, listings
    def table(self, naam): return _Q(self, naam)


def _situatie():
    """Eén mislukte plaatsing en tien die nog wachten, allemaal 2dehands."""
    jobs = [{"id": JOB_ID, "user_id": USER_ID, "item_id": "it0",
             "platform": "2dehands", "action": "create", "status": "claimed",
             "payload": {"category": "wonen tapijten en kleden"}}]
    listings = []
    for n in range(10):
        jobs.append({"id": f"wacht{n}", "user_id": USER_ID, "item_id": f"it{n + 1}",
                     "platform": "2dehands", "action": "create", "status": "pending",
                     "payload": {"category": "wonen tapijten en kleden"}})
        listings.append({"id": f"L{n}", "item_id": f"it{n + 1}",
                         "platform": "2dehands", "status": "pending",
                         "error_message": None})
    # Marktplaats staat er los van en mag niet meegepauzeerd worden: dáár
    # publiceert hij juist wel.
    jobs.append({"id": "mp1", "user_id": USER_ID, "item_id": "it99",
                 "platform": "marktplaats", "action": "create", "status": "pending",
                 "payload": {}})
    return _DB(jobs, listings)


def _ontwapen(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda vraag, **_kw: vraag.execute())
    # De remmen die hier niet aan de orde zijn: die vragen de database dingen
    # die met dit geval niets te maken hebben.
    monkeypatch.setattr(module, "_kanaal_kansloos", lambda *_a, **_kw: False)
    monkeypatch.setattr(module, "_queue_scan", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "_meld_mislukte_herplaatsing", lambda *_a, **_kw: None)
    monkeypatch.setattr(module, "_verwijderdoelen", lambda *_a, **_kw: [])
    monkeypatch.setattr(module, "_herplaatsing_kansloos", lambda *_a, **_kw: None)


# ── 1. De rij gaat op pauze, met de uitleg erbij ───────────────────────────

def test_leeg_adres_pauzeert_de_rij_voor_dat_kanaal(monkeypatch):
    db = _situatie()
    _ontwapen(jobs_api, monkeypatch, db)

    jobs_api.fail_job(JOB_ID, {"error": FOUT_VAN_DE_EXTENSIE}, USER_ID)

    wachtend = [j for j in db.jobs if j["platform"] == "2dehands" and j["id"] != JOB_ID]
    assert all(j["status"] == "cancelled" for j in wachtend), (
        "elke volgende opdracht loopt op dezelfde lege regel vast en hoort niet "
        f"te blijven staan: {[(j['id'], j['status']) for j in wachtend]}")
    reden = wachtend[0]["result"]["error"]
    assert "Buitenland" in reden, "de melding hoort te zeggen waar hij moet zijn"
    assert "2dehands.be" in reden
    assert "gepauzeerd" in reden

    # De advertentierijen blijven niet op "bezig" staan, met de reden erbij.
    assert all(l["status"] == "error" and "Buitenland" in (l["error_message"] or "")
               for l in db.listings)

    # Marktplaats blijft ongemoeid.
    assert next(j for j in db.jobs if j["id"] == "mp1")["status"] == "pending"

    # En de mislukte opdracht zelf draagt de uitgelegde tekst, met het origineel
    # er nog bij voor ons.
    mislukt = next(j for j in db.jobs if j["id"] == JOB_ID)
    assert mislukt["status"] == "error"
    assert "Buitenland" in mislukt["result"]["error"]
    assert "postcode is still empty" in mislukt["result"]["error_oorspronkelijk"]


# ── 2. De melding van de site zelf telt ook ────────────────────────────────

@pytest.mark.parametrize("fout", [
    "Error: Not published — complete the fields marked in red and click publish "
    "yourself. Geen postcode ingevuld. | Fields marked invalid: "
    "contactInformation.postCode=LEEG",
    "Error: Your postcode is still empty on the listing form, so nothing was published.",
])
def test_ook_de_tekst_van_de_site_zelf_slaat_aan(monkeypatch, fout):
    db = _situatie()
    _ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job(JOB_ID, {"error": fout}, USER_ID)
    assert all(j["status"] == "cancelled"
               for j in db.jobs if j["platform"] == "2dehands" and j["id"] != JOB_ID)


# ── 3. Een gewone fout pauzeert niets ──────────────────────────────────────

def test_een_andere_fout_laat_de_rij_staan(monkeypatch):
    db = _situatie()
    _ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job(JOB_ID, {"error": "Extension timed out waiting for this job"}, USER_ID)
    assert all(j["status"] == "pending"
               for j in db.jobs if j["platform"] == "2dehands" and j["id"] != JOB_ID)


# ── 4. Voor-en-na: de oude code liet de tien staan ─────────────────────────

def test_de_oude_code_liet_de_tien_wachtenden_staan(monkeypatch):
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_GEEN_ADRES" not in bron, (
        f"commit {VOOR_DE_REPARATIE} bevat de reparatie al — dan vergelijkt de "
        f"voor-proef de reparatie met zichzelf")

    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)

    db = _situatie()
    _ontwapen(oud, monkeypatch, db)
    oud.fail_job(JOB_ID, {"error": FOUT_VAN_DE_EXTENSIE}, USER_ID)

    wachtend = [j for j in db.jobs if j["platform"] == "2dehands" and j["id"] != JOB_ID]
    assert all(j["status"] == "pending" for j in wachtend), (
        "de oude code hoort de tien wachtenden te laten staan — dat is precies "
        "wat we repareren")
