"""Vinted sluit de merklijst bij blur (11-11-2026, platformcontrole).

Meisjeskleding: de merkstap vond geen enkele optie ("attr option not found"),
omdat fillInput na het typen ook change en blur stuurde en Vinted de lijst dan
terugzette op de pakketgrootte. Het zoekveld mag alleen input krijgen.
"""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "extension" / "content" / "vinted.js").read_text(encoding="utf-8")


def test_merkzoekveld_krijgt_geen_fillinput():
    assert "fillInput(brandSearch" not in SRC
    blok = SRC.split("const brandSearch = zoekveld();")[1][:900]
    assert 'new Event("input"' in blok
    assert 'new Event("blur"' not in blok and 'new Event("change"' not in blok
