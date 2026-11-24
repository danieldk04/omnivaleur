"""Wandlampen, kinderkamer decoratie en paraplu's (24-11-2026, Esther, hetisvintastisch).

Nummers en groepen zijn op 24-11 gemeten: zoek-API van marktplaats.nl en 2dehands.be
(zelfde nummers) en het ingelogde plaatsformulier (groepen 137, 154 en 197).
Deze proef bewaakt dat alle plekken dezelfde sleutel en dezelfde nummers kennen.
"""
import json
import re
from pathlib import Path

from backend.api import imports, jobs

ROOT = Path(__file__).resolve().parent.parent
RUBRIEKEN = {
    "wonen wandlampen": (504, 1622, None, "wonen"),
    "wonen kinderkamer decoratie": (565, 1671, 154, "wonen"),
    "sieraden paraplus": (1826, 3150, 197, "sieraden"),
}


def _lees(pad):
    return (ROOT / pad).read_text(encoding="utf-8")


def test_taxonomie_kent_de_drie_in_de_juiste_tak():
    for sleutel, (_, _, _, tak) in RUBRIEKEN.items():
        assert sleutel in imports._TAXONOMY[tak], sleutel


def test_servernummers_en_extensie_hebben_dezelfde_nummers():
    ext = _lees("extension/background.js")
    for sleutel, (l1, l2, bucket, _) in RUBRIEKEN.items():
        assert jobs._MP_NUMMERS_VAN_DE_SERVER[sleutel]["l1"] == l1
        assert jobs._MP_NUMMERS_VAN_DE_SERVER[sleutel]["l2"] == l2
        m = re.search(r'"%s":\s*\{([^}]*)\}' % re.escape(sleutel), ext)
        assert m, sleutel
        regel = m.group(1)
        assert f"cat1: {l1}" in regel and f"cat3: {l2}" in regel
        assert (f"bucketId: {bucket}" in regel) == (bucket is not None)


def test_marktplaats_wacht_niet_maar_vinted_wacht_op_de_nieuwe_extensie():
    for sleutel in RUBRIEKEN:
        assert jobs._RUBRIEK_VANAF_VERSIE[sleutel] == (1, 0, 435)
        for platform in ("marktplaats", "2dehands"):
            assert jobs._minimale_versie_voor_rubriek(
                {"platform": platform, "payload": {"category": sleutel}}) is None
        assert jobs._minimale_versie_voor_rubriek(
            {"platform": "vinted", "payload": {"category": sleutel}}) == (1, 0, 435)


def test_uitgaande_opdracht_krijgt_de_nummers_van_de_server():
    for sleutel, (l1, l2, _, _) in RUBRIEKEN.items():
        job = {"platform": "2dehands", "payload": {"category": sleutel}}
        assert jobs._mp_nummers_van_de_server([job]) == 1
        assert (job["payload"]["mp_category"]["l1"], job["payload"]["mp_category"]["l2"]) == (l1, l2)


def test_extensieversie_is_minstens_de_poortversie():
    manifest = json.loads(_lees("extension/manifest.json"))
    versie = tuple(int(x) for x in manifest["version"].split("."))
    assert versie >= (1, 0, 435)


def test_alle_andere_plekken_kennen_de_sleutels():
    plekken = ["extension/content/vinted.js", "frontend/app.html", "backend/platforms/ebay.py"]
    for pad in plekken:
        tekst = _lees(pad)
        for sleutel in RUBRIEKEN:
            assert sleutel in tekst, (pad, sleutel)
    assert "wonen wandlampen" in _lees("backend/platforms/shopify_importer.py")
    assert "wonen kinderkamer decoratie" in _lees("backend/platforms/shopify_importer.py")


def test_nederlandse_namen_in_het_dashboard():
    nl = json.loads(_lees("frontend/i18n/nl.json"))
    assert nl["Wall Lamps"] == "Wandlampen"
    assert nl["Nursery Decor"] == "Kinderkamerdecoratie"
    assert nl["Umbrellas"] == "Paraplu's"
