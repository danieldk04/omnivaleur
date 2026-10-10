"""Een prijs die in het veld staat zonder klacht van Vinted houdt het plaatsen niet meer tegen (Janneke, 10-10-2026)."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_prijsbesluit():
    uit = subprocess.run(["node", str(ROOT / "tests/vinted-prijs-laat-vinted-beslissen-test.js")],
                         capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
