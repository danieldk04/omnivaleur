"""De vaste tekst onder elke advertentie.

Aanleiding (29-08-2026, Jaap van zilverwebsite.nl). Hij meldde dat onderaan elke
advertentie een blok tekst ontbrak — artikelnummer, uitleg over de winkel,
verzendkosten, zoekwoorden — en zag scherp dat het ALTIJD op dezelfde plek
stopte: vlak onder gewicht en afmetingen, ongeacht hoeveel tekst eraan
voorafging.

Nagemeten op zijn echte gegevens: de omschrijving in onze database is teken voor
teken gelijk aan die van hetzelfde product in zijn eigen webshop, en die eindigt
daar ook. Het ontbrekende blok stond dus nooit in de producttekst; hij tikte het
per advertentie zelf op Marktplaats erbij. Er viel niets af te knippen en niets
terug te halen — dit moest gebouwd worden.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.instellingen import SLOTTEKST_MAX, STANDAARD, _schoon  # noqa: E402

SLOT = "23-10-013\n\nGRATIS verzonden.\n\nKijkt u ook eens bij onze andere advertenties."


def _met_slot(tekst: str, slot: str) -> str:
    """Dezelfde regel als in crosslist.publish_to_platforms, los te toetsen."""
    bron = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    blok = bron.split("def _met_slot(tekst: str) -> str:")[1].split("\n\n    def _pick")[0]
    ruimte = {"_slot": slot}
    exec("def _met_slot(tekst: str) -> str:" + blok, ruimte)   # noqa: S102 — eigen broncode
    return ruimte["_met_slot"](tekst)


def test_de_slottekst_komt_onder_de_omschrijving():
    uit = _met_slot("Zilveren lepel.\n\nGewicht: 15,8 gram.", SLOT)
    assert uit.startswith("Zilveren lepel.")
    assert uit.endswith(SLOT)
    assert "\n\n" in uit


def test_hij_komt_er_nooit_twee_keer_onder():
    """Een advertentie mét slottekst wordt bij een scan weer ingelezen. Zonder
    deze controle groeide de tekst bij elke ronde met een blok."""
    een = _met_slot("Zilveren lepel.", SLOT)
    twee = _met_slot(een, SLOT)
    assert een == twee


def test_zonder_slottekst_verandert_er_niets():
    assert _met_slot("Zilveren lepel.", "") == "Zilveren lepel."


def test_een_leeg_item_krijgt_alleen_de_slottekst():
    assert _met_slot("", SLOT) == SLOT


def test_de_instelling_wordt_begrensd_en_opgeschoond():
    assert STANDAARD["slottekst"] == ""
    assert _schoon({"slottekst": "  tekst met spaties  "})["slottekst"] == "tekst met spaties"
    lang = "x" * (SLOTTEKST_MAX + 500)
    assert len(_schoon({"slottekst": lang})["slottekst"]) == SLOTTEKST_MAX
    # Niet meegestuurd = niet gewist.
    assert _schoon({"levering": "verzenden"})["slottekst"] == ""


def test_de_slottekst_hangt_aan_elke_opdracht_en_niet_aan_een_platform():
    """Anders staat hij wel op Marktplaats en niet op Vinted, en dat is precies
    het soort verschil waar niemand achter komt."""
    bron = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    pick = bron.split("def _pick(platform: str) -> dict:")[1].split("\n    # Eerst de extensieplatforms")[0]
    assert '"description": _met_slot(' in pick


def test_het_veld_staat_in_het_scherm():
    app = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
    assert 'id="slottekst"' in app
    assert "saveSlottekst()" in app
    assert re.search(r"slottekst:\s*document\.getElementById\('slottekst'\)\.value", app)
