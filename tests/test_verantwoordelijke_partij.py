"""De "verantwoordelijke partij" is een keuze, geen verplichting.

AANLEIDING (30-08-2026, Amanda). Na een verversing zag ze op Marktplaats bij
"fabrikant, adres en mailadres" de bedrijfsgegevens van haar eigen bedrijf
staan: "Dat is niet de bedoeling."

Ze had die drie velden ook nooit vrijwillig ingevuld. Het dashboard weigerde
zonder die gegevens te publiceren naar Marktplaats en 2dehands, dus vulde ze ze
in — en sindsdien staan haar bedrijfsnaam, postadres en e-mailadres onder elke
advertentie, in het blok dat Marktplaats "Fabrikant" noemt. Bij tweedehands
brocante is de verkoper de fabrikant niet, en Marktplaats vraagt dat blok lang
niet in elke categorie.

Wat er nu geldt:
  * aan blijft aan — wie het al ingevuld heeft merkt niets;
  * het kan uit, en dan wordt er niets ingevuld én niets geblokkeerd;
  * de extensie klaagt alleen nog over een leeg veld als wij het hadden moeten
    vullen. Anders zou de schakelaar wél bestaan maar de advertentie alsnog
    stranden op de controle achteraf.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.instellingen import (  # noqa: E402
    FABRIKANT_MEESTUREN, STANDAARD, _schoon)

INGEVULD = {
    "fabrikant_naam": "Vintage Freaks",
    "fabrikant_adres": "Straat 1, 1234 AB Stad",
    "fabrikant_email": "info@vintagefreaks.nl",
}

SHARED = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")
CROSSLIST = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
APP = (ROOT / "frontend/app.html").read_text(encoding="utf-8")


def test_standaard_staat_hij_aan():
    """Anders zou deze wijziging bij iedereen het blok in één klap weghalen."""
    assert STANDAARD[FABRIKANT_MEESTUREN] is True
    assert _schoon({})[FABRIKANT_MEESTUREN] is True
    assert _schoon(None)[FABRIKANT_MEESTUREN] is True


def test_de_schakelaar_wordt_bewaard():
    assert _schoon({**INGEVULD, FABRIKANT_MEESTUREN: False})[FABRIKANT_MEESTUREN] is False
    assert _schoon({**INGEVULD, FABRIKANT_MEESTUREN: True})[FABRIKANT_MEESTUREN] is True


def test_uit_betekent_een_leeg_blok(monkeypatch):
    """Uit mag niet betekenen "we sturen toch je oude gegevens mee"."""
    import backend.services.instellingen as I

    monkeypatch.setattr(I, "lees", lambda uid: {**STANDAARD, **INGEVULD,
                                                FABRIKANT_MEESTUREN: False})
    assert I.fabrikant("wie-dan-ook") == {
        "manufacturer_name": "", "manufacturer_address": "", "manufacturer_email": ""}
    assert I.fabrikant_verplicht("wie-dan-ook") is False


def test_aan_stuurt_de_gegevens_gewoon_mee(monkeypatch):
    import backend.services.instellingen as I

    monkeypatch.setattr(I, "lees", lambda uid: {**STANDAARD, **INGEVULD})
    assert I.fabrikant("wie-dan-ook")["manufacturer_name"] == "Vintage Freaks"
    assert I.fabrikant_verplicht("wie-dan-ook") is True


def test_publiceren_wordt_niet_meer_geblokkeerd_als_hij_uitstaat():
    """De blokkade in crosslist hangt aan de schakelaar, niet aan de velden."""
    regel = [r for r in CROSSLIST.splitlines() if "manufacturer_details" in r]
    assert regel, "de blokkade bestaat niet meer — dan klopt deze test niet"
    blok = CROSSLIST.split("fabrikant_verplicht as _fab_verplicht")[1][:400]
    assert "_fab_verplicht(user_id) and not all(fab.values())" in blok, \
        "zonder deze voorwaarde blijft publiceren geblokkeerd voor wie hem uitzet"


def test_de_extensie_klaagt_alleen_over_wat_ze_moest_invullen():
    """Anders strandt de advertentie alsnog op de controle achteraf.

    Marktplaats toont dit blok in sommige categorieën gewoon op het formulier.
    Stond het er en was het leeg, dan gooide de extensie een fout en werd er
    NIETS gepubliceerd — ook als de verkoper het bewust leeg wilde laten.
    """
    fn = SHARED.split("function verifyMpGroupFields(item)")[1].split("\n  }")[0]
    assert 'item.manufacturer_name && emptyInput("textAttribute[manufacturerTradename]")' in fn
    assert 'item.manufacturer_email && emptyInput("textAttribute[manufacturerEmail]")' in fn


def test_er_wordt_nooit_iets_ingevuld_wat_er_niet_is():
    """fillManufacturer slaat lege waarden over — dat is wat "uit" betekent."""
    fn = SHARED.split("function fillManufacturer(item)")[1].split("\n  }")[0]
    assert "if (!val || !String(val).trim()) continue;" in fn


def test_de_schakelaar_staat_in_het_scherm():
    assert 'id="fabrikant-meesturen"' in APP
    assert "saveFabrikantMeesturen()" in APP
    assert "async function saveFabrikantMeesturen()" in APP


def test_het_scherm_blokkeert_publish_niet_meer_als_hij_uitstaat():
    fn = APP.split("function fabrikantCompleet()")[1].split("\n}")[0]
    assert "s.fabrikant_meesturen === false" in fn, \
        "anders staat de Publish-knop op slot met een reden die niet meer geldt"


def test_de_waarschuwing_verdwijnt_als_hij_uitstaat():
    fn = APP.split("function toonFabrikant(data)")[1].split("\n}")[0]
    assert "(leeg && meesturen)" in fn, \
        '"publiceren staat stil" is niet waar voor wie het blok niet meestuurt'
