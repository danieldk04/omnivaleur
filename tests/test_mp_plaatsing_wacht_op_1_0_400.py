"""Plaatsen en bijwerken op Marktplaats en 2dehands gaat alleen naar 1.0.400 of nieuwer.

WAAROM (21-10-2026, Voordeelsieraden 09e089ec). Marktplaats gaf de
beschrijvingseditor vanaf 12:30 UTC een ander kenmerk. Haar 1.0.398 vond het veld
niet: 2dehands 90 van 90 mislukt, Marktplaats 26 van 26, en er stonden nog 15
plaatsingen in de rij die precies zo zouden mislukken. Tot de kopie bijwerkt
blijft het werk staan. Verwijderen moet gewoon doorgaan (na een verkoop).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_2dehands_verzendkosten_bijwerken import _db, _plaatsing_in_de_rij, _uitgifte  # noqa: E402

VOOR_DE_REPARATIE = "0df29acc"


def _oude_jobs():
    spec = importlib.util.spec_from_file_location(
        "rubriekproef", ROOT / "tests" / "test_2dehands_volgt_de_marktplaats_rubriek.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._oude_module("backend/api/jobs.py", VOOR_DE_REPARATIE, "oude_jobs_mp_editor",
                            moet_bevatten=("MINIMALE_VINTED_PLAATS_VERSIE",),
                            moet_missen=("MINIMALE_MP_BESCHRIJVING_VERSIE",))


@pytest.mark.parametrize("platform", ["marktplaats", "2dehands"])
def test_oude_server_gaf_haar_oude_kopie_de_plaatsing(monkeypatch, platform):
    uit = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij(platform=platform)]), "1.0.398",
                    platform=platform, module=_oude_jobs())
    assert uit, "dan bewijst deze proef niets"


@pytest.mark.parametrize("platform", ["marktplaats", "2dehands"])
@pytest.mark.parametrize("versie,uitgedeeld", [
    ("1.0.398", False), ("1.0.399", False), ("1.0.400", True), ("1.0.405", True),
])
def test_plaatsing_alleen_naar_1_0_400_of_nieuwer(monkeypatch, platform, versie, uitgedeeld):
    uit = _uitgifte(monkeypatch, _db([_plaatsing_in_de_rij(platform=platform)]), versie, platform=platform)
    assert bool(uit) == uitgedeeld, f"{platform} {versie}: {uit}"


def test_verwijderen_gaat_gewoon_door_op_de_oude_kopie(monkeypatch):
    verwijdering = {**_plaatsing_in_de_rij(platform="marktplaats"), "action": "delete"}
    uit = _uitgifte(monkeypatch, _db([verwijdering]), "1.0.398", platform="marktplaats")
    assert uit
