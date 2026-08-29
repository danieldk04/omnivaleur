"""Wat er in de advertentie terechtkomt, en of de koppeling met het platform klopt.

Drie dingen die in de praktijk misgingen:
  1. de letterlijke <text>-tags van het vertaalmodel in de beschrijving;
  2. de Vinted-prijs die het veld wél toont maar het formulier niet accepteert;
  3. een handmatig op "listed" gezette advertentie zonder link, waardoor
     auto-delist hem later niet kan terugvinden.
"""
from pathlib import Path

import pytest

from backend.api.jobs import _scan_norm_title, _scan_sku, _unique_index
from backend.services.crosslist import _strip_text_tags

ROOT = Path(__file__).resolve().parents[1]


# ── 1. Geen <text>-tags in de advertentie ────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("<text>B'TWIN cycling set.</text>", "B'TWIN cycling set."),
    ("<TEXT>Hallo</TEXT>", "Hallo"),
    ("< text >Hallo</ text >", "Hallo"),
    ("Gewone tekst", "Gewone tekst"),
    ("", ""),
    # Losse punthaken midden in de tekst blijven staan.
    ("Maat < 40 en > 38", "Maat < 40 en > 38"),
    ("<text>Regel 1\n\nRegel 2</text>", "Regel 1\n\nRegel 2"),
])
def test_strip_text_tags(raw, expected):
    assert _strip_text_tags(raw) == expected


def test_payload_is_stripped_before_publishing():
    src = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
    pick = src.split("def _pick(platform: str) -> dict:")[1].split("\n    # API platforms")[0]
    assert '"title": _strip_text_tags' in pick
    # De omschrijving gaat sinds 29-08-2026 door _met_slot heen (de vaste tekst
    # onder elke advertentie), maar de <text>-zeef moet daar binnenin blijven
    # staan — anders reist een vertaal-omhulling alsnog mee de advertentie in.
    assert '"description": _met_slot(_strip_text_tags(' in pick


# ── 2. Vinted-prijs via de pagina zelf ───────────────────────────────────
def test_price_is_set_in_the_page_context():
    """Alleen daar is React's waarde-tracker bereikbaar."""
    bg = (ROOT / "extension/background.js").read_text(encoding="utf-8")
    assert "async function _mwSetVintedPrice(" in bg
    assert '_valueTracker' in bg
    assert 'msg.type === "SET_PRICE_MAIN"' in bg
    assert 'world: "MAIN"' in bg.split('msg.type === "SET_PRICE_MAIN"')[1][:400]

    vinted = (ROOT / "extension/content/vinted.js").read_text(encoding="utf-8")
    fill = vinted.split("async function fillPriceVinted(price) {")[1].split("\n  }")[0]
    assert '"SET_PRICE_MAIN"' in fill
    # De oude routes blijven als terugval bestaan.
    assert "_typePriceVariant" in fill


# ── 3. Koppeling met het platform ────────────────────────────────────────
def test_manual_mark_active_queues_a_linking_scan():
    src = (ROOT / "backend/api/listings.py").read_text(encoding="utf-8")
    fn = src.split("def mark_listing_active(")[1].split("\n@router")[0]
    assert "_queue_scan" in fn
    assert "scan_queued" in fn


@pytest.mark.parametrize("title,sku", [
    ("(1327) Navy Suitsupply Suit Pants", "1327"),
    ("  (A-12) Iets  ", "a-12"),
    ("Geen sku hier", ""),
])
def test_scan_sku(title, sku):
    assert _scan_sku(title) == sku


@pytest.mark.parametrize("a,b", [
    ("(1327) Navy Suitsupply Suit Pants - Men W36", "Navy Suitsupply Suit Pants — Men W36"),
    ("Crème Trui", "creme trui"),
    ("B'TWIN  Cycling   Set", "btwin cycling set"),
])
def test_norm_title_survives_punctuation_and_accents(a, b):
    assert _scan_norm_title(a) == _scan_norm_title(b)


def test_unique_index_drops_ambiguous_keys():
    idx = _unique_index([("a", "1"), ("b", "2"), ("a", "3"), ("", "4")])
    assert idx == {"b": "2"}, "een dubbele sleutel mag nooit een koppeling opleveren"


def test_scan_falls_back_to_sku_and_normalised_title():
    src = (ROOT / "backend/api/jobs.py").read_text(encoding="utf-8")
    store = src.split("def _store_scan_results(")[1]
    assert "_sku_index.get(_scan_sku(title))" in store
    assert "_norm_title_index.get(_scan_norm_title(title))" in store
