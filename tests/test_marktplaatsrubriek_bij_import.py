"""Egbert (Papa's Plectrums, 25-10 en 26-10-2026): "structureel neemt Omnivaleur de rubriek niet mee".

Nagemeten in zijn scan van 26-10 12:08: elke Marktplaats-advertentie kwam met
`category_id: "926"` (Verzamelen | Muziek, Artiesten en Beroemdheden) binnen, en
die ging bij het opslaan verloren. De rubriek werd uit de titel geraden, en onze
indeling had voor bandmerchandise geen rubriek: patches werden "babykleding" of
"unisex accessoires", zes artikelen bleven leeg.

Tweede fout, bij het plaatsen op 2dehands: de opzoeking van de Marktplaats-rubriek
zocht op "The Stone Roses -Elephant Stone" en vond niets, terwijl dezelfde
advertentie zonder het streepje wel gevonden werd. Gevonden-niet gold als "staat
niet op Marktplaats", dus ging het zoekertje met de geraden rubriek de deur uit.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import imports as imp  # noqa: E402
from backend.api import jobs as api  # noqa: E402
from backend.services import mp_enrich as M  # noqa: E402
from tests.test_gescande_advertentie_al_gekoppeld import (  # noqa: E402,F401
    _DB, _lokale_helpers)

JOB = {"id": "j1", "user_id": "u1", "platform": "marktplaats", "action": "scan"}
# Zoals de extensie het op 26-10 aanleverde (category_name kwam leeg binnen).
ECHTE_RIJ = {"platform_listing_id": "1533084450", "status": "ACTIVE",
             "title": "Jimi Hendrix - Band of Gypsys Sleutelhanger off. merchandise",
             "price": None, "category_id": "926", "category_name": ""}


def test_het_rubrieknummer_van_marktplaats_wordt_onze_rubriek():
    assert imp.rubriek_uit_marktplaats(ECHTE_RIJ) == {
        "gender": "muziek", "category": "muziek artiesten en merchandise"}
    assert "muziek artiesten en merchandise" in imp._ALL_CATEGORIES
    assert imp._TAK_VAN_RUBRIEK["muziek artiesten en merchandise"] == "muziek"


def test_een_onbekende_rubriek_blijft_geraden_en_wordt_niet_verzonnen():
    assert imp.rubriek_uit_marktplaats({"category_id": "99999"}) == {}
    assert imp.rubriek_uit_marktplaats({"category_id": "", "category_name": ""}) == {}
    assert imp.rubriek_uit_marktplaats({}) == {}


def test_de_scan_bewaart_de_rubriek_en_het_artikel_krijgt_hem():
    db = _DB(items=[], listings=[])
    api._store_scan_results(db, JOB, [dict(ECHTE_RIJ)])
    kand = db.import_candidates[0]
    assert kand["category"] == "muziek artiesten en merchandise"
    assert kand["gender"] == "muziek"
    item = imp._item_data_from_candidate(kand)
    assert item["category"] == "muziek artiesten en merchandise"
    assert item["gender"] == "muziek"


def test_een_rubriek_die_de_scan_zelf_meegeeft_blijft_staan():
    db = _DB(items=[], listings=[])
    rij = {**ECHTE_RIJ, "category": "antiek overige antiek", "gender": "antiek"}
    api._store_scan_results(db, JOB, [rij])
    assert db.import_candidates[0]["category"] == "antiek overige antiek"


def test_opzoeking_vindt_een_titel_met_een_vastgeplakt_streepje(monkeypatch):
    titel = "The Stone Roses -Elephant Stone - Opstrijk Patch off. merch."
    antwoord = {"listings": [{"itemId": "m1533053955", "categoryId": 926}],
                "facets": [{"key": "RelevantCategories", "categories": [
                    {"id": 895, "label": "Verzamelen"},
                    {"id": 926, "label": "Muziek, Artiesten en Beroemdheden",
                     "parentId": 895}]}]}

    async def nep_json(_client, _url, params=None):
        # Marktplaats vindt de advertentie alleen als het streepje weg is.
        vraag = (params or {}).get("query") or ""
        return antwoord if "-" not in vraag and vraag else {"listings": [{"itemId": "x"}]}

    monkeypatch.setattr(M, "_json", nep_json)
    uit = asyncio.run(M.rubriek_op_advertentienummer(None, 1, titel, "1533053955"))
    assert uit.get("l2") == 926 and uit.get("l1") == 895
