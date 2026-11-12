"""2dehands: staat de Marktplaats-rubriek vol, dan plaatsen we in onze eigen keuze.

WAT ER SPEELDE (12-11-2026, Mieneke Post, Voordeelsieraden, 09e089ec). "Ik heb
een flink aantal advertenties die wel op Marktplaats staan maar niet op 2dehands,
als ik deze op 2dehands wil plaatsen krijg ik elke keer een melding. Haal ik ze
offline en plaats ik tegelijk op Marktplaats en 2dehands, dan doet hij het wel."

Gemeten in haar opdrachten: 104 plaatsingen strandden op "charges for adverts in
Sieraden, Tassen en Uiterlijk Antieke sieraden" (1826/13). Dat was precies de
rubriek die ze op Marktplaats koos; onze plaatsing op 2dehands volgt die. De
eerste betaalmelding kwam bij het 251e zoekertje in die rubriek. Dezelfde
artikelen gingen wel gratis online in onze eigen keuze (kettinghangers, ringen),
want tegelijk plaatsen volgt Marktplaats niet.

Deze proef draait haar rij in het klein twee keer: met de code van nu en met de
code van vóór de reparatie (commit f4052229).
"""
import copy
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import backend.api.jobs as jobs_api  # noqa: E402
import test_smartwatch_wijkt_uit_naar_sporthorloges as basis  # noqa: E402

VOOR_DE_REPARATIE = "f4052229"  # vast nummer, geen HEAD
USER = "mieneke"
MP13 = {"l1": 1826, "l2": 13, "l1_naam": "Sieraden, Tassen en Uiterlijk", "l2_naam": "Antieke sieraden"}
HANGERS = "sieraden kettinghangers"
# De melding zoals de extensie hem stuurt (opbouw van betaalrubriekBezwaar()).
FOUT = ('Error: 2dehands (2dehands.be) charges for an advert in this category '
        '(Antieke sieraden): there is no free option left and the publish button now reads '
        '"Naar betalen". Nothing was published and nothing was ordered.')


def _job(jid, status, categorie, mp=None, platform="2dehands", **extra):
    pl = {"category": categorie}
    if mp:
        pl["mp_category"] = copy.deepcopy(mp)
    return {"id": jid, "user_id": USER, "item_id": f"item-{jid}", "platform": platform,
            "action": "create", "status": status, "payload": pl,
            "created_at": "2026-11-12T09:00:00+00:00", "done_at": None, "result": None,
            "claimed_at": None, **extra}


def _haar_rij():
    return basis._DB([
        _job("f1", "claimed", HANGERS, MP13),
        _job("f2", "pending", HANGERS, MP13),
        _job("f3", "pending", "sieraden ringen", MP13),
        _job("r1", "pending", "sieraden ringen", {"l1": 1826, "l2": 22}),
        _job("m1", "pending", HANGERS, MP13, platform="marktplaats"),
    ])


def _oude_module():
    bron = subprocess.run(["git", "show", f"{VOOR_DE_REPARATIE}:backend/api/jobs.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_uitwijk_naar_eigen_rubriek" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_2d", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def test_voor_de_reparatie_stond_de_rij_stil(monkeypatch):
    oud = _oude_module()
    db = _haar_rij()
    basis._ontwapen(oud, monkeypatch, db)
    uit = oud.fail_job("f1", {"error": FOUT}, user_id=USER)
    assert not uit.get("requeued")
    assert db.job("f1")["status"] == "error"
    assert db.job("f2")["status"] == "cancelled", "de rest van de rij werd teruggenomen"


def test_na_de_reparatie_gaat_hij_in_de_eigen_rubriek_de_rij_weer_in(monkeypatch):
    db = _haar_rij()
    basis._ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("f1", {"error": FOUT}, user_id=USER)

    assert uit.get("requeued") is True
    f1 = db.job("f1")
    assert f1["status"] == "pending"
    assert "mp_category" not in f1["payload"]
    assert f1["payload"]["category"] == HANGERS
    assert f1["payload"]["_uitgeweken_van"] == "mp:1826/13"
    assert f1["payload"]["_rubriek_niet_op_marktplaats"] is True
    for jid in ("f2", "f3"):
        assert db.job(jid)["status"] == "pending"
        assert "mp_category" not in db.job(jid)["payload"]
    assert not [j for j in db.tabellen["jobs"] if j["status"] in ("cancelled", "error")]


def test_andere_rubrieken_en_marktplaats_blijven_onaangeroerd(monkeypatch):
    db = _haar_rij()
    basis._ontwapen(jobs_api, monkeypatch, db)
    jobs_api.fail_job("f1", {"error": FOUT}, user_id=USER)
    assert db.job("r1")["payload"]["mp_category"]["l2"] == 22
    assert db.job("m1")["payload"]["mp_category"]["l2"] == 13, "op Marktplaats is dit haar eigen rubriek"
    assert jobs_api._uitwijk_payload(db.job("m1")["payload"], "marktplaats") is None


def test_hooguit_een_sprong_en_geen_lus(monkeypatch):
    # Kost de eigen keuze ook geld, dan de gewone rem (zoals smartwatch en tapijt).
    db = basis._DB([_job("x1", "claimed", HANGERS), _job("x2", "pending", HANGERS)])
    for j in db.tabellen["jobs"]:
        j["payload"].update({"_uitgeweken_van": "mp:1826/13", "_rubriek_niet_op_marktplaats": True})
    basis._ontwapen(jobs_api, monkeypatch, db)
    uit = jobs_api.fail_job("x1", {"error": FOUT}, user_id=USER)
    assert not uit.get("requeued")
    assert db.job("x2")["status"] == "cancelled"


def test_uitgifte_wijkt_uit_zodra_de_marktplaatsrubriek_vol_is():
    db = basis._DB([
        _job("d1", "error", HANGERS, MP13, done_at="2026-11-12T09:05:00+00:00",
             result={"error": FOUT}),
        _job("n1", "pending", HANGERS, MP13),
    ])
    kandidaat = copy.deepcopy(db.job("n1"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert "mp_category" not in kandidaat["payload"]
    assert kandidaat["payload"]["category"] == HANGERS
    assert "mp_category" not in db.job("n1")["payload"], "ook in de database"


def test_zolang_er_plek_is_blijft_hij_Marktplaats_volgen():
    db = basis._DB([
        _job("d1", "done", HANGERS, MP13, done_at="2026-11-12T09:05:00+00:00"),
        _job("n1", "pending", HANGERS, MP13),
    ])
    kandidaat = copy.deepcopy(db.job("n1"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"]["mp_category"] == MP13


def test_eigen_keuze_die_ook_vol_is_geeft_geen_sprong():
    db = basis._DB([
        _job("d1", "error", HANGERS, MP13, done_at="2026-11-12T09:05:00+00:00",
             result={"error": FOUT}),
        _job("d2", "error", HANGERS, done_at="2026-11-12T09:06:00+00:00",
             result={"error": FOUT}),
        _job("n1", "pending", HANGERS, MP13),
    ])
    kandidaat = copy.deepcopy(db.job("n1"))
    jobs_api._wijk_uit_naar_gratis_rubriek(db, USER, kandidaat)
    assert kandidaat["payload"]["mp_category"] == MP13


def test_de_volgrubriek_zet_de_marktplaatsrubriek_er_niet_terug_in():
    # _zet_rubriek_van_marktplaats mag na de sprong geen Marktplaats meer bellen.
    pl = {"category": HANGERS, "_rubriek_niet_op_marktplaats": True,
          "_uitgeweken_van": "mp:1826/13"}
    job = {"id": "n1", "action": "create", "platform": "2dehands", "item_id": "i", "payload": pl}
    assert jobs_api._zet_rubriek_van_marktplaats(None, USER, job) is True
    assert "mp_category" not in job["payload"]
