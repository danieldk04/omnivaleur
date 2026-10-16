"""Een vaste staat voor elke Vinted-advertentie, als de verkoper dat kiest.

WAAROM (16-10-2026, De Juiste Toon): "Doorplaatsen naar vinted ... komt in
verkeerde status. Ik wil graag automatisch alles bij status GOED". Zijn artikelen
staan op "good" (Zo goed als nieuw, de importstand), en dat wordt op Vinted
"Heel goed". De instelling vinted_staat zet bij de uitgifte de staat van elke
Vinted-plaatsing vast; het artikel en de andere kanalen blijven met rust.

Deze proef draait de echte uitgifte (get_pending_jobs) met de nagemaakte database
uit test_kanalen_om_de_beurt.py, plus de oude jobs.py ter vergelijking.
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.api.jobs as J  # noqa: E402
import backend.services.instellingen as I  # noqa: E402
from tests.test_kanalen_om_de_beurt import _bouw_db, _job  # noqa: E402

VOOR = "a3290e50"   # jobs.py van vóór deze reparatie


def _oude_jobs():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/api/jobs.py"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    assert "VINTED_STAAT" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_staat.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_staat", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    return oud


def _uitgifte(module, monkeypatch, platform, instelling):
    j = _job("v1", platform, 5)
    j["payload"] = {"price": 20, "condition": "good", "title": "Granny deken"}
    db = _bouw_db([j], laatst_bediend=None)
    monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(module, "_record_extension_heartbeat", lambda *a, **kw: None)
    monkeypatch.setattr(module, "_recover_stale_claims", lambda *a, **kw: None)
    monkeypatch.setattr(module, "execute_with_retry", lambda q, *a, **k: q.execute())
    monkeypatch.setattr(module, "_zet_kleur_goed", lambda rijen: None)
    monkeypatch.setattr(I, "lees", lambda user_id: I._schoon({I.VINTED_STAAT: instelling}))
    uit = module.get_pending_jobs(
        request=type("R", (), {"headers": {"x-omnivaleur-ext": "1.0.391"}})(),
        platform=platform, user_id="u1")
    assert uit and uit[0]["id"] == "v1"
    return uit[0]["payload"]["condition"]


def test_vaste_staat_gaat_mee_naar_vinted(monkeypatch):
    assert _uitgifte(J, monkeypatch, "vinted", "fair") == "fair"


def test_oude_uitgifte_negeerde_de_wens(monkeypatch):
    assert _uitgifte(_oude_jobs(), monkeypatch, "vinted", "fair") == "good", (
        "de oude uitgifte deed het al goed, dan bewijst deze proef niets")


def test_zonder_keuze_volgt_hij_het_artikel(monkeypatch):
    assert _uitgifte(J, monkeypatch, "vinted", None) == "good"


def test_marktplaats_merkt_er_niets_van(monkeypatch):
    assert _uitgifte(J, monkeypatch, "marktplaats", "fair") == "good"


def test_instelling_laat_alleen_echte_staten_toe():
    assert I._schoon({I.VINTED_STAAT: "fair"})[I.VINTED_STAAT] == "fair"
    assert I._schoon({I.VINTED_STAAT: ""})[I.VINTED_STAAT] is None, "leeg = het artikel volgen"
    assert I._schoon({I.VINTED_STAAT: "kapot"})[I.VINTED_STAAT] is None
    assert I._schoon({})[I.VINTED_STAAT] is None


def test_fair_wordt_op_vinted_goed():
    bron = (ROOT / "extension" / "content" / "vinted.js").read_text()
    assert '"fair": "Good",' in bron, "de vaste staat rekent op fair = Goed op Vinted"
