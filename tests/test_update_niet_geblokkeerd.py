"""Tabbladen voor "maak hem zelf af" mogen de zelfupdate niet tegenhouden (Janneke, 10-10-2026)."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_zelf_afmaken_houdt_update_niet_tegen():
    uit = subprocess.run(["node", str(ROOT / "tests/update-niet-geblokkeerd-door-zelf-afmaken-test.js")],
                         capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr
