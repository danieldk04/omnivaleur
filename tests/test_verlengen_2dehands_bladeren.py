"""Draait de node-proeven van verlengen op 2dehands mee in de pytest-reeks.

verlengen-2dehands-bladeren-test.js laat de versie van vóór de reparatie
(19e90b78) falen bij 625 zoekertjes en de nieuwe slagen (28-09-2026).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("node"), reason="node ontbreekt")
@pytest.mark.parametrize("proef", ["verlengen-2dehands-bladeren-test.js", "verlengen-2dehands-test.js",
                                   "verlengen-2dehands-groot-overzicht-test.js"])
def test_node_proef(proef):
    uit = subprocess.run(["node", str(ROOT / "tests" / proef)], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert uit.returncode == 0, uit.stdout + uit.stderr
