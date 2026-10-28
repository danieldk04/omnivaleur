"""Het producttype van de Shopify-winkel bepaalt de rubriek (28-10-2026).

Van de 542 artikelen zonder rubriek kwamen er 455 uit Shopify. Voordeelsieraden
en Goudlief gaven elk product een nette soort mee ("Kettingen", "Ringen"), maar
de woordenlijst kent geen sieraden en de rubriekvraag kreeg van Google alleen 429.
"""
from backend.api.imports import _TAXONOMY, rubriek_uit_producttype
from backend.services.shopify_scan import naar_scanregel


def test_gemeten_producttypes():
    verwacht = {
        "Kettingen": "sieraden kettingen", "Hangers": "sieraden kettinghangers",
        "Ringen": "sieraden ringen", "Armbanden": "sieraden armbanden",
        "Broches": "sieraden broches", "Oorbellen": "sieraden oorbellen",
        "Dames sieraden/Kettingen/Hangerkettingen": "sieraden kettingen",
        "Accessoires/Sjaals/Zomersjaals": "unisex accessoires",
    }
    for soort, rubriek in verwacht.items():
        assert rubriek_uit_producttype(soort).get("category") == rubriek, soort


def test_onzekere_soorten_blijven_leeg():
    for soort in ("Overig", "Horloges", "Verpakking en weergave", "Accessoires/Make-uptassen", "", None):
        assert rubriek_uit_producttype(soort) == {}, soort


def test_elke_rubriek_bestaat_in_de_indeling():
    from backend.api.imports import _RUBRIEK_VAN_PRODUCTTYPE
    for tak, rubriek in set(_RUBRIEK_VAN_PRODUCTTYPE.values()):
        assert rubriek in _TAXONOMY[tak]


def test_de_scan_neemt_het_producttype_mee():
    product = {"id": 1, "title": "Granaten 3-strengs vintage collier", "product_type": "Kettingen",
               "tags": "Dames", "variants": [{"price": "95.00", "sku": "X1"}], "images": []}
    regel = naar_scanregel(product, "winkel.myshopify.com")
    assert regel["category"] == "sieraden kettingen"
    assert regel["gender"] == "sieraden"
