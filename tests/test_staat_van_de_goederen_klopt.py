"""De staat op de advertentie moet de staat van de verkoper zijn, geen gok.

Egbert Brouwer (Papa's Plectrums), 10-09-2026: "Alle listings die gelukt zijn
staan nu te boek als bijna nieuw, dit klopt natuurlijk niet." Hij verkoopt
nieuwe plectrums en miniatuurgitaren.

DE KETEN, GEMETEN OP 10-09-2026.

1. Bij het importeren komt de staat mee van het platform. Kwam er niets mee,
   dan vulde de import "good" in (backend/api/imports.py, _map_condition geeft
   "good" terug bij een lege bron). "good" is bij ons "Zo goed als nieuw".
2. Dat is geen leeg veld maar een verzonnen uitspraak over de goederen — en
   juist daarom zag niemand het. Vanaf dat moment is het veld GEVULD, dus sloeg
   elke verrijkronde het over ("alleen aanvullen wat leeg is").
3. Bij hem stonden zo 1.284 van de 5.533 artikelen op "good", terwijl zijn eigen
   3.000 openbare Marktplaats-advertenties allemaal "Nieuw" zeggen. Live gemeten
   via de openbare zoek-API: condition Counter({'Nieuw': 3000}).
4. Het platform gééft die staat gewoon mee in elk zoekresultaat, honderd
   advertenties per aanvraag, in "attributes". Die lazen we niet.

En één stap verderop zat dezelfde soort val: de wachtrij draagt een kopie van
het artikel van het moment van klikken. Zijn rij was na twee uur nog 402 lang.
Corrigeert hij in die tijd de staat in het dashboard, dan verandert dat aan de
wachtende opdrachten niets en gaat elke volgende advertentie tóch fout online.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.services.mp_enrich as mp  # noqa: E402

# Letterlijk zoals de openbare zoek-API het teruggaf op 10-09-2026 voor
# "Miniatuur replica Gibson SG Classic gitaar" van Papa's Plectrums.
ECHT_ZOEKRESULTAAT = {
    "itemId": "a1132824745",
    "title": "Miniatuur replica Gibson SG Classic gitaar - A. Young AC/DC",
    "priceInfo": {"priceCents": 1795, "priceType": "FIXED"},
    "vipUrl": "/v/muziek-en-instrumenten/a1132824745",
    "attributes": [
        {"key": "condition", "value": "Nieuw", "values": ["Nieuw"]},
        {"key": "delivery", "value": "Ophalen of Verzenden", "values": ["Ophalen of Verzenden"]},
    ],
}
# En één van zijn zoekertjes op 2dehands, met bieden aan: priceType MIN_BID.
MIN_BID_ZOEKERTJE = {
    "itemId": "m2441158873",
    "title": "Miniatuur replica Rasta gitaar - Bob Marley",
    "priceInfo": {"priceCents": 1795, "priceType": "MIN_BID"},
    "vipUrl": "/v/muziek-en-instrumenten/m2441158873",
    "attributes": [{"key": "condition", "value": "Zo goed als nieuw"}],
}


def test_de_staat_komt_gewoon_mee_uit_de_zoek_api():
    a = mp._naar_advertentie(ECHT_ZOEKRESULTAAT)
    assert a["conditie"] == "Nieuw", a


def test_een_geraden_staat_wordt_rechtgezet():
    item = {"id": "x", "title": "…", "condition": "good"}   # de importstandaard
    assert mp._conditie_correctie(item, mp._naar_advertentie(ECHT_ZOEKRESULTAAT)) \
        == {"condition": "new"}


def test_een_bewust_gezette_staat_blijft_staan():
    """Alleen de gok van de import wordt overruled, nooit een echte keuze."""
    for eigen in ("new", "new_with_tags", "fair", "poor"):
        item = {"id": "x", "condition": eigen}
        assert mp._conditie_correctie(item, mp._naar_advertentie(ECHT_ZOEKRESULTAAT)) == {}, eigen


def test_zonder_staat_op_het_platform_veranderen_we_niets():
    kaal = dict(ECHT_ZOEKRESULTAAT, attributes=[{"key": "delivery", "value": "Ophalen"}])
    assert mp._conditie_correctie({"condition": "good"}, mp._naar_advertentie(kaal)) == {}


def test_zegt_het_platform_hetzelfde_dan_gebeurt_er_niets():
    zgan = dict(ECHT_ZOEKRESULTAAT, attributes=[{"key": "condition", "value": "Zo goed als nieuw"}])
    assert mp._conditie_correctie({"condition": "good"}, mp._naar_advertentie(zgan)) == {}


def test_een_vraagprijs_met_bieden_blijft_een_vraagprijs():
    """MIN_BID is geen bied-advertentie maar een vraagprijs mét "bieden vanaf".

    Hier stond alleen FIXED, en daarmee gooide elke verrijkronde de prijs weg
    van iedere verkoper die bieden toestaat. Op 10-09-2026 stonden elf van de
    elf 2dehands-zoekertjes van Papa's Plectrums op MIN_BID.
    """
    assert mp._naar_advertentie(MIN_BID_ZOEKERTJE)["price"] == 17.95


def test_bieden_blijft_wel_zonder_prijs():
    bieden = dict(ECHT_ZOEKRESULTAAT, priceInfo={"priceCents": 0, "priceType": "FAST_BID"})
    assert mp._naar_advertentie(bieden)["price"] is None


def test_de_vorige_versie_liet_de_gok_staan():
    """Voor-en-na, met een vast commitnummer in plaats van HEAD."""
    import importlib.util
    import subprocess
    import tempfile
    bron = subprocess.run(["git", "show", "af816f80:backend/services/mp_enrich.py"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "_conditie_correctie" not in bron, "verkeerd commitnummer gepind"
    with tempfile.TemporaryDirectory() as m:
        pad = Path(m) / "oud_mp.py"
        pad.write_text(bron)
        spec = importlib.util.spec_from_file_location("oud_mp", pad)
        oud = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oud)
    a = oud._naar_advertentie(ECHT_ZOEKRESULTAAT)
    assert "conditie" not in a, "de oude versie las de staat al — dan bewijst dit niets"
    assert oud._naar_advertentie(MIN_BID_ZOEKERTJE)["price"] is None, (
        "de oude versie hield de MIN_BID-prijs al — dan bewijst dit niets")
