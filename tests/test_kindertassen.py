"""Kindertassen en -rugzakjes hebben een eigen rubriek: "kinderen tassen".

WAAROM DIT ER IS (17-10-2026, Janneke 31d28378, Als Nieuw kinderkleding)
Ze verkoopt alleen kinderspullen en zette Vinted bewust op "alleen kinderen".
Haar teddyrugzakjes stonden als "sieraden rugtassen" (de volwassen tassentak),
dus hield haar eigen instelling ze tegen: "Hier niet mogelijk". Omnivaleur had
geen kindertassen; Vinted wel (Kids > Girls/Boys clothing > Bags & backpacks,
id 1258/1257) en Marktplaats legt ze onder Kinderen en Baby's |
Kindermode-accessoires (gemeten in het plaatsformulier, 17-10-2026).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_nieuwe_takken import _mp_categorieen, _v_pad, _dashboard, _uitgedeeld  # noqa: E402


def test_vinted_alleen_kinderen_laat_de_kindertas_door_en_de_volwassen_tas_niet():
    from backend.services import platformregels as pr
    oud = {"title": "Rugtas Teddy onesize", "category": "sieraden rugtassen"}
    nieuw = {"title": "Rugtas Teddy onesize", "category": "kinderen tassen"}
    assert pr.beoordeel(oud, "vinted", ["kinderen"])[0] == pr.BLOKKADE
    assert pr.beoordeel(nieuw, "vinted", ["kinderen"])[0] == pr.OK


def test_rubriek_staat_op_elke_plek():
    from backend.api.imports import _TAXONOMY
    from backend.services.crosslist import _GEEN_MAAT_CATEGORIEEN
    from backend.platforms.ebay import _EBAY_CATEGORY_HINTS
    from backend.api.items import _doelgroep_bij_rubriek
    assert "kinderen tassen" in _TAXONOMY["kinderen"]
    assert "kinderen tassen" in _dashboard()["kinderen"]
    assert "kinderen tassen" in _GEEN_MAAT_CATEGORIEEN
    assert "'kinderen tassen'" in (ROOT / "frontend/app.html").read_text(encoding="utf-8") \
        .split("const GEEN_MAAT_CATEGORIEEN = ")[1].split(";")[0]
    assert _EBAY_CATEGORY_HINTS["kinderen tassen"]
    assert _doelgroep_bij_rubriek("kinderen tassen") == "kinderen"


def test_marktplaats_is_de_gemeten_kinderrubriek():
    # /plaats/565/3136?bucketId=427 -> "Kinderen en Baby's | Kindermode-accessoires"
    assert _mp_categorieen()["kinderen tassen"] == (565, 3136, 427)


def test_vinted_pad_is_kids_bags_and_backpacks_in_vinteds_boom():
    boom = json.loads((ROOT / "tests/fixtures/vinted_catalogus_en_15-10-2026.json")
                      .read_text(encoding="utf-8"))["boom"]
    assert _v_pad()["kinderen tassen"] == ["Kids", "Girls clothing", "Bags & backpacks"]
    assert boom["1258"] == ["Bags & backpacks", 1195] and boom["1195"][0] == "Girls clothing"
    assert boom["1257"] == ["Bags & backpacks", 1194] and boom["1194"][0] == "Boys clothing"


def _kinder_pad(cat, title):
    src = (ROOT / "extension/content/vinted.js").read_text(encoding="utf-8")
    start = src.index("  function kinderPad(cat, item) {")
    eind = src.index("\n  }\n", start) + 4
    kk = re.search(r"const KIND_KLEDING = .*?;\n", src).group(0)
    code = (kk + src[start:eind]
            + f"\nconsole.log(JSON.stringify(kinderPad({json.dumps(cat)}, {{title: {json.dumps(title)}}})));")
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True,
                                     check=True).stdout)


@pytest.mark.parametrize("titel,verwacht", [
    ("Rugtas Teddy onesize", None),                    # -> V_PAD: Girls clothing
    ("Rugtas Teddy Leopard onesize", None),
    ("Rugzak dino jongens", ["Kids", "Boys clothing", "Bags & backpacks"]),
    ("Rugzak broer en zus, jongens en meisjes", None),
])
def test_jongens_alleen_als_de_tekst_het_zegt(titel, verwacht):
    assert _kinder_pad("kinderen tassen", titel) == verwacht


@pytest.mark.parametrize("titel,verwacht", [
    ("Rugtas Teddy kids onesize", "kinderen tassen"),
    ("Kids schooltas", "kinderen tassen"),
    ("Girls backpack unicorn", "kinderen tassen"),
    ("Meisjes jurk met tasje maat 110", "meisjes kleding"),
    ("Jongens jas maat 128", "jongens kleding"),
])
def test_import_herkent_een_kindertas(titel, verwacht):
    from backend.api.imports import _infer_attributes
    assert _infer_attributes(titel).get("category") == verwacht


@pytest.mark.parametrize("versie,verwacht", [
    ("1.0.394", False),   # kent de rubriek niet: wacht op de update
    ("1.0.395", True),
])
def test_oude_kopie_krijgt_geen_kindertas(monkeypatch, versie, verwacht):
    assert _uitgedeeld(monkeypatch, versie, "create", "kinderen tassen") == verwacht
    assert _uitgedeeld(monkeypatch, versie, "delete", "kinderen tassen") is True
