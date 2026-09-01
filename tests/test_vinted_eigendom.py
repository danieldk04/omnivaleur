"""Alleen een advertentie van de verkoper zelf mag worden afgemeld.

De echte functies uit background.js draaien in tests/vinted-eigendom-test.js
tegen nagebootste Vinted-antwoorden. Dit haakt ze aan de gewone testronde.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_de_eigendomscontrole_doet_wat_ze_belooft():
    uit = subprocess.run(["node", str(ROOT / "tests/vinted-eigendom-test.js")],
                         capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
