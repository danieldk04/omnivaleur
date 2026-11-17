"""Rubrieken in groepen (services/rubriek_groepen): geen netwerk, geen database."""
import asyncio
import json

from backend.api import imports as I
from backend.services import rubriek_groepen as R


def _items(n):
    return [{"id": f"i{k}", "title": f"Vintage vaas {k}", "description": "keramiek",
             "brand": None, "category": None, "gender": None} for k in range(n)]


def test_systeemtekst_bevat_regels_maar_geen_artikel():
    s = R._systeemtekst()
    assert "Pick the single best" in s and "JSON array" in s
    assert "Brand:" not in s.split("Pick the single best")[0][-40:]
    assert "Respond with ONLY JSON:" not in s  # de enkelvoudige slotzin is vervangen


def test_antwoord_wordt_gecontroleerd():
    groep = _items(5)
    raw = json.dumps([
        {"n": 1, "gender": "x", "category": "antiek vazen", "confidence": "high"},
        {"n": 2, "gender": "x", "category": "bestaat niet", "confidence": "high"},
        {"n": 3, "gender": "x", "category": "antiek vazen", "confidence": "low"},
        {"n": 4, "gender": "none", "category": "none", "confidence": "high"},
        {"n": 99, "gender": "x", "category": "antiek vazen", "confidence": "high"},
    ])
    uit = R._lees_antwoord("tekst voor " + raw + " tekst na", groep)
    assert uit == {"i0": {"gender": "antiek", "category": "antiek vazen"},
                   "i3": {"geen_tak": True}}   # verzonnen, onzeker en nummer 99 tellen niet


def test_schoen_onder_andere_rubriek_blijft_leeg():
    groep = [{"id": "s", "title": "Witte Puma shoes", "description": "", "brand": "Puma"}]
    raw = json.dumps([{"n": 1, "gender": "x", "category": "antiek vazen", "confidence": "high"}])
    assert R._lees_antwoord(raw, groep) == {}


def test_deel_in_splitst_in_groepen_van_twintig(monkeypatch):
    aantallen = []

    def nep(systeem, gebruiker, n):
        aantallen.append(n)
        return json.dumps([{"n": k + 1, "gender": "x", "category": "antiek vazen",
                            "confidence": "high"} for k in range(n)])
    monkeypatch.setattr(R, "_vraag_claude", nep)
    monkeypatch.setattr(R.settings, "anthropic_api_key", "test")
    uit = asyncio.run(R.deel_in(_items(45)))
    assert sorted(aantallen) == [5, 20, 20] and len(uit) == 45


def test_mislukte_groep_telt_niet_als_antwoord(monkeypatch):
    def stuk(*a):
        raise RuntimeError("storing")
    monkeypatch.setattr(R, "_vraag_claude", stuk)
    monkeypatch.setattr(R.settings, "anthropic_api_key", "test")
    echte = asyncio.sleep
    monkeypatch.setattr(R.asyncio, "sleep", lambda s: echte(0))
    assert asyncio.run(R.deel_in(_items(3))) == {}


def test_dagplafond(monkeypatch):
    monkeypatch.setattr(R, "DAGMAX_ARTIKELEN", 25)
    R._DAG.update(dag=None, n=0)
    assert R._ruimte(20) and not R._ruimte(20)


def test_ronde_vult_alleen_lege_rubrieken(monkeypatch):
    items = _items(3)
    items[1]["category"] = "wonen stoelen"   # de verkoper deelde hem tussendoor zelf in
    geschreven = {}
    monkeypatch.setattr(R, "_lees_kandidaten", lambda db, u, l: items)
    monkeypatch.setattr(R, "_schrijf_rubriek", lambda db, i, p: geschreven.update({i: p}))
    monkeypatch.setattr(R, "get_db", lambda: object())

    async def nep(its):
        return {x["id"]: {"gender": "antiek", "category": "antiek vazen"} for x in its}
    monkeypatch.setattr(R, "deel_in", nep)
    res = asyncio.run(R.vul_rubrieken_in_groepen())
    assert set(geschreven) == {"i0", "i2"} and res["gevuld"] == 2
