"""Een Vinted-plaatsing gaat alleen naar extensie 1.0.386 of nieuwer.

WAAROM (15-10-2026, Janneke 31d28378). Haar extensie bleef op 1.0.384 staan
terwijl de Web Store 1.0.386 al aanbood. Elke Vinted-plaatsing die die oude
kopie kreeg, liep vast op de prijsstap (Chrome 128: eerste prijsvraag 12 tot
33 s, oude kopie wacht zonder grens) en liet een leeg concept op Vinted achter.
Een oude kopie werkt zichzelf binnen ~2 uur bij; tot dan blijft het werk staan.
Marktplaats en 2dehands hebben dit probleem niet en gaan gewoon door.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_2dehands_verzendkosten_bijwerken import _db, _plaatsing_in_de_rij, _uitgifte  # noqa: E402

VOOR_DE_REPARATIE = "60d0cc9"


def _oude_jobs():
    spec = importlib.util.spec_from_file_location(
        "rubriekproef", ROOT / "tests" / "test_2dehands_volgt_de_marktplaats_rubriek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_vinted",
                            moet_bevatten=("MINIMALE_2DH_BIJWERK_VERSIE",),
                            moet_missen=("MINIMALE_VINTED_PLAATS_VERSIE",))


def test_oude_server_gaf_haar_oude_kopie_de_vinted_plaatsing(monkeypatch):
    uit = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij(platform="vinted")]), "1.0.384",
                    platform="vinted", module=_oude_jobs())
    assert uit, "dan bewijst deze proef niets"


@pytest.mark.parametrize("versie,uitgedeeld", [
    ("1.0.384", False), ("1.0.385", False), ("1.0.386", True), ("1.0.390", True),
])
def test_vinted_plaatsing_alleen_naar_1_0_386_of_nieuwer(monkeypatch, versie, uitgedeeld):
    uit = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij(platform="vinted")]), versie, platform="vinted")
    assert bool(uit) == uitgedeeld, f"{versie}: {uit}"


def test_marktplaats_gaat_gewoon_door_op_de_oude_kopie(monkeypatch):
    uit = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij(platform="marktplaats")]), "1.0.384",
                    platform="marktplaats")
    assert uit
