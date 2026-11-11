"""Marktplaats gaf op 21-10-2026 (12:30 UTC) de beschrijvingseditor een ander kenmerk:
data-testid="text-editor-input_nl-NL" bestaat niet meer, de editor heet nu
id="DescriptionEditor_nl-NL". Alle plaatsingen op Marktplaats faalden daarop met
"The description field could not be found". De extensie moet beide vormen kennen."""
from pathlib import Path

EXT = Path(__file__).resolve().parent.parent / "extension"


def test_marktplaats_kent_de_nieuwe_editor():
    assert "#DescriptionEditor_nl-NL" in (EXT / "content/marktplaats.js").read_text()


def test_2dehands_kent_de_nieuwe_editor():
    assert "#DescriptionEditor_nl-BE" in (EXT / "content/tweedehands.js").read_text()


def test_echt_typen_vindt_de_nieuwe_editor():
    bg = (EXT / "background.js").read_text()
    assert bg.count('[id^="DescriptionEditor"]') >= 4
