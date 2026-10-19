"""Luiertassen en mombags hebben een eigen kinderrubriek: "kinderen luiertassen".

WAAROM DIT ER IS (18/19-10-2026, Janneke 31d28378)
"Ik wilde 2 mombags plaatsen, maar dat kan niet." Haar "Mombag onesize" (Your
Wishes) is een luiertas, maar stond als "sieraden schoudertassen". Haar eigen
instelling "Vinted alleen kinderen" hield hem daardoor tegen. Vinted heeft er een
kinderrubriek voor: Kids > Bathing & changing > Baby changing bags (3394).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_nieuwe_takken import _v_pad, _dashboard, _uitgedeeld  # noqa: E402

VOOR = "206f955e"


def test_vinted_alleen_kinderen_laat_de_mombag_nu_door():
    from backend.services import platformregels as pr
    oud = {"title": "Mombag onesize", "category": "sieraden schoudertassen"}
    nieuw = {"title": "Mombag onesize", "category": "kinderen luiertassen"}
    assert pr.beoordeel(oud, "vinted", ["kinderen"])[0] == pr.BLOKKADE
    assert pr.beoordeel(nieuw, "vinted", ["kinderen"])[0] == pr.OK


@pytest.mark.parametrize("titel,verwacht", [
    ("Mombag onesize", "kinderen luiertassen"),
    ("Mombag onesize (kopie)", "kinderen luiertassen"),
    ("Luiertas Jollein beige", "kinderen luiertassen"),
    ("Luierrugzak Little Company", "kinderen luiertassen"),
    ("Diaper bag Babymoov", "kinderen luiertassen"),
    ("Rugtas Teddy kids onesize", "kinderen tassen"),
    ("Schoudertas leer dames", None),
])
def test_import_herkent_een_luiertas(titel, verwacht):
    from backend.api.imports import _infer_attributes
    uit = _infer_attributes(titel)
    if verwacht is None:
        assert uit.get("category") != "kinderen luiertassen"
    else:
        assert uit.get("category") == verwacht and uit.get("gender") == "kinderen"


def test_oude_import_maakte_er_geen_kinderspul_van():
    bron = subprocess.run(["git", "show", f"{VOOR}:backend/api/imports.py"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    assert "kinderen luiertassen" not in bron


def test_rubriek_staat_op_elke_plek():
    from backend.api.imports import _TAXONOMY
    from backend.services.crosslist import _GEEN_MAAT_CATEGORIEEN
    from backend.platforms.ebay import _EBAY_CATEGORY_HINTS
    assert "kinderen luiertassen" in _TAXONOMY["kinderen"]
    assert "kinderen luiertassen" in _dashboard()["kinderen"]
    assert "kinderen luiertassen" in _GEEN_MAAT_CATEGORIEEN
    assert "'kinderen luiertassen'" in (ROOT / "frontend/app.html").read_text(encoding="utf-8") \
        .split("const GEEN_MAAT_CATEGORIEEN = ")[1].split(";")[0]
    assert _EBAY_CATEGORY_HINTS["kinderen luiertassen"]
    assert '"kinderen luiertassen":' in (ROOT / "extension/background.js").read_text(encoding="utf-8")


def test_vinted_pad_bestaat_in_vinteds_boom():
    boom = json.loads((ROOT / "tests/fixtures/vinted_catalogus_en_15-10-2026.json")
                      .read_text(encoding="utf-8"))["boom"]
    assert _v_pad()["kinderen luiertassen"] == ["Kids", "Bathing & changing", "Baby changing bags"]
    assert boom["3394"] == ["Baby changing bags", 3393]
    assert boom["3393"] == ["Bathing & changing", 1193]


@pytest.mark.parametrize("versie,verwacht", [("1.0.397", False), ("1.0.398", True)])
def test_oude_kopie_krijgt_geen_luiertas(monkeypatch, versie, verwacht):
    assert _uitgedeeld(monkeypatch, versie, "create", "kinderen luiertassen") == verwacht
