"""Een lege importlijst geeft een lege lijst, geen serverfout.

WAAROM DIT ER IS (02-11-2026)
Nieuwe klant kardkid9 opende op 01-11 drie keer het importscherm voordat hij iets
gescand had; GET /api/imports/ gaf elke keer 500 ("not enough values to unpack
(expected 5, got 4)"). De lege tak van list_import_candidates gaf vier waarden
terug waar vijf verwacht werden, sinds 24-09. Ook wie net "Import all" klikte en
niets meer had wachten zag daardoor de oude lijst blijven staan.

Draait list_import_candidates zelf met een nagebootste database. Met
IMPORTS_BRON=<pad> draait dezelfde proef tegen een ander bestand (de oude versie).
"""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _laad():
    bron = os.environ.get("IMPORTS_BRON") or str(ROOT / "backend/api/imports.py")
    spec = importlib.util.spec_from_file_location("imports_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _R:
    def __init__(self, data):
        self.data = data


class _Q:
    def select(self, *_a, **_k): return self
    def eq(self, *_a): return self
    def order(self, *_a, **_k): return self
    def limit(self, *_a): return self
    def execute(self): return _R([])


class _DB:
    def table(self, _naam): return _Q()


def test_lege_importlijst_geeft_lege_lijst():
    imp = _laad()
    imp.get_db = lambda: _DB()
    uit = asyncio.run(imp.list_import_candidates(platform=None, status="pending", user_id="u"))
    assert uit == []


if __name__ == "__main__":
    try:
        test_lege_importlijst_geeft_lege_lijst()
        print("ok")
    except Exception as e:
        print(f"FOUT: {type(e).__name__}: {e}")
        sys.exit(1)
