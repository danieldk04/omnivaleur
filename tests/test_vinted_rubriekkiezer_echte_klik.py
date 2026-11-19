"""19-11-2026 platformcontrole: de Vinted-rubriekkiezer is een knop die alleen opengaat op een echte
pointerdown-reeks. Een kale .click() opende niets, de zoekterugval typte in het zoekvak bovenaan de site
en rubriek, maat, merk en kleur vielen uit voor elk artikel zonder vast pad (kinderschoenen)."""
import pathlib

SRC = (pathlib.Path(__file__).parent.parent / "extension/content/vinted.js").read_text()


def test_zoekterugval_opent_de_kiezer_met_een_echte_klik():
    i = SRC.index("const wantKids")
    stuk = SRC[i:i + 3000]
    assert "inp.click();" not in stuk
    assert "realClickEl(inp)" in stuk


def test_zoekvak_van_de_kiezer_wint_van_het_zoekvak_van_de_site():
    assert 'e.id === "catalog-search-input"' in SRC
