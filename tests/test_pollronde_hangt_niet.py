"""Een hangende pollronde mag de hartslag niet voor altijd stilleggen (Janneke, 10-10-2026).

Draait tests/pollronde-hangt-niet-voor-altijd-test.js met de echte pollJobs uit
extension/background.js.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hangende_ronde_wordt_overgenomen():
    uit = subprocess.run(["node", str(ROOT / "tests/pollronde-hangt-niet-voor-altijd-test.js")],
                         capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
