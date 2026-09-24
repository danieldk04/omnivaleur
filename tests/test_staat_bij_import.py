"""De staat van een geïmporteerde advertentie landt op de juiste trede.

WAAROM DIT ER IS (24-09-2026, Daniel)
_map_condition zocht op losse lettergrepen in de verkeerde volgorde. Gemeten op
1000 echte Vinted-kandidaten: 414 zeiden "Goed"/"Good" en werden "good" (Like
new) in plaats van "fair" (Used). "New with tags" verloor zijn kaartje. Voor
Marktplaats-woorden werd "Zo goed als nieuw" zelfs "new", "Gebruikt" "poor"
(Damaged) en "Niet werkend" "good".

Onze treden en wat ze op de kanalen betekenen: CONDITION_HINTS in
frontend/app.html en CONDITION_MAP in extension/content/vinted.js. Deze proef
volgt die twee, niet de code die hij toetst.

Met IMPORTS_BRON=<pad> draait dezelfde proef tegen een oude versie.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _laad():
    bron = os.environ.get("IMPORTS_BRON") or str(ROOT / "backend/api/imports.py")
    spec = importlib.util.spec_from_file_location("imports_staat_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


imp = _laad()

# Elk woord dat een scan aanlevert, met de trede die erbij hoort. De eerste
# negen zijn letterlijk wat er op 24-09-2026 in import_candidates stond.
VERWACHT = {
    # Vinted, Nederlands en Engels (gemeten)
    "Nieuw met prijskaartje": "new_with_tags",
    "New with tags": "new_with_tags",
    "Nieuw zonder prijskaartje": "new",
    "New without tags": "new",
    "Heel goed": "good",
    "Very good": "good",
    "Goed": "fair",
    "Good": "fair",
    "Veelgebruikt": "poor",
    # Vinted, oudere en andere talen
    "Redelijk": "poor",
    "Satisfactory": "poor",
    "Neuf avec étiquette": "new_with_tags",
    "Neuf sans étiquette": "new",
    "Très bon état": "good",
    "Bon état": "fair",
    "Satisfaisant": "poor",
    "Neu mit Etikett": "new_with_tags",
    "Neu ohne Etikett": "new",
    "Sehr gut": "good",
    "Gut": "fair",
    "Zufriedenstellend": "poor",
    # Marktplaats en 2dehands
    "Nieuw": "new",
    "Nieuw met kaartje": "new_with_tags",
    "Nieuw met etiket": "new_with_tags",
    "Nieuw zonder etiket": "new",
    "Zo goed als nieuw": "good",
    "Gebruikt": "fair",
    "Gedragen": "fair",
    "Beschadigd": "poor",
    "Niet werkend": "poor",
    "Defect": "poor",
    "Comme neuf": "good",
    "Utilisé": "fair",
    # Hoofdletters en spaties maken niets uit
    "  zo GOED als   nieuw ": "good",
}


@pytest.mark.parametrize("woord,trede", VERWACHT.items())
def test_woord_landt_op_de_juiste_trede(woord, trede):
    assert imp._map_condition(woord) == trede


@pytest.mark.parametrize("woord", ["", None, "Onbekend", "xyz"])
def test_onbekend_woord_is_geen_gok(woord):
    assert imp._map_condition(woord) is None


def _cand(staat):
    return {"title": "Trui", "price": 10, "condition": staat, "photo_urls": []}


def test_artikel_krijgt_de_trede_van_het_platform():
    assert imp._item_data_from_candidate(_cand("Goed"), inferred={})["condition"] == "fair"
    assert imp._item_data_from_candidate(_cand("Zo goed als nieuw"), inferred={})["condition"] == "good"


def test_onbekend_woord_valt_terug_op_de_standaard_van_de_lading():
    body = {"_default_condition": "new"}
    assert imp._item_data_from_candidate(_cand("xyz"), body, inferred={})["condition"] == "new"
    assert imp._item_data_from_candidate(_cand(None), body, inferred={})["condition"] == "new"
    assert imp._item_data_from_candidate(_cand(None), inferred={})["condition"] == "good"


def test_verkoper_wint_van_het_platform():
    body = {"condition": "poor"}
    assert imp._item_data_from_candidate(_cand("Heel goed"), body, inferred={})["condition"] == "poor"


def test_aanvullen_zet_de_juiste_trede_en_raakt_een_gezette_staat_niet():
    assert imp._backfill_patch({"condition": None}, _cand("Goed"), {})["condition"] == "fair"
    assert "condition" not in imp._backfill_patch({"condition": None}, _cand("xyz"), {})
    assert "condition" not in imp._backfill_patch({"condition": "new"}, _cand("Goed"), {})
