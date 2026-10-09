"""Twee Shopify-producten met alleen dezelfde titel heten geen dubbel product.

WAAROM DIT ER IS (09-10-2026, Janneke 31d28378, kinderkleding). 526 van haar
wachtende Shopify-producten ("Schoenen Hip Shoestyle schoenmaat 31", vijftien
keer "Trui Your Wishes maat 122-128") kregen in "Te controleren" de uitleg
"zelfde nummer als een product dat al in je winkel staat", en na koppelen het
advies het extra product in Shopify te verwijderen. Er was geen nummer gelijk,
alleen de titel. Een gedeeld nummer blijft shopify_duplicate; alleen een gelijke
titel was eerst second_advert (een vraag). Diezelfde middag zag ze er 291 die
ze één voor één moest toevoegen; Daniel: twee producten in haar eigen winkel
zijn twee stukken. Dus geen vraag meer: "Import all" maakt er een eigen item
van. Op Vinted en Marktplaats blijft een tweede advertentie wel een vraag.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api.imports import TWIJFEL_REDENEN, _ander_shopify_product, _twijfelreden  # noqa: E402

CAND = {"platform": "shopify", "platform_listing_id": "222", "title": "Trui Your Wishes maat 128"}
ITEM = "item-1"
# Het item hangt al aan een ánder Shopify-product (111).
LISTINGS = {("shopify", "111"): ITEM}
SHOPIFY_VAN_ITEM = {ITEM: {"111"}}


def test_alleen_titel_gelijk_is_een_eigen_stuk_zonder_vraag():
    assert _twijfelreden(CAND, ITEM, "same_title", set(), SHOPIFY_VAN_ITEM, LISTINGS) is None
    assert _ander_shopify_product(CAND, ITEM, "same_title", LISTINGS)


def test_ook_als_het_gelijknamige_item_verkocht_is():
    # Ander productnummer in de eigen winkel: een nieuw stuk, geen oude advertentie.
    assert _twijfelreden(CAND, ITEM, "same_title", {ITEM}, SHOPIFY_VAN_ITEM, LISTINGS) is None


def test_vinted_tweede_advertentie_blijft_een_vraag():
    cand = {"platform": "vinted", "platform_listing_id": "222"}
    reden = _twijfelreden(cand, ITEM, "same_title", set(), {}, {("vinted", "111"): ITEM})
    assert reden == "second_advert" and reden in TWIJFEL_REDENEN


def test_eerste_shopify_product_met_die_titel_koppelt_gewoon():
    # Het item staat nog niet in Shopify: dan is dit gewoon dat stuk.
    assert not _ander_shopify_product(CAND, ITEM, "same_title", {("vinted", "9"): ITEM})


def test_zelfde_nummer_blijft_dubbel_product():
    reden = _twijfelreden(CAND, ITEM, "same_code", set(), SHOPIFY_VAN_ITEM, LISTINGS)
    assert reden == "shopify_duplicate"


def test_zelfde_product_is_geen_twijfel():
    cand = {**CAND, "platform_listing_id": "111"}
    assert _twijfelreden(cand, ITEM, "same_listing", set(), SHOPIFY_VAN_ITEM, LISTINGS) is None
