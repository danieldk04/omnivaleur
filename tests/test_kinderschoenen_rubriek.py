"""Kinderschoenen krijgen vanzelf een rubriek (Janneke 31d28378, 07-10-2026).

"Schoenen | Regenlaarzen Bergstein schoenmaat 27" had geen woord als "kids" of
"kinder", dus bleef de rubriek leeg en weigerden Vinted, Marktplaats en
2dehands het plaatsen ("Vinted: category"). Een schoenmaat onder de 30 bestaat
bij volwassenen niet, dus maat plus schoenwoord is genoeg.
"""
from backend.api.imports import _infer_attributes


def test_regenlaarzen_met_schoenmaat_27_wordt_kinderschoen():
    uit = _infer_attributes("Schoenen | Regenlaarzen Bergstein schoenmaat 27")
    assert uit.get("gender") == "kinderen"
    assert uit.get("category") == "kinderen schoenen"


def test_andere_schrijfwijzen_van_de_maat():
    for titel in ("Sneakers Nike maat 19", "Sandalen mt. 24", "Laarsjes size 22",
                  "Schoentjes maat: 21"):
        assert _infer_attributes(titel).get("category") == "kinderen schoenen", titel


def test_volwassen_schoenmaat_blijft_buiten_de_kinderrubriek():
    uit = _infer_attributes("Schoenen | Regenlaarzen Bergstein schoenmaat 38")
    assert uit.get("category") != "kinderen schoenen"
    assert uit.get("gender") != "kinderen"


def test_kindermaat_zonder_schoenwoord_doet_niets():
    # Een broek in maat 28 is een taillemaat, geen kind.
    uit = _infer_attributes("Levi's 501 jeans maat 28")
    assert uit.get("gender") != "kinderen"


def test_bestaande_engelse_regel_werkt_nog():
    assert _infer_attributes("Kids sneakers size 30").get("category") == "kinderen schoenen"
