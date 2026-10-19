"""Een verkoopcontrole die te lang wacht, gaat voor de plaatsingen.

WAAROM DIT ER IS (19-10-2026, Janneke 31d28378)
"De bovenste jas van Dirkje is gisteren verkocht via Vinted, maar dus niet uit
marktplaats gehaald." Gemeten in haar opdrachten: de Vinted-scan van 17-10 18:39
werd pas op 18-10 19:25 opgepakt. Twee minuten later was de verkoop gezien en
ging de jas van Marktplaats af. Al die tijd stond haar Vinted-rij vol
plaatsingen: een scan kwam achter elke plaatsing, en zolang er een plaatsing
liep gaf de uitgifte voor Vinted niets, ook geen scan.

Deze proef draait de echte uitgifte (`get_pending_jobs`) tegen dezelfde
nagemaakte database als test_kanalen_om_de_beurt, oud tegen nieuw.
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_kanalen_om_de_beurt import _bouw_db, _job, _uitgifte, _uitgifte_op  # noqa: E402

VOOR = "206f955e"   # de uitgifte zoals hij op 18-10 draaide


def _oud():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/api/jobs.py"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    assert "SCAN_VOORRANG_NA" not in bron
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "oude_jobs_scan.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oude_jobs_scan", pad)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _janneke(scan_minuten_geleden):
    # Haar rij op 18-10: tientallen Vinted-plaatsingen van de avond ervoor, en de
    # scan die daarna klaargezet werd.
    rij = [_job(f"v{i}", "vinted", 1500 - i) for i in range(30)]
    rij.append(_job("scan", "vinted", scan_minuten_geleden, actie="scan"))
    return rij


def test_oud_kreeg_de_scan_nooit_terwijl_er_een_plaatsing_liep(monkeypatch):
    oud = _oud()
    assert _uitgifte_op(oud, monkeypatch, _bouw_db(_janneke(1440), None, bezig=["vinted"]),
                        "vinted") == []
    # En met het kanaal vrij ging de plaatsing voor, ook na een dag wachten.
    uit = _uitgifte_op(oud, monkeypatch, _bouw_db(_janneke(1440), None), "vinted")
    assert uit and uit[0]["action"] == "create"


def test_nieuw_een_dag_oude_scan_naast_de_lopende_plaatsing(monkeypatch):
    uit = _uitgifte(monkeypatch, _bouw_db(_janneke(1440), None, bezig=["vinted"]), "vinted")
    assert [j["id"] for j in uit] == ["scan"]


def test_nieuw_de_scan_gaat_ook_voor_als_het_kanaal_vrij_is(monkeypatch):
    uit = _uitgifte(monkeypatch, _bouw_db(_janneke(25), None), "vinted")
    assert uit and uit[0]["id"] == "scan"


def test_een_verse_scan_wacht_gewoon_achter_de_plaatsingen(monkeypatch):
    # Pas na 20 minuten: een scan die net klaarstaat, loopt niet voor een klik uit.
    uit = _uitgifte(monkeypatch, _bouw_db(_janneke(5), None), "vinted")
    assert uit and uit[0]["action"] == "create"
    assert _uitgifte(monkeypatch, _bouw_db(_janneke(5), None, bezig=["vinted"]), "vinted") == []


def test_nooit_een_tweede_plaatsing_naast_de_lopende(monkeypatch):
    rij = [_job(f"v{i}", "vinted", 100 - i) for i in range(5)]
    assert _uitgifte(monkeypatch, _bouw_db(rij, None, bezig=["vinted"]), "vinted") == []
