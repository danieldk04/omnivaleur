"""Een vers Woo-product mag niet mislukken omdat de fototaak nog niet langs was.

WAAROM (16-10-2026, De Juiste Toon): "blijft mislukken als ik nieuwe adv wil
plaatsen die uit Woo komen". SiteGround houdt onze server tegen en zijn browser
mag de foto's niet ophalen; ze komen via de GitHub-taak bronfotos.yml binnen, en
die draaide 's nachts maar drie keer. Drie nieuwe producten mislukten daardoor op
alle kanalen met "None of the 7 photo(s) could be downloaded", en de opdracht
droeg ook na het binnenkomen van de foto's nog de oude bronadressen.

Nu: de plaatsing wacht (hooguit _FOTO_GEDULD, achteraan de rij), krijgt de
foto's uit onze opslag mee zodra ze er zijn, en het dashboard blijft haar tellen.
Deze proef draait de echte uitgifte (get_pending_jobs) met de nagemaakte database
uit test_kanalen_om_de_beurt.py, plus de oude jobs.py ter vergelijking.
"""
import importlib.util
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402
from tests.test_kanalen_om_de_beurt import NU, _bouw_db, _job  # noqa: E402

VOOR = "4645c4bd"   # jobs.py van vóór deze reparatie
BRON = [f"https://dejuistetoon.eu/wp-content/uploads/2026/10/1103{i}.jpg" for i in range(3)]
ONS = [f"https://x.supabase.co/storage/v1/object/public/p/96e/{i}.jpg" for i in range(3)]


def _oude_jobs():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/api/jobs.py"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    assert "_wacht_op_fotos" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_fotos.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_fotos", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _met_fotos(db, artikel_fotos):
    """Dezelfde nep-database, maar het artikel draagt nu echt foto's."""
    class _Items:
        def __init__(self, b): self.b = b
        def __getattr__(self, naam):
            echt = getattr(self.b, naam)
            if not callable(echt):
                return echt
            def door(*a, **k):
                r = echt(*a, **k)
                return self if r is self.b else r
            return door
        def execute(self):
            r = self.b.execute()
            for rij in r.data:
                rij["photo_urls"] = list(artikel_fotos)
            return r

    class _Db:
        def table(self, naam):
            b = db.table(naam)
            return _Items(b) if naam == "items" else b
    return _Db()


def _plaatsing(minuten_geleden=5, gestempeld_minuten=5, fotos=BRON):
    j = _job("woo1", "marktplaats", minuten_geleden)
    j["payload"] = {"price": 20, "photo_urls": list(fotos)}
    if gestempeld_minuten is not None:
        j["payload"]["_fotos_wachten_sinds"] = (NU - timedelta(minutes=gestempeld_minuten)).isoformat()
    return j


def _ext(module, monkeypatch, db):
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(module, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(module, "_zet_kleur_goed", lambda rijen: None)
    # De nagemaakte kopie hoort zonder dit al snel bij "loopt te ver
    # achter" (geen werk). Dat is een andere poort dan wat deze proef meet.
    monkeypatch.setattr(module, "_kopie_staat_stil", lambda *a, **k: None, raising=False)
    return module.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.419"}})(),
        platform="marktplaats", user_id="u1")


def test_wacht_zolang_de_fotos_nog_op_de_webshop_staan(monkeypatch):
    db = _met_fotos(_bouw_db([_plaatsing()], laatst_bediend=None), BRON)
    assert _ext(J, monkeypatch, db) == [], "met alleen bronfoto's hoort de plaatsing te wachten"


def test_oude_uitgifte_gaf_hem_meteen_mee_met_bronadressen(monkeypatch):
    oud = _oude_jobs()
    db = _met_fotos(_bouw_db([_plaatsing()], laatst_bediend=None), ONS)
    uit = _ext(oud, monkeypatch, db)
    assert uit and uit[0]["payload"]["photo_urls"] == BRON, (
        "de oude uitgifte had dit geval al goed, dan bewijst deze proef niets")


def test_zodra_de_fotos_er_zijn_gaat_hij_met_onze_fotos(monkeypatch):
    db = _met_fotos(_bouw_db([_plaatsing()], laatst_bediend=None), ONS)
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["id"] == "woo1"
    assert uit[0]["payload"]["photo_urls"] == ONS


def test_na_de_wachttijd_gaat_hij_hoe_dan_ook(monkeypatch):
    lang = int(J._FOTO_GEDULD.total_seconds() // 60) + 5
    db = _met_fotos(_bouw_db([_plaatsing(lang, lang)], laatst_bediend=None), BRON)
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["id"] == "woo1", "nooit eindeloos wachten"


def test_zonder_stempel_verandert_er_niets(monkeypatch):
    db = _met_fotos(_bouw_db([_plaatsing(gestempeld_minuten=None)], laatst_bediend=None), BRON)
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["id"] == "woo1", "andere klanten wachten nooit op foto's"


def test_een_wachter_houdt_de_rest_niet_tegen(monkeypatch):
    rij = [_plaatsing(minuten_geleden=30)] + [_job("mp2", "marktplaats", 1)]
    db = _met_fotos(_bouw_db(rij, laatst_bediend=None), BRON)
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["id"] == "mp2"


def test_het_dashboard_blijft_hem_tellen(monkeypatch):
    db = _met_fotos(_bouw_db([_plaatsing()], laatst_bediend=None), BRON)
    monkeypatch.setattr(J, "get_db", lambda: db)
    monkeypatch.setattr(J, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(J, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(J, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(J, "_zet_kleur_goed", lambda rijen: None)
    uit = J.get_pending_jobs(request=type("R", (), {"headers": {}})(), platform=None, user_id="u1")
    assert [j["id"] for j in uit] == ["woo1"]


def test_wachtrij_volgorde_zet_wachters_achteraan():
    licht = [
        {"id": "w", "action": "create", "platform": "vinted", "created_at": "2026-10-16T07:00:00+00:00",
         "fotos_sinds": (NU - timedelta(minutes=3)).isoformat()},
        {"id": "n", "action": "create", "platform": "vinted", "created_at": "2026-10-16T08:00:00+00:00"},
    ]
    assert [j["id"] for j in J._wachtrij_volgorde(licht, NU)] == ["n", "w"]


# ── Het stempel bij het plaatsen, en het bijwerken bij aflevering ─────────────
import asyncio  # noqa: E402

from backend.services import crosslist as cl  # noqa: E402
from backend.services import photo_mirror as pm  # noqa: E402


class _Rij:
    def __init__(self, data, log=None): self.data_, self.log = data, log
    def __getattr__(self, n): return lambda *a, **k: (self.log.append((n, a)) if self.log is not None and n == "update" else None) or self
    def execute(self): return type("R", (), {"data": self.data_})()


def _stempel(fotos, woo):
    async def _exec(q): return q.execute()
    cl_exec, cl._exec = cl._exec, _exec
    try:
        db = type("D", (), {"table": lambda s, n: _Rij([{"user_id": "u1"}] if woo else [])})()
        return asyncio.run(cl._fotos_wachten_stempel(db, {"id": "i1", "photo_urls": fotos}, "u1"))
    finally:
        cl._exec = cl_exec


def test_stempel_alleen_bij_woo_met_bronfotos():
    assert _stempel(BRON, woo=True), "Woo-klant met bronfoto's: wachten"
    assert _stempel(BRON, woo=False) is None, "zonder Woo-koppeling haalt de taak niets op"
    assert _stempel(ONS, woo=True) is None, "foto's al bij ons: niets te wachten"


def test_aflevering_werkt_de_wachtende_plaatsing_bij(monkeypatch):
    bijgewerkt = []
    wachtend = {"id": "j1", "payload": {"price": 20, "photo_urls": list(BRON),
                                        "_fotos_wachten_sinds": NU.isoformat()}}

    class _Db:
        def table(self, n):
            return _Rij([wachtend] if n == "jobs" else [], bijgewerkt)
    asyncio.run(pm._wachtende_plaatsingen_bijwerken(_Db(), "u1", "i1", list(BRON), list(ONS), 0))
    assert bijgewerkt, "de wachtende opdracht hoort de nieuwe foto's te krijgen"
    nieuw = bijgewerkt[0][1][0]["payload"]
    assert nieuw["photo_urls"] == ONS and "_fotos_wachten_sinds" not in nieuw


def test_mislukte_fotoplaatsing_gaat_terug_zodra_de_fotos_er_zijn():
    """07-11-2026 Toon: 48 plaatsingen faalden op foto's, niets zette ze terug."""
    bijgewerkt = []
    rijen = [
        {"id": "a", "platform": "2dehands", "status": "error", "payload": {"photo_urls": list(BRON)},
         "result": {"error": "None of the 7 photo(s) could be downloaded"}},
        {"id": "b", "platform": "marktplaats", "status": "error", "payload": {"photo_urls": list(BRON)},
         "result": {"error": "None of the 7 photo(s) could be downloaded"}},
        {"id": "b2", "platform": "marktplaats", "status": "pending", "payload": {}, "result": None},
        {"id": "c", "platform": "vinted", "status": "error", "payload": {},
         "result": {"error": "Vinted wouldn't accept these fields: colour"}},
    ]

    class _Db:
        def table(self, n):
            return _Rij(rijen, bijgewerkt)
    n = asyncio.run(pm._fotoplaatsingen_terugzetten(_Db(), "u1", "i1", list(ONS)))
    assert n == 1, "alleen 2dehands: marktplaats loopt al, vinted faalde om iets anders"
    nieuw = bijgewerkt[0][1][0]
    assert nieuw["status"] == "pending" and nieuw["payload"]["photo_urls"] == ONS


# DE JUISTE TOON, 07-11-2026: wandkleed 03859008. Zijn webshop gaf 8 foto's,
# waarvan twee met dezelfde inhoud; onze opslag (naam op inhoud) maakte er 7 van.
# De uitgifte ververste alleen als het artikel minstens evenveel foto's had als
# de opdracht, dus 7 < 8: de plaatsing wachtte de volle twee uur op foto's die al
# binnen waren en ging daarna met 8 onbereikbare bronadressen de deur uit, op
# Marktplaats, 2dehands en Vinted tegelijk mislukt.
VOOR_ONTDUBBELD = "44914eb3"   # jobs.py met de oude telling
BRON_DUBBEL = BRON + [BRON[0].replace(".jpg", "-kopie.jpg")]


def _oude_jobs_ontdubbeld():
    bron = subprocess.run(["git", "show", f"{VOOR_ONTDUBBELD}:backend/api/jobs.py"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    assert "len(verse_fotos) >= len(oude_fotos)" in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_ontdubbeld.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_ontdubbeld", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def test_oude_uitgifte_hield_ontdubbelde_fotos_tegen(monkeypatch):
    lang = int(J._FOTO_GEDULD.total_seconds() // 60) + 5
    db = _met_fotos(_bouw_db([_plaatsing(lang, lang, fotos=BRON_DUBBEL)], laatst_bediend=None), ONS)
    uit = _ext(_oude_jobs_ontdubbeld(), monkeypatch, db)
    assert uit and uit[0]["payload"]["photo_urls"] == BRON_DUBBEL, (
        "de oude uitgifte had dit geval al goed, dan bewijst deze proef niets")


def test_ontdubbelde_fotos_gaan_meteen_mee(monkeypatch):
    db = _met_fotos(_bouw_db([_plaatsing(fotos=BRON_DUBBEL)], laatst_bediend=None), ONS)
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["id"] == "woo1", "de foto's zijn binnen, niet langer wachten"
    assert uit[0]["payload"]["photo_urls"] == ONS


def test_artikel_met_minder_bruikbare_fotos_vervangt_niets(monkeypatch):
    # Opdracht heeft 3 foto's uit onze opslag plus 1 bronfoto; het artikel nog maar 2.
    # Dan wint de opdracht: nooit armer aan foto's die echt werken.
    opdracht = ONS + [BRON[0]]
    db = _met_fotos(_bouw_db([_plaatsing(gestempeld_minuten=None, fotos=opdracht)],
                             laatst_bediend=None), ONS[:2])
    uit = _ext(J, monkeypatch, db)
    assert uit and uit[0]["payload"]["photo_urls"] == opdracht
