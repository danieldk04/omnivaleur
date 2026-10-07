"""Een waarde die niet in het databaseveld past laat de import niet mislukken.

WAAROM DIT ER IS (07-10-2026, Goudlief)
De Shopify-lezer neemt het tweede stuk van de titel als maat. Bij "Cetabever -
Meesterbeits Deur & Kozijn Dekkend - RAL 7022 - 750 ML" werd dat een maat van 34
tekens, in een databaseveld van 20 (character varying(20)). De database weigerde
het hele artikel en 19 producten vielen stil om op "failed"; 28 wachtende stonden
klaar om hetzelfde te doen. De grenzen hieronder zijn gemeten uit de database.

Met IMPORTS_BRON=<pad> draait dezelfde proef tegen een oude versie.
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.models import ItemCreate  # noqa: E402


def _laad():
    bron = os.environ.get("IMPORTS_BRON") or str(ROOT / "backend/api/imports.py")
    spec = importlib.util.spec_from_file_location("imports_veld_onder_proef", bron)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


imp = _laad()

# Gemeten op 07-10-2026 via de OpenAPI-beschrijving van de database.
DATABASE_MAX = {"sku": 50, "title": 100, "brand": 100, "size": 20, "condition": 20,
                "category": 100, "color": 50, "material": 100}

# Letterlijk uit zijn winkel.
CETABEVER = {
    "title": "Cetabever - Meesterbeits Deur & Kozijn Dekkend - RAL 7022 - 750 ML",
    "price": 24.95, "photo_urls": ["https://cdn.shopify.com/a.jpg"],
    "size": "Meesterbeits Deur & Kozijn Dekkend", "platform": "shopify",
}


def _past_in_de_database(data: dict):
    for veld, maximum in DATABASE_MAX.items():
        waarde = data.get(veld)
        assert not isinstance(waarde, str) or len(waarde) <= maximum, (veld, waarde)


def test_te_lange_maat_wordt_geen_mislukte_import():
    data = ItemCreate(**imp._item_data_from_candidate(dict(CETABEVER), inferred={})).model_dump()
    _past_in_de_database(data)
    assert data["size"] is None
    assert data["title"] == CETABEVER["title"]


def test_een_echte_maat_blijft_staan():
    cand = {**CETABEVER, "size": "750 ML"}
    assert imp._item_data_from_candidate(cand, inferred={})["size"] == "750 ML"


def test_te_lange_geraden_kleur_en_rubriek_ook():
    data = imp._item_data_from_candidate(
        {**CETABEVER, "size": None},
        inferred={"color": "x" * 51, "category": "y" * 101})
    _past_in_de_database(data)


def test_aanvullen_schrijft_geen_te_lange_maat_in_een_bestaand_artikel():
    patch = imp._backfill_patch({"size": None}, dict(CETABEVER), {})
    _past_in_de_database(patch)
    assert "size" not in patch
