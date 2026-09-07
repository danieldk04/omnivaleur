"""Vraag geen maat en merk aan een speld, een patch of een sleutelhanger.

WAAROM DIT ER IS (Egbert Brouwer, papas-plectrums, 07-09-2026)
"Ik kom nog steeds gaten tegen in mijn listings."

Van zijn 5.533 geïmporteerde artikelen staan er 2.343 in "unisex accessoires":
bandana's, patches, pins, sleutelhangers. Die tak valt in onze indeling onder
kleding, dus vroeg het dashboard bij elk van die artikelen om merk, maat en
kleur, en blokkeerde publiceren naar Marktplaats en 2dehands zolang die er niet
stonden. Ze bestaan niet: een patch heeft geen maat.

GEMETEN, NIET AANGENOMEN (07-09-2026, in het opdrachtenlogboek): van de
geslaagde plaatsingen in "unisex accessoires" hadden er 13 van de 14 GEEN maat,
en in "kinderen accessoires" 16 van de 21. Marktplaats neemt ze dus gewoon aan.
De eis kwam van ons.

Dit is de tweede ronde op dezelfde fout: op 03-09-2026 is hij al uit de
knopteller gehaald (_mist_iets in mp_enrich.py), maar niet uit de eis zelf.

En zonder categorie weten we de tak niet, dus vragen we dan alleen om de
categorie in plaats van om vijf velden die misschien nergens voor nodig zijn.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.crosslist import _missing_fields_per_platform, _is_non_clothing  # noqa: E402

KANALEN = ["marktplaats", "2dehands"]


def _item(**kw):
    basis = {
        "title": "ZZ Top Logo bandana officiele merchandise",
        "description": "Officiele merchandise, nieuw.",
        "price": 12.95,
        "photo_urls": ["https://img/1.jpg"],
        "category": "unisex accessoires",
        "brand": "", "size": "", "color": "", "gender": "",
    }
    basis.update(kw)
    return basis


def test_een_accessoire_zonder_maat_is_gewoon_publiceerbaar():
    assert _missing_fields_per_platform(_item(), KANALEN) == {}


def test_dat_geldt_ook_voor_de_andere_accessoiretakken():
    for cat in ("accessoires dames", "kinderen accessoires"):
        assert _missing_fields_per_platform(_item(category=cat), KANALEN) == {}, cat


def test_echte_kleding_moet_nog_steeds_een_maat_hebben():
    ontbreekt = _missing_fields_per_platform(_item(category="heren truien"), KANALEN)
    assert "size" in ontbreekt["marktplaats"]
    assert "brand" in ontbreekt["marktplaats"]


def test_zonder_categorie_vragen_we_alleen_om_de_categorie():
    ontbreekt = _missing_fields_per_platform(_item(category=""), KANALEN)
    assert ontbreekt["marktplaats"] == ["category"]
    assert ontbreekt["2dehands"] == ["category"]


def test_wat_echt_ontbreekt_wordt_nog_steeds_gemeld():
    ontbreekt = _missing_fields_per_platform(_item(price=None, photo_urls=[]), KANALEN)
    assert "price" in ontbreekt["marktplaats"]
    assert "photos" in ontbreekt["marktplaats"]


def test_accessoires_tellen_als_maatloos():
    assert _is_non_clothing({"category": "unisex accessoires"})
    assert not _is_non_clothing({"category": "unisex truien"})


def test_de_muziektak_blijft_werken_zoals_hij_werkte():
    assert _missing_fields_per_platform(_item(category="muziek instrumenten toebehoren"), KANALEN) == {}
