"""Waar de verkoper staat, van het scherm tot op het formulier.

AANLEIDING (10-09-2026, De Juiste Toon). Zijn zoekertjes op 2dehands kwamen
niet door, veertien keer achter elkaar, allemaal op onze eigen weigering
"postcode leeg". Nagemeten op een ingelogd 2dehands-account: het account kent
maar één adresgegeven, een postcode in Belgisch formaat, en hij woont in
Etten-Leur. Er is daar geen scherm waarin hij dat kan zetten; de keuze
"Buitenland" met land en woonplaats bestaat alleen op het zoekertje zelf, en
die onthoudt de site niet — vandaar zijn 402 zoekertjes op acht spellingen van
"Etten-Leur".

Deze proef bewaakt de hele keten: het scherm slaat land, woonplaats en postcode
op, de server zet ze in elke opdracht, en de extensie heeft een stap die ze op
het formulier invult. Het formulierwerk zelf staat in
tests/locatie-op-het-formulier-test.js, met een voor-en-na-proef.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.instellingen import STANDAARD, _schoon, locatie  # noqa: E402

SHARED = (ROOT / "extension/content/shared.js").read_text(encoding="utf-8")
CROSSLIST = (ROOT / "backend/services/crosslist.py").read_text(encoding="utf-8")
RELIST = (ROOT / "backend/services/relist.py").read_text(encoding="utf-8")
APP = (ROOT / "frontend/app.html").read_text(encoding="utf-8")
TWEEDEHANDS = (ROOT / "extension/content/tweedehands.js").read_text(encoding="utf-8")
MARKTPLAATS = (ROOT / "extension/content/marktplaats.js").read_text(encoding="utf-8")

TOON = {"locatie_land": "Nederland", "locatie_plaats": "Etten-Leur",
        "locatie_postcode": "4871 AB"}


def test_leeg_is_de_standaard():
    """Wie niets invult houdt precies het gedrag dat hij altijd had."""
    for veld in ("locatie_land", "locatie_plaats", "locatie_postcode"):
        assert STANDAARD[veld] == ""
        assert _schoon({})[veld] == ""
        assert _schoon(None)[veld] == ""


def test_wat_erin_gaat_komt_er_zo_weer_uit():
    """Het land wordt op de site op naam gezocht, dus het mag niet verbouwd
    worden. Een hoofdletterkuur zou "Verenigd Koninkrijk" onvindbaar maken."""
    schoon = _schoon(TOON)
    assert schoon["locatie_land"] == "Nederland"
    assert schoon["locatie_plaats"] == "Etten-Leur"
    assert schoon["locatie_postcode"] == "4871 AB"
    assert _schoon({"locatie_plaats": "  Etten-Leur  "})["locatie_plaats"] == "Etten-Leur"
    assert len(_schoon({"locatie_plaats": "x" * 400})["locatie_plaats"]) == 100
    assert _schoon({"locatie_land": None})["locatie_land"] == ""


def test_de_opdracht_draagt_de_locatie_mee(monkeypatch):
    import backend.services.instellingen as I

    monkeypatch.setattr(I, "lees", lambda uid: {**STANDAARD, **TOON})
    assert locatie("wie-dan-ook") == {"location_country": "Nederland",
                                      "location_city": "Etten-Leur",
                                      "location_postcode": "4871 AB"}
    monkeypatch.setattr(I, "lees", lambda uid: dict(STANDAARD))
    assert locatie("wie-dan-ook") == {"location_country": "", "location_city": "",
                                      "location_postcode": ""}


def test_alle_publicatiepaden_zetten_hem_erbij():
    """Vier paden zetten een 'create' klaar. Eén ervan overslaan betekent dat het
    bij herplaatsen wél goed gaat en bij publiceren niet, of andersom."""
    assert "payload.update(locatie(user_id))" in CROSSLIST
    assert "**locatie(user_id)" in RELIST, "het herstelpad mist de locatie"
    assert "create_payload.update(_locatie(user_id))" in RELIST, \
        "het herplaatspad mist de locatie"


def test_de_extensie_heeft_de_stap_en_gebruikt_de_gemeten_namen():
    """De veldnamen zijn live van het formulier gelezen (11-09-2026). Verandert
    er hier iets zonder nieuwe meting, dan vult de stap stilletjes niets in."""
    assert "async function vulLocatie(item)" in SHARED
    for naam in ('"syi-address-radio-home"', '"syi-address-radio-abroad"',
                 'select#country', 'contactInformation.foreignCity',
                 'contactInformation.postCode'):
        assert naam in SHARED, naam
    assert "vulLocatie," in SHARED, "de stap wordt niet geëxporteerd"
    for bron, naam in ((TWEEDEHANDS, "2dehands"), (MARKTPLAATS, "marktplaats")):
        assert "vulLocatie(item)" in bron, f"{naam} roept de stap niet aan"


def test_het_scherm_vraagt_erom_en_slaat_het_op():
    for stuk in ('id="locatie-land"', 'id="locatie-plaats"', 'id="locatie-postcode"',
                 "function saveLocatie()", "function toonLocatie(data)",
                 "toonLocatie(data);"):
        assert stuk in APP, stuk
    # De landnamen moeten exact die van de site zijn; deze zijn op 11-09-2026
    # uit de landenlijst van het 2dehands-formulier gecontroleerd.
    for land in ("Nederland", "België", "Duitsland", "Verenigd Koninkrijk", "Tsjechië"):
        assert f'<option value="{land}">{land}</option>' in APP, land
