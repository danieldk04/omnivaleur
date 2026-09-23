"""Het script dat Toons Duitse advertenties opzoekt, kiest de juiste.

WAAROM DIT ER IS (22-09-2026). Na de reparatie van de taalherkenning blijven de
advertenties die al online staan in de verkeerde taal tot ze opnieuw geplaatst
worden. Op die uitkomst wordt besloten welke advertentie wordt weggehaald en
opnieuw geplaatst. Dat is niet terug te draaien: de advertentie krijgt een
nieuw nummer en begint onderaan.

23-09-2026: de keuze kijkt naar de LIVE tekst (de openbare zoek-API van het
kanaal), niet naar de items-rij. Bij Toon was elke items-rij Nederlands terwijl
er 10 advertenties Duits of Engels online stonden; de eerste versie zag er nul.
De proef `test_nederlands_artikel_met_duitse_advertentie_wordt_gevonden` legt
precies dat geval vast.

Deze proef draait `kies_verdachte` zonder database en zonder Marktplaats, met
zijn echte advertentietekst zoals de zoek-API hem teruggeeft (afgekapt op 200
tekens, in kleine letters).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vreemde_taal_advertenties import ADVERTENTIENUMMER, kies_verdachte  # noqa: E402

# Letterlijk van de zoek-API, m2443801898, 23-09-2026.
DUITS_LIVE = ("Herren original trachten lederhosen größe 50 farbe khaki material "
              "leder/wildleder flach gemessen 53 zentimeter siehe letztes foto mehrere "
              "modelle auf lager damen/herren info dejuistetoon #dejuistetoon")
NEDERLANDS_LIVE = ("Kenmerkt zich door geometrische patronen en levendige kleuren in vaal "
                   "rode kleur met blauw ecru en oranje accenten afmeting: 135/80 cm kijk "
                   "op onze webshop dejuistetoon voor het volledige en actuele aanbod")
ENGELS_LIVE = ("Black MyProtein shorts for men, size XL. This item is new with tags and "
               "comes from a smoke free home. Please check the measurements in the photos.")

OPENBAAR = [
    {"itemId": "m1", "title": "Heren originele trachten Lederhosen", "description": DUITS_LIVE},
    {"itemId": "m2", "title": "Handgeknoopt Perzisch Shiraz wollen tapijt",
     "description": NEDERLANDS_LIVE},
    {"itemId": "m3", "title": "Black MyProtein Shorts - Men XL", "description": ENGELS_LIVE},
    {"itemId": "m4", "title": "Kelim kleedje rood 73/40 cm", "description": "Kelim kleedje rood 73/40 cm"},
    {"itemId": "m5", "title": "Heren lederhosen bruin", "description": DUITS_LIVE},
]
# Onze boeken: m5 staat live op zijn lijst maar niet bij ons.
ONZE = {
    lid: {"item_id": f"i-{lid}", "platform": "marktplaats", "platform_listing_id": lid,
          "status": "active", "titel": t}
    for lid, t in [("m1", "Heren originele trachten Lederhosen"),
                   ("m2", "Handgeknoopt Perzisch Shiraz wollen tapijt"),
                   ("m3", "Black MyProtein Shorts - Men XL"),
                   ("m4", "Kelim kleedje rood 73/40 cm")]
}


def _ids(uitkomst):
    return sorted(adv["itemId"] for _rij, adv, _taal in uitkomst)


def test_nederlands_artikel_met_duitse_advertentie_wordt_gevonden():
    """Het geval van Toon: titel Nederlands, live omschrijving Duits."""
    per_id = {adv["itemId"]: (rij, taal) for rij, adv, taal in kies_verdachte(OPENBAAR, ONZE)}
    rij, taal = per_id["m1"]
    assert taal == "de"
    assert rij["item_id"] == "i-m1"


def test_duits_en_engels_gevonden_nederlands_niet():
    assert _ids(kies_verdachte(OPENBAAR, ONZE)) == ["m1", "m3", "m5"]


def test_de_taal_wordt_erbij_gemeld():
    per_id = {adv["itemId"]: taal for _r, adv, taal in kies_verdachte(OPENBAAR, ONZE)}
    assert per_id["m3"] == "en"


def test_een_korte_trefwoordtekst_blijft_erbuiten():
    """Die staat in geen enkele taal overtuigend; die mag niet herplaatst worden."""
    assert "m4" not in _ids(kies_verdachte(OPENBAAR, ONZE))


def test_advertentie_buiten_onze_boeken_wordt_gemeld_zonder_rij():
    """Niet verzwijgen, maar ook niet opnieuw plaatsen: we weten niet welk artikel het is."""
    per_id = {adv["itemId"]: rij for rij, adv, _t in kies_verdachte(OPENBAAR, ONZE)}
    assert per_id["m5"] is None


def test_bevat_kijkt_naar_de_live_titel():
    assert _ids(kies_verdachte(OPENBAAR, ONZE, bevat="lederhos")) == ["m1", "m5"]
    assert _ids(kies_verdachte(OPENBAAR, ONZE, bevat="LEDERHOS")) == ["m1", "m5"]


def test_de_items_rij_speelt_geen_rol():
    """Ook als onze eigen titel iets anders zegt, telt wat er online staat."""
    anders = {k: {**v, "titel": "Nederlandse titel"} for k, v in ONZE.items()}
    assert _ids(kies_verdachte(OPENBAAR, anders)) == ["m1", "m3", "m5"]


def test_zonder_advertenties_gebeurt_er_niets():
    assert kies_verdachte([], ONZE) == []


def test_alleen_echte_advertentienummers():
    """Admarkt- en webwinkelnummers staan niet op de openbare lijst."""
    assert ADVERTENTIENUMMER.match("m2443801898")
    assert not ADVERTENTIENUMMER.match("1502022894")
