"""Ligt de vertaling plat, dan wacht de advertentie — hij gaat niet fout de deur uit.

WAAROM DIT ER IS (Daniel, 08-09-2026)

Het Anthropic-tegoed was op. `_vertaal` ving elke fout op met `return text`, dus
de Engelse tekst ging ongewijzigd naar Marktplaats en 2dehands. Erger nog: de
opdracht kreeg het stempel `_taal: nl` mee alsof hij vertaald wás, dus hij werd
ook nooit meer opnieuw aangeboden. Er ging technisch niets mis, dus niemand
kreeg een foutmelding.

GEMETEN, NIET AANGENOMEN (08-09-2026, in het opdrachtenlogboek):
  19:06 marktplaats, status done: "(1346) Black MyProtein Shorts - Men XL - New"
        met een Engelse omschrijving, payload-stempel `_taal: nl`.
  20:38 2dehands, status done:   "(1071) Light Blue Massimo Dutti Turtleneck -
        Women XS - Very Good", zelfde verhaal.

Wat er nu gebeurt: staat de tekst al aantoonbaar in de doeltaal, dan gaat hij
gewoon door (gemeten op 1.350 echt gepubliceerde advertenties: 96%). Staat hij
er niet in, dan blijft de opdracht wachten tot de vertaling het weer doet.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.crosslist as cl  # noqa: E402
from backend.services.crosslist import (TAAL_VELD, VertalingOnbeschikbaar,  # noqa: E402
                                        lijkt_al_in_taal, localiseer_sync)

ENGELS = {
    "title": "(1346) Black MyProtein Shorts - Men XL - New",
    "description": ("Authentic designer Shorts from MyProtein in size XL, "
                    "measurements available in the photos. Condition: new with tags."),
    "brand": "MyProtein",
}
NEDERLANDS = {
    "title": "Vintage tafellamp hoogte 44 cm",
    "description": ("Vintage tafellamp hoogte 44 cm, de lampenvoet is van messing en "
                    "marmer. De lampenkap is niet beschadigd en staat mooi."),
    "brand": None,
}


@pytest.fixture
def vertaling_ligt_plat(monkeypatch):
    """Zoals een lege API-rekening zich gedraagt: elke aanroep gooit."""
    def kapot(*a, **kw):
        raise VertalingOnbeschikbaar("de vertaling lukte niet")
    monkeypatch.setattr(cl, "_vertaal", kapot)


def test_engelse_advertentie_gaat_niet_naar_marktplaats(vertaling_ligt_plat):
    """Dit is de fout zelf: een Engelse tekst mocht niet op een NL-kanaal komen."""
    with pytest.raises(VertalingOnbeschikbaar):
        localiseer_sync(ENGELS, "marktplaats")


def test_nederlandse_advertentie_gaat_gewoon_door(vertaling_ligt_plat):
    """Een storing mag de verkopers die al Nederlands schrijven niet stilleggen."""
    uit = localiseer_sync(NEDERLANDS, "marktplaats")
    assert uit["title"] == NEDERLANDS["title"]
    assert uit[TAAL_VELD] == "nl"


def test_korte_titel_wordt_samen_met_de_tekst_gewogen(vertaling_ligt_plat):
    """"Vintage tafellamp hoogte 44 cm" alleen is te kort om een taal aan af te
    lezen; samen met de omschrijving eronder is het glashelder Nederlands."""
    assert lijkt_al_in_taal(NEDERLANDS["title"], "nl") is False
    assert lijkt_al_in_taal(f"{NEDERLANDS['title']}\n{NEDERLANDS['description']}", "nl") is True


def test_vinted_en_shopify_blijven_erbuiten(vertaling_ligt_plat):
    """Engelstalige kanalen vertalen niet naar het Nederlands, dus een NL-storing
    mag ze niet raken."""
    assert localiseer_sync(ENGELS, "shopify")["title"] == ENGELS["title"]


def test_bij_twijfel_wachten_en_niet_plaatsen(vertaling_ligt_plat):
    """Een kale trefwoordtekst is geen bewijs van taal. Dan wachten we."""
    kaal = {"title": "Kelim kleedje rood 73/40 cm", "description": "Kelim kleedje rood", "brand": None}
    with pytest.raises(VertalingOnbeschikbaar):
        localiseer_sync(kaal, "marktplaats")
