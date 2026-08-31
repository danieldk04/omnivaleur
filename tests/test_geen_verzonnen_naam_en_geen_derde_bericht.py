"""Drie mails die niet verstuurd hadden mogen worden, en waarom.

WAAROM DIT ER IS (31-08-2026)
Daniel, na een ochtend waarin ik de mailagent zelf liet versturen: "je hebt
mails gestuurd naar jaap van zilverwebsite met naam ronald en een totaal random
bericht (...) ook teveel mails verstuurd naar frank. pas hier echt mee op."

Drie aparte fouten, met drie aparte oorzaken. Het zelf-versturen is inmiddels
helemaal weggehaald, maar dat lost er maar één van op: de andere twee zitten in
de TEKST, en die schade is precies even groot als Daniel zelf op verzenden
drukt. Vandaar deze proeven.
"""
import importlib.util
import pathlib
import sys

import pytest

WORTEL = pathlib.Path(__file__).resolve().parents[1]
BRON = (WORTEL / "scripts" / "leadgen_mail.py").read_text(encoding="utf-8")
ANALYSE = (WORTEL / "scripts" / "mail_analyse.py").read_text(encoding="utf-8")


def _laad(naam):
    sys.path.insert(0, str(WORTEL / "scripts"))
    spec = importlib.util.spec_from_file_location(naam, WORTEL / "scripts" / f"{naam}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[naam] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def L():
    return _laad("leadgen_mail")


@pytest.fixture()
def M(L):
    return _laad("mail_analyse")


# ── 1. "Hi Ronald" — een naam die niet bestaat ───────────────────────────────

def test_de_instructie_vraagt_niet_meer_om_een_naam():
    """DE OORZAAK, letterlijk. De instructie zei "Hi <naam>," terwijl er nergens
    een naam werd meegegeven — alleen een e-mailadres en de reparatiepunten. Het
    model vulde dat gat toen zelf in, en zo kreeg Zilverwebsite een mail voor
    ene Ronald."""
    regels = ANALYSE.split("HERSTELBERICHT_REGELS = ", 1)[1].split('"""')[1]
    assert "<naam>" not in regels, "de instructie vraagt nog steeds om een naam"
    assert '"Hi,"' in regels


@pytest.mark.parametrize("aanhef, wat", [
    ("Hi Ronald,", "een verzonnen voornaam"),
    ("Hi Zilverwebsite,", "een winkelnaam"),
    ("Hoi Jaap,", "een andere begroeting"),
    ("Hallo Ronald,", "hallo"),
    ("Beste heer De Vries,", "formeel"),
    ("Dag Amanda,", "dag"),
])
def test_elke_naam_gaat_uit_de_aanhef(M, aanhef, wat):
    """Een promptregel is een verzoek, geen garantie. Dit is het slot.

    Een verkeerde voornaam in de eerste regel vertelt de klant dat er een
    machine schrijft die hem niet kent — dat is erger dan helemaal geen naam."""
    uit = M._aanhef_zonder_naam(f"{aanhef}\n\nJe gaf door dat...", "test@x.nl")
    assert uit.startswith("Hi,\n"), f"{wat} bleef staan: {uit.splitlines()[0]!r}"


def test_een_aanhef_zonder_naam_blijft_precies_zoals_hij_is(M):
    tekst = "Hi,\n\nJe gaf door dat je advertenties verschoven."
    assert M._aanhef_zonder_naam(tekst, "test@x.nl") == tekst


def test_een_gewone_zin_die_met_hi_begint_wordt_niet_verminkt(M):
    """"Hi, dit is geen aanhef" mag niet half weggeknipt worden."""
    tekst = "Hi, dit is geen aanhef maar een zin, toch?"
    assert M._aanhef_zonder_naam(tekst, "test@x.nl") == tekst


def test_het_slot_zit_in_de_weg_van_elk_herstelbericht():
    """Niet ergens los aanroepbaar, maar op de enige uitgang."""
    blok = ANALYSE.split("def _herstelbericht(", 1)[1].split("\n# Een aanhef", 1)[0]
    assert "_aanhef_zonder_naam(tekst, adres)" in blok


# ── 2. Frank — een derde bericht op een gesprek dat wij zelf dichtdeden ──────

@pytest.mark.parametrize("tekst, wat", [
    ("Hi Frank,\n\nDuidelijk, jullie hebben het zo ingericht dat het past bij hoe "
     "jullie werken. Mocht dat op enig moment anders liggen, dan hoor ik het wel.",
     "Frank, 20-08 — precies de mail waar een derde bericht op volgde"),
    ("Hi Patricia,\n\nHelder, en bedankt voor je reactie! Dan spreken we elkaar "
     "later. Voor nu, succes met de verkoop en een fijne vakantie toegewenst!",
     "Patricia, 27-08 — Daniel had het gesprek zelf al gesloten"),
    ("Ik laat het hierbij, ik ga je er niet langer mee lastigvallen.", "afscheid"),
    ("Laatste berichtje van mij hierover, ik val je verder niet lastig.", "laatste bericht"),
])
def test_na_een_afsluiting_komt_er_geen_zetje_meer(L, tekst, wat):
    """De stiltemeting kan dit niet zien: er ís stilte, en dat klopt ook — wij
    hebben het gesprek dichtgedaan. Dat is het verschil tussen "ik wacht op je"
    en "ik laat je met rust"."""
    assert L._is_afsluiting(tekst), f"niet herkend als afsluiting: {wat}"


@pytest.mark.parametrize("tekst", [
    "Hi,\n\nIk had je aangeboden dat filmpje te sturen. Zeg maar of je 'm nog wilt hebben.",
    "Hi,\n\nWaar ik benieuwd naar ben: hoeveel tijd zijn jullie per week kwijt aan "
    "het overzetten van jullie spullen?",
    "Hi Twan,\n\nDat filmpje staat nog steeds voor je klaar — een woordje en ik "
    "stuur 'm door. Geen haast hoor.",
])
def test_een_openstaande_vraag_mag_wel_een_zetje_krijgen(L, tekst):
    """De rem mag niet zó ruim worden dat elke opvolging verdwijnt; dan valt
    juist de groep stil die het meest waard is."""
    assert not L._is_afsluiting(tekst)


def test_de_opvolging_kijkt_daar_ook_echt_naar():
    blok = BRON.split("def _warme_opvolging(", 1)[1].split("\ndef ", 1)[0]
    assert "_is_afsluiting(" in blok
    # en zet de teller door, zodat er niet elke ronde opnieuw naar gekeken wordt
    volgt = blok.split("_is_afsluiting(", 1)[1][:220]
    assert 'st["warm_opvolg"] = len(WARM_OPVOLG_DAGEN)' in volgt


def test_een_vakantiemelding_telt_niet_als_gesprek():
    """Het enige wat Frank ooit terugstuurde was zijn afwezigheidsassistent.
    Dat werd gelezen als "hij heeft gereageerd, dus dit gesprek is stilgevallen"
    — terwijl er nooit iemand heeft meegelezen."""
    blok = BRON.split("def _warme_opvolging(", 1)[1].split("\ndef ", 1)[0]
    assert 'st.get("auto_antwoord") and not st.get("beantwoord")' in blok
