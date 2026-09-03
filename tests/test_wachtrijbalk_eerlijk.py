"""De wachtrijbalk mag geen tempo beloven dat ze niet waarmaakt.

De echte renderActivityBar uit frontend/app.html draait in
tests/wachtrijbalk-eerlijk-test.js tegen een nagebouwd scherm. Dit haakt hem
aan de gewone testronde. Aanleiding: Toon, 03-09-2026 (zie het bestand zelf).
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_de_balk_vertelt_het_gemeten_tempo():
    uit = subprocess.run(["node", str(ROOT / "tests/wachtrijbalk-eerlijk-test.js")],
                         capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
