"""Draait tests/vinted-inlog-verlopen-koekje-test.js (Janneke 31d28378, 09-10-2026)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which("node"), reason="node ontbreekt")
def test_vinted_inlogcontrole():
    r = subprocess.run([shutil.which("node"), str(ROOT / "tests" / "vinted-inlog-verlopen-koekje-test.js")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
