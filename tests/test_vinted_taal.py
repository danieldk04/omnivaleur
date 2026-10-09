"""Vinted-taal per verkoper (Janneke 31d28378, 09-10-2026).

Standaard gaat een Nederlands artikel VERTAALD naar het Engels op Vinted; dat is
geen kopie van wat de verkoper intikte. Met vinted_taal "nl" blijft het
Nederlands. Marktplaats en 2dehands blijven altijd Nederlands.
"""
import asyncio

from backend.services import crosslist, instellingen

ITEM = {"user_id": "j", "title": "Regenlaarzen Bergstein schoenmaat 24 zilver",
        "description": "Mooie regenlaarzen voor kinderen, goed als nieuw, met een stevige zool."}


def _zet(monkeypatch, taal):
    crosslist._VINTED_TAAL_CACHE.clear()
    monkeypatch.setattr(instellingen, "lees", lambda _u: instellingen._schoon({"vinted_taal": taal}))
    vertaald = []

    async def vertaal(tekst, doel, _merk=None):
        vertaald.append(doel)
        return f"[{doel}] {tekst}"
    monkeypatch.setattr(crosslist, "_translate_with_claude", vertaal)
    return vertaald


def test_standaard_wordt_nederlands_op_vinted_engels(monkeypatch):
    vertaald = _zet(monkeypatch, None)
    uit = asyncio.run(crosslist.localize_item_for_platform(dict(ITEM), "vinted"))
    assert uit["title"].startswith("[en] ") and uit[crosslist.TAAL_VELD] == "en"
    assert vertaald == ["en", "en"]


def test_met_nederlands_gekozen_blijft_het_nederlands(monkeypatch):
    vertaald = _zet(monkeypatch, "nl")
    uit = asyncio.run(crosslist.localize_item_for_platform(dict(ITEM), "vinted"))
    assert uit["title"] == ITEM["title"] and uit[crosslist.TAAL_VELD] == "nl"
    assert vertaald == []


def test_marktplaats_blijft_altijd_nederlands(monkeypatch):
    _zet(monkeypatch, "en")
    assert crosslist.taal_van_platform("marktplaats", "j") == "nl"
    assert crosslist.taal_van_platform("vinted", "j") == "en"
    assert crosslist.taal_van_platform("vinted") == "en"


def test_instelling_kent_alleen_nl_en_en():
    assert instellingen._schoon({"vinted_taal": "nl"})["vinted_taal"] == "nl"
    assert instellingen._schoon({"vinted_taal": "fr"})["vinted_taal"] == "en"
    assert instellingen._schoon({})["vinted_taal"] == "en"
