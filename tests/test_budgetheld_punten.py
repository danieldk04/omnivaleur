"""De punten uit het gesprek met Budgetheld (01-09-2026).

De echte controles draaien in tests/budgetheld-fixes-test.js — daar zijn de
functies uit app.html, background.js en vinted.js nodig, en die zijn JavaScript.
Dit bestand haakt ze aan de gewone testronde, zodat ze niet vergeten worden.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNAS = ROOT / "tests/budgetheld-fixes-test.js"


def test_de_drie_reparaties_blijven_staan():
    uit = subprocess.run(["node", str(HARNAS)], capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
