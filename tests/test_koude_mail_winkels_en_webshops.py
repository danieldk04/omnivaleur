"""Winkels en webshops krijgen een tekst die over hén gaat, niet over Marktplaats.

AANLEIDING, 27-09-2026. Nieuwe leads komen sinds deze week ook van Google,
OpenStreetMap en winkelgidsen. De mailteksten vulden `[platform]` voor iedereen
behalve 2dehands met "Marktplaats", en versie B zegt letterlijk "Alles staat nu
alleen op Marktplaats". Een vintagewinkel kreeg dus "Vraagje over jullie
Marktplaats-aanbod". Nu: platform "webshop" of "winkel", altijd versie A, en een
openingszin over hun eigen shop.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import leadgen_mail as L  # noqa: E402

WEBSHOP = {"email": "info@vintagewinkel-voorbeeld.nl", "platform": "webshop", "je_jullie": "Jullie",
           "site": "https://vintagewinkel-voorbeeld.nl", "shopsysteem": "Shopify"}
WINKEL = {"email": "hallo@antiek-voorbeeld.nl", "platform": "winkel", "je_jullie": "Jullie",
          "site": "https://antiek-voorbeeld.nl"}
MP = {"email": "verkoper@voorbeeld.nl", "platform": "MP", "ads": 250, "je_jullie": "Je"}


def _b_adres():
    """Een adres dat volgens de hash versie B zou krijgen."""
    for i in range(100):
        adres = f"proef{i}@voorbeeld.nl"
        if L._variant(adres) == "B":
            return adres
    raise AssertionError("geen B-adres gevonden")


def test_platformnaam_volgt_de_bron():
    assert L._platformnaam(WEBSHOP) == "webshop"
    assert L._platformnaam(WINKEL) == "winkel"
    assert L._platformnaam(MP) == "Marktplaats"
    assert L._platformnaam({"platform": "2dehands"}) == "2dehands"


def test_openingszin_noemt_geen_marktplaats():
    for lead in (WEBSHOP, WINKEL):
        zin = L._haakje(lead)
        assert "Marktplaats" not in zin and "advertenties" not in zin
        assert "voorbeeld.nl" in zin
    assert "Marktplaats" in L._haakje(MP)


def test_winkels_krijgen_nooit_versie_b():
    adres = _b_adres()
    assert L._variant(adres) == "B"
    assert L._variant(adres, None, {**WEBSHOP, "email": adres}) == "A"
    assert L._variant(adres, None, {**MP, "email": adres}) == "B"


def test_extra_leads_tellen_mee(monkeypatch):
    lijsten = {"mp_leads": [MP], "2dh_leads": [], "extra_leads": [WEBSHOP]}
    monkeypatch.setattr(L, "_load", lambda pad: lijsten.get(pad.stem, []))
    adressen = {l["email"] for l in L._leads()}
    assert WEBSHOP["email"] in adressen and MP["email"] in adressen
