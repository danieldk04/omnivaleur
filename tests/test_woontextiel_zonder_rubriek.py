"""De Juiste Toon, 05-09-2026: 21 artikelen zonder rubriek, dus onpubliceerbaar.

Een artikel zonder rubriek weigert het publicatiepad met "This item has no
category set". Dat is terecht — liever niets dan gokken — maar het gebeurt
stil: in zijn overzicht is niet te zien dat die 21 nooit ergens heen kunnen.

Doorgemeten wat er in de weg zat: de woordenlijst kijkt op héle woorden, dus
"kleed" ving wél "kleed" maar niet "kleedje", "wandkleed", "sprei" of "kelim".
Zeven van zijn 21 waren precies zulke gevallen. Die zeven vullen zichzelf nu bij
het publiceren (zie crosslist._fill_inferred_gaps, die dezelfde woordenlijst
gebruikt en de uitkomst opslaat). De overige veertien zijn kleding zonder
geslachtssignaal in de titel; daar blijft het model voor nodig, en dan is leeg
laten de goede uitkomst.

Draaien: python -m pytest tests/test_woontextiel_zonder_rubriek.py
"""
import pytest

from backend.api.imports import _TAXONOMY, _infer_attributes


# ── de zeven die het nu zelf oplossen, met zijn echte titels ────────────────

@pytest.mark.parametrize("titel,rubriek", [
    ("Vintage handgemaakt wandkleed paarden 98/80 cm", "wonen wanddecoraties"),
    ("Wandkleed wol handgeknoopt smyrna blauw rood bruin 90/60", "wonen wanddecoraties"),
    ("Vintage sprei Mexicaans patroon reversibel 185/125 cm", "wonen plaids en woondekens"),
    ("Grand foulard Perzisch met Oosters motief 170/127 cm", "wonen plaids en woondekens"),
    ("Kelim loper 98/35 cm", "wonen tapijten en kleden"),
    ("Kleedje recycle geweven kleurrijk 113/45 cm", "wonen tapijten en kleden"),
    ("Vintage tafelloper kleedje geknoopt ecru bruintinten", "wonen tafelkleden"),
])
def test_woontextiel_krijgt_zijn_eigen_rubriek(titel, rubriek):
    uit = _infer_attributes(titel, "")
    assert uit.get("category") == rubriek, uit
    assert uit.get("gender") == "wonen"


def test_elke_gekozen_rubriek_bestaat_echt():
    for titel, _ in [("Wandkleed paarden", None), ("Sprei bloemen", None),
                     ("Tafelloper ecru", None), ("Kelim loper", None)]:
        uit = _infer_attributes(titel, "")
        assert uit["category"] in _TAXONOMY["wonen"]


# ── en wat er NIET mee opgeschoven mag worden ───────────────────────────────

def test_een_vlaams_kleedje_met_kledingsignaal_blijft_kleding():
    """In Vlaanderen is een "kleedje" een jurk. De hele woontak hangt daarom
    achter `not gender`: staat er dames, heren of een maat bij, dan beslist het
    model en niet deze lijst."""
    uit = _infer_attributes("Mooi kleedje maat 38 dames", "")
    assert uit.get("gender") == "dames"
    assert uit.get("category") != "wonen tapijten en kleden"


def test_een_geruit_overhemd_wordt_geen_woondeken():
    """Daarom staat "plaid" bewust niet in de lijst: in het Engels is dat een
    ruitpatroon, en een plaid shirt heeft geen geslachtswoord in de titel."""
    uit = _infer_attributes("Plaid flannel shirt", "")
    assert uit.get("category") != "wonen plaids en woondekens"


def test_de_bestaande_kledenregel_werkt_nog_gewoon():
    assert _infer_attributes("Vloerkleed 200/300", "")["category"] == "wonen tapijten en kleden"
    assert _infer_attributes("Handgeknoopt tapijt 87/47cm", "")["category"] == "wonen tapijten en kleden"


def test_kleding_zonder_geslacht_blijft_leeg_in_plaats_van_geraden():
    """De veertien die overblijven. Leeg is hier het goede antwoord: een jas
    onder de verkeerde rubriek is erger dan een jas die om een keuze vraagt."""
    for titel in ("Mooie rode jas", "Mooie cashmere jasje", "Mooie broek"):
        assert "category" not in _infer_attributes(titel, ""), titel
