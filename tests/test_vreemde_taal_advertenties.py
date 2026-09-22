"""Het script dat Toons Duitse advertenties opzoekt, kiest de juiste.

WAAROM DIT ER IS (22-09-2026). Na de reparatie van de taalherkenning blijven de
advertenties die al online staan in het Duits tot ze opnieuw geplaatst worden.
Zijn vraag was: "Dus dan moet ik alles nakijken?" Nee — maar dan moet het script
dat ze opzoekt wél de goede eruit halen, want op die uitkomst wordt besloten
welke advertentie wordt weggehaald en opnieuw geplaatst. Dat is niet terug te
draaien: de advertentie krijgt een nieuw nummer en begint onderaan.

Deze proef draait `kies_verdachte` zonder database en zonder Marktplaats, met
zijn echte advertentietekst.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from vreemde_taal_advertenties import kies_verdachte  # noqa: E402

WINKELBLOK = (
    "Kijk op onze webshop Dejuistetoon voor het volledige en actuele aanbod.\n\n"
    "Wil je onze collectie in het echt bekijken , maak een afspraak.\n\n"
    "Alle dagen op afspraak | Do & Za 10.00 uur tot 17.00 uur\n\n"
    "Locatie: Mon Plaisir 19, Etten-Leur."
)
DUITS = (
    "Herren Original Trachten Lederhosen\nGröße 50\nFarbe Khaki\n"
    "Material Leder/Wildleder\nFlach gemessen 53 Zentimeter siehe letztes Foto\n"
    "Mehrere Modelle auf Lager Damen/Herren\n\n"
)
NEDERLANDS = (
    "Kenmerkt zich door geometrische patronen en levendige kleuren\n\n"
    "In vaal rode kleur met blauw ecru en oranje accenten\n\nAfmeting: 135/80 cm\n\n"
)
ENGELS = (
    "Black MyProtein shorts for men, size XL. This item is new with tags and comes "
    "from a smoke free home. Please check the measurements in the photos.\n\n"
)

ITEMS = {
    "i-duits":  {"id": "i-duits",  "title": "Heren originele trachten Lederhosen",
                 "description": DUITS + WINKELBLOK},
    "i-nl":     {"id": "i-nl",     "title": "Handgeknoopt Perzisch Shiraz wollen tapijt",
                 "description": NEDERLANDS + WINKELBLOK},
    "i-engels": {"id": "i-engels", "title": "Black MyProtein Shorts - Men XL",
                 "description": ENGELS + WINKELBLOK},
    "i-kort":   {"id": "i-kort",   "title": "Kelim kleedje rood 73/40 cm",
                 "description": "Kelim kleedje rood 73/40 cm"},
}
ADVERTENTIES = [
    {"item_id": "i-duits",  "platform": "marktplaats", "platform_listing_id": "a1"},
    {"item_id": "i-duits",  "platform": "2dehands",    "platform_listing_id": "m1"},
    {"item_id": "i-nl",     "platform": "marktplaats", "platform_listing_id": "a2"},
    {"item_id": "i-engels", "platform": "marktplaats", "platform_listing_id": "a3"},
    {"item_id": "i-kort",   "platform": "marktplaats", "platform_listing_id": "a4"},
]


def _ids(uitkomst):
    return sorted(rij["platform_listing_id"] for rij, _item, _taal in uitkomst)


def test_de_duitse_advertentie_wordt_gevonden_op_beide_kanalen():
    assert _ids(kies_verdachte(ADVERTENTIES, ITEMS)) == ["a1", "a3", "m1"]


def test_de_nederlandse_advertentie_blijft_erbuiten():
    assert "a2" not in _ids(kies_verdachte(ADVERTENTIES, ITEMS))


def test_een_korte_trefwoordtekst_blijft_erbuiten():
    """Die staat in geen enkele taal overtuigend; die mag niet herplaatst worden."""
    assert "a4" not in _ids(kies_verdachte(ADVERTENTIES, ITEMS))


def test_de_taal_wordt_erbij_gemeld():
    per_id = {rij["platform_listing_id"]: taal for rij, _i, taal in kies_verdachte(ADVERTENTIES, ITEMS)}
    assert per_id["a1"] == "de"
    assert per_id["a3"] == "en"


def test_bevat_beperkt_tot_de_lederhosen():
    """Waar haast bij is gaat voor: de oktoberfeesten."""
    assert _ids(kies_verdachte(ADVERTENTIES, ITEMS, bevat="lederhos")) == ["a1", "m1"]
    assert _ids(kies_verdachte(ADVERTENTIES, ITEMS, bevat="LEDERHOS")) == ["a1", "m1"]


def test_een_advertentie_zonder_artikel_wordt_overgeslagen():
    los = ADVERTENTIES + [{"item_id": "weg", "platform": "marktplaats",
                           "platform_listing_id": "a9"}]
    assert "a9" not in _ids(kies_verdachte(los, ITEMS))


def test_zonder_advertenties_gebeurt_er_niets():
    assert kies_verdachte([], ITEMS) == []
