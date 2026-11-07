"""eBay Europa voor De Juiste Toon (07-11-2026): NL 7 euro, rest van de EU 15 euro."""
from backend.platforms import ebay_beleid as B

INST = {"kosten": 7.0, "verzenddagen": 3, "retourdagen": 14, "ophalen": True}


def test_zonder_eu_tarief_blijft_het_beleid_zoals_het_was():
    opties = B._verzend_beleid(INST, "EBAY_NL")["shippingOptions"]
    assert [o["optionType"] for o in opties] == ["DOMESTIC"]


def test_met_eu_tarief_komt_er_een_internationale_optie():
    opties = B._verzend_beleid({**INST, "kosten_eu": 15.0}, "EBAY_NL")["shippingOptions"]
    assert [o["optionType"] for o in opties] == ["DOMESTIC", "INTERNATIONAL"]
    s = opties[1]["shippingServices"][0]
    assert s["shippingServiceCode"] == "NL_StandardInternational"
    assert s["shippingCost"]["value"] == "15.00"
    assert s["shipToLocations"]["regionIncluded"] == [{"regionName": "EuropeanUnion"}]


def test_ebay_be_krijgt_geen_gegokte_code():
    opties = B._verzend_beleid({**INST, "kosten_eu": 15.0}, "EBAY_BE")["shippingOptions"]
    assert len(opties) == 1


def test_controle_van_eu_tarief():
    assert B.controleer_instellingen({"kosten": "7", "kosten_eu": "15,00"})["kosten_eu"] == 15.0
    assert "kosten_eu" not in B.controleer_instellingen({"kosten": "7"})
