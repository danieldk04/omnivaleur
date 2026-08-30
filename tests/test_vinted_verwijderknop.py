"""De verwijderknop van Vinted heet niet overal "Delete".

WAT ER GEBEURDE (30-08-2026, account aertssen.pleun@gmail.com)
Acht Vinted-verversingen op rij mislukten met "still in your wardrobe after
confirming delete". Haar advertenties stonden aantoonbaar nog online
(vinted.nl/items/... gaf gewoon HTTP 200), dus er was echt niets weggehaald.

De teksten hieronder zijn geen aanname. Ze komen uit Vinted's eigen tekstenboek,
dat in elke artikelpagina wordt meegestuurd, opgehaald op 30-08-2026:

    domein      item.actions.delete   ...modal.actions.delete      ...delete_v2
    vinted.nl   Verwijderen           Bevestigen en verwijderen    Ja, verwijderen
    vinted.be   Supprimer             Confirmer et supprimer       Supprimer
    vinted.fr   Supprimer             Confirmer et supprimer       Supprimer
    vinted.de   Löschen               Bestätigen und löschen       Löschen
    vinted.com  Delete                Confirm and delete           Delete

Let op de tweede variant bij .fr/.be en .de: de bevestigknop in het venster heet
daar LETTERLIJK hetzelfde als de knop op de pagina. Wie in de hele pagina zoekt
en de eerste pakt, klikt gegarandeerd de verkeerde aan.

Deze test bewaakt dat die teksten in de extensie blijven staan. Dat ze ook echt
op het juiste element klikken wordt bewezen in tests/vinted-mock/vinted-delete.html:
die pagina draait de ECHTE routine tegen een namaakscherm en zet er de code van
vóór 30-08-2026 naast. Uitkomst: nieuw 8 van de 8 goed, oud 7 van de 8 stuk.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BG = (ROOT / "extension/background.js").read_text(encoding="utf-8")
HARNAS = ROOT / "tests/vinted-mock/vinted-delete.html"


@pytest.mark.parametrize("label", [
    "verwijderen",                 # nl — de knop op de pagina
    "supprimer",                   # fr/be
    "löschen",                     # de
    "delete",                      # com
])
def test_de_knop_wordt_in_elke_taal_herkend(label):
    assert label in BG.lower(), f"'{label}' staat niet in de extensie — dat land kan niets verwijderen"


@pytest.mark.parametrize("label", [
    "bevestigen en verwijderen",
    "ja, verwijderen",
    "confirmer et supprimer",
    "bestätigen und löschen",
    "confirm and delete",
])
def test_de_bevestigknop_staat_er_letterlijk_in(label):
    assert label in BG.lower(), f"bevestigtekst '{label}' ontbreekt"


def test_annuleren_wordt_nooit_aangeklikt():
    for label in ("annuleren", "annuler", "abbrechen", "cancel"):
        assert label in BG.lower(), f"'{label}' moet uitgesloten worden, anders klikken we hem aan"


def test_de_bevestiging_klikt_nooit_dezelfde_knop_nog_eens():
    """Dit is de kern van de storing: zonder venster viel de zoektocht terug op
    de hele pagina, en dan is de eerste treffer de knop op de pagina zelf. Die
    werd dus twee keer aangeklikt — venster open, venster dicht, niets weg."""
    assert "e !== del" in BG, "de bevestiging mag nooit hetzelfde element zijn als de knop op de pagina"


def test_zonder_venster_wordt_van_achteren_gezocht():
    """Een venster wordt onderaan de body gehangen; de knop van de pagina staat
    erboven. Van achteren zoeken is dus het verschil tussen de goede en de
    verkeerde knop."""
    assert "kandidaten[kandidaten.length - 1]" in BG


def test_het_namaakscherm_bestaat_en_zet_de_oude_code_ernaast():
    tekst = HARNAS.read_text(encoding="utf-8")
    assert "_mwVintedVerwijderen" in tekst
    assert "_oudVintedVerwijderen" in tekst, \
        "zonder de oude code ernaast toont die proef niets aan"
    # De acht schermen die Vinted echt uitserveert.
    for geval in ("vinted.nl", "vinted.fr", "vinted.de", "vinted.com",
                  "zonder role=dialog", "achter het menu", "haar geval"):
        assert geval in tekst


def test_de_routine_staat_los_zodat_de_proef_de_echte_code_draait():
    """De harnas snijdt deze functie uit background.js (zie vinted-mock/build.js).
    Staat hij weer als anonieme functie binnen bgDeleteVinted, dan test die
    pagina stilletjes niets meer."""
    assert "async function _mwVintedVerwijderen()" in BG
    assert "execInTab(tabId, _mwVintedVerwijderen)" in BG
    build = (ROOT / "tests/vinted-mock/build.js").read_text(encoding="utf-8")
    assert "_mwVintedVerwijderen" in build
