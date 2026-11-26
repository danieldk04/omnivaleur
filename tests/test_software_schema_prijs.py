"""Google eist een price op elke Offer; zonder price keurt Ahrefs 210 pagina's af (26-11-2026)."""
from backend.content.pipeline import _software_json_ld


def test_offer_heeft_prijs_en_valuta():
    sw = _software_json_ld()
    assert sw["aggregateRating"]["ratingValue"] and sw["aggregateRating"]["reviewCount"]
    offer = sw["offers"]
    assert offer["price"] and offer["priceCurrency"] == "EUR"
