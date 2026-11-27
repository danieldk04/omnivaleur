"""Goudlief, 27-11-2026: 115 accessoires stonden in Blouses en Tunieken (628) en een
verversing zette ze daar terug. Die rubriek wordt voor accessoires niet overgenomen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api.jobs import _rubriek_past_niet_bij_accessoire as f  # noqa: E402


def test_blouses_voor_accessoire_wordt_geweigerd():
    for cat in ("accessoires dames", "unisex accessoires", "Heren accessoires"):
        assert f(cat, {"l1": 621, "l2": 628})
        assert f(cat, {"l1": 621, "l2": "628"})


def test_andere_rubrieken_en_categorieen_blijven_gelden():
    assert not f("accessoires dames", {"l1": 621, "l2": 1679})
    assert not f("blouses", {"l1": 621, "l2": 628})
    assert not f("accessoires dames", None)
