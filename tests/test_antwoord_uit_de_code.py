"""De klantenservice zoekt een feitelijke vraag eerst zelf op in de code.

AANLEIDING (29-08-2026, info@zilverwebsite.nl)
Jaap stelde twee vragen: "moet de computer aan blijven staan bij het verversen?"
en "er is deze maand twee keer afgeschreven". Het concept dat klaarstond zei op
allebei dat Daniel het zou nakijken. De eerste vraag is gewoon in de code na te
zoeken — publiceren, verversen en scannen lopen allemaal via de wachtrij die de
extensie in Chrome leegpoetst. De tweede gaat over geld en hoort bij Daniel.

Dit bestand bewaakt drie dingen:
  1. Bij een feitelijke vraag gaat er ECHT broncode mee als bewijsmateriaal, en
     wel de regels die over zijn vraag gaan — niet de eerste zestig regels van
     een bestand, want dat zijn de invoerregels.
  2. Lukt het antwoord niet met zekerheid, dan komt er GEEN mail met "ik kijk het
     na", maar gaat de vraag naar Daniel.
  3. De schrijfregels schrijven dat vage antwoord niet langer voor.
"""
import sys
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORTEL / "scripts"))
import leadgen_mail as L  # noqa: E402
import mail_analyse as M  # noqa: E402


# ── 1. het bewijsmateriaal ─────────────────────────────────────────────────
def test_de_vraag_van_jaap_levert_nu_broncode_op():
    """Precies zijn zin, en dan moet er code meekomen. Eerder kwam er niets."""
    bewijs = L._grondslag("Moet mijn computer aan blijven staan bij het verversen?")
    assert bewijs, "geen enkele regel code bij een vraag die in de code te vinden is"
    assert "backend/api/jobs.py" in bewijs or "extension/background.js" in bewijs


def test_er_komen_regels_mee_die_over_zijn_vraag_gaan():
    """Niet de kop van het bestand alleen: de plek waar het woord voorkomt."""
    bewijs = L._grondslag("Waarom worden mijn advertenties niet ververst?").lower()
    assert "ververs" in bewijs or "relist" in bewijs


def test_zonder_herkenbaar_onderwerp_gaat_er_niets_mee():
    assert L._grondslag("Hoi, alles goed?") == ""
    assert L._grondslag("") == ""


def test_weggelaten_stukken_worden_gemarkeerd():
    """Twee losse fragmenten mogen niet als één doorlopend stuk code lezen —
    daar valt van alles uit af te leiden wat er niet staat."""
    bewijs = L._grondslag("Waarom is mijn import zo traag en duurt het zo lang?")
    assert "..." in bewijs


def test_elk_onderwerp_in_de_lijst_wijst_naar_een_bestand_dat_bestaat():
    """Een verkeerd pad levert stil geen bewijsmateriaal op, en dan raadt het
    model weer. Dat is precies wat deze lijst moet voorkomen."""
    for woord, bestanden in L.GRONDSLAG_BESTANDEN.items():
        for rel in bestanden:
            assert (WORTEL / rel).is_file(), f"{woord} wijst naar {rel}, dat bestaat niet"


# ── 2. geen vaag antwoord, maar de vraag naar Daniel ───────────────────────
def test_de_ene_regel_wordt_herkend():
    assert L._geen_antwoord("GEEN ANTWOORD: Kan Jaap zijn Vinted-maten koppelen?") \
        == "Kan Jaap zijn Vinted-maten koppelen?"
    # ook als het model er een sterretje of kopje omheen zet
    assert L._geen_antwoord("**GEEN ANTWOORD: Wat kost een extra account?**")


def test_een_gewone_mail_is_geen_signaal():
    assert L._geen_antwoord("Hi Jaap,\n\nJe advertenties staan er weer op.\n") is None


def test_de_vraag_belandt_op_de_lijst_van_daniel(monkeypatch):
    kast: dict = {}
    monkeypatch.setattr(M.L, "_db_lees", lambda naam, standaard: kast.get(naam, standaard))
    monkeypatch.setattr(M.L, "_db_schrijf", lambda naam, inhoud: kast.__setitem__(naam, inhoud) or True)
    assert M.vraag_voor_daniel("jaap@voorbeeld.nl", "Moet zijn computer aan blijven staan?")
    lijst = kast["mail_escalaties"]
    assert len(lijst) == 1
    assert lijst[0]["escalatie"] == "kan_niet_onderbouwen"
    assert lijst[0]["adres"] == "jaap@voorbeeld.nl"
    # Tweede keer dezelfde vraag: niet nog een regel op zijn lijst.
    M.vraag_voor_daniel("jaap@voorbeeld.nl", "Moet zijn computer aan blijven staan?")
    assert len(kast["mail_escalaties"]) == 1


def test_een_lege_vraag_belandt_nergens(monkeypatch):
    monkeypatch.setattr(M, "_bewaar_escalaties", lambda n: pytest.fail("niets doorgeven"))
    assert M.vraag_voor_daniel("x@y.nl", "   ") is False


# ── 3. de schrijfregels ────────────────────────────────────────────────────
def test_de_regels_schrijven_geen_vaag_antwoord_meer_voor():
    """Hier zat het: drie plekken zeiden letterlijk 'schrijf dat je het nakijkt'."""
    assert "schrijf dan dat je het nakijkt" not in L.GRONDSLAG_REGEL
    assert "dat Daniel het nakijkt" not in L._SCHRIJF_REGELS
    assert "dat je het vandaag nakijkt" not in L._KLANT_REGELS


def test_de_regels_leggen_de_ene_uitweg_uit():
    assert L.GEEN_ANTWOORD in L.GRONDSLAG_REGEL


def test_over_geld_beslist_daniel_nog_steeds_zelf():
    """Een dubbele afschrijving is geen technische vraag. Die route blijft."""
    assert "geld" in L._KLANT_REGELS
    assert "geld" in M.ESCALATIE_REDENEN and "geld" in M.SPOED
