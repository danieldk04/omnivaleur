"""Vinted krijgt precies wat de verkoper intikte (Daniel, 09-10-2026).

Tot 09-10-2026 ging elke tekst op Vinted vertaald naar het Engels de deur uit,
ook een Nederlandse tekst op vinted.nl (Janneke: "Ik heb dit graag gewoon in het
Nederlands"). Nu: standaard geen vertaling voor Vinted; alleen wie zelf
vinted_taal "en" kiest krijgt Engels. Marktplaats en 2dehands blijven altijd
Nederlands, ook als de verkoper in het Engels schreef.
"""
import asyncio

import pytest

from backend.services import crosslist, instellingen

NL = {"user_id": "j", "title": "Regenlaarzen Bergstein schoenmaat 24 zilver",
      "description": "Mooie regenlaarzen voor kinderen, goed als nieuw, met een stevige zool."}
EN = {"user_id": "j", "title": "Grey Ralph Lauren cable knit jumper size L",
      "description": "Beautiful wool jumper in very good condition, barely worn, from a smoke free home."}


@pytest.fixture
def zet(monkeypatch):
    def _zet(keuze):
        crosslist._VINTED_TAAL_CACHE.clear()
        rauw = {} if keuze is None else {"vinted_taal": keuze}
        monkeypatch.setattr(instellingen, "lees", lambda _u: instellingen._schoon(rauw))
        vertaald = []

        async def vertaal(tekst, doel, _merk=None):
            vertaald.append(doel)
            return f"[{doel}] {tekst}"
        monkeypatch.setattr(crosslist, "_translate_with_claude", vertaal)
        monkeypatch.setattr(crosslist, "_vertaal", lambda t, doel, _m=None: f"[{doel}] {t}")
        return vertaald
    return _zet


@pytest.mark.parametrize("item", [NL, EN])
def test_standaard_gaat_de_eigen_tekst_ongewijzigd_naar_vinted(zet, item):
    vertaald = zet(None)
    uit = asyncio.run(crosslist.localize_item_for_platform(dict(item), "vinted"))
    assert uit["title"] == item["title"] and uit["description"] == item["description"]
    assert vertaald == []
    assert crosslist.localiseer_sync(dict(item), "vinted")["title"] == item["title"]


def test_wie_engels_kiest_krijgt_een_vertaling(zet):
    vertaald = zet("en")
    uit = asyncio.run(crosslist.localize_item_for_platform(dict(NL), "vinted"))
    assert uit["title"] == "[en] " + NL["title"] and vertaald == ["en", "en"]


@pytest.mark.parametrize("keuze", [None, "en"])
def test_marktplaats_en_2dehands_altijd_nederlands(zet, keuze):
    zet(keuze)
    for pf in ("marktplaats", "2dehands"):
        uit = asyncio.run(crosslist.localize_item_for_platform(dict(EN), pf))
        assert uit["title"] == "[nl] " + EN["title"]


def test_publiceren_kiest_per_kanaal(zet, monkeypatch):
    """De echte keuze in publish_to_platforms: welke tekst krijgt welk kanaal."""
    zet(None)
    assert crosslist.taal_van_platform("vinted", "j") is None
    assert crosslist.taal_van_platform("vinted") is None
    assert crosslist.taal_van_platform("marktplaats", "j") == "nl"
    zet("en")
    assert crosslist.taal_van_platform("vinted", "j") == "en"


def test_instelling_kent_alleen_zelf_en_en():
    assert instellingen._schoon({})["vinted_taal"] == "zelf"
    assert instellingen._schoon({"vinted_taal": "en"})["vinted_taal"] == "en"
    assert instellingen._schoon({"vinted_taal": "nl"})["vinted_taal"] == "zelf"
