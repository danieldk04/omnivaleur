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
    assert "knoppen(document).reverse()" in BG


def test_het_cookiescherm_telt_nooit_als_venster():
    """DE STORING VAN 10-09-2026, account dkresellacademy.

    Het venster "Confirm and delete" stond op het scherm en er werd niet op
    geklikt. Gemeten op de echte pagina van advertentie 9419472843: het
    cookiescherm van OneTrust hangt als 179e blok in de body met role="dialog"
    en aria-modal="true", terwijl React het verwijdervenster er PAS DAARNA
    onderaan bij hangt. "Het eerste venster op de pagina" was dus altijd het
    cookiescherm, en daar staat geen bevestigknop in. Bij wie de cookies al
    heeft weggeklikt staat dat blok er onzichtbaar nog steeds — vandaar dat de
    foutmelding ook geen enkele knop kon opnoemen."""
    for merk in ("onetrust", "didomi", "consent", "cookie"):
        assert merk in BG.lower(), f"{merk}-schermen moeten uitgesloten worden"
    assert "isToestemming" in BG
    for stuk in (
        'const exact = [...document.querySelectorAll(\'[data-testid="item-delete-confirmation-button"]\')]',
        "for (const v of echteVensters())",
    ):
        assert stuk in BG, f"ontbreekt: {stuk}"


def test_er_wordt_niet_op_klokjes_gewacht():
    """Deze routine draait in een tabblad dat de verkoper niet ziet. Chrome rekt
    daar elke setTimeout op tot minstens een seconde (gemeten 10-09-2026: tien
    pauzes van 300 ms kostten 3,0 s zichtbaar en 10,0 s verborgen), en na vijf
    minuten nog maar één per minuut. Vandaar dat de verkoper zag dat er pas iets
    gebeurde zodra hij naar dat tabblad ging. Een MutationObserver wordt niet
    geknepen."""
    start = BG.index("async function _mwVintedVerwijderen()")
    eind = BG.index("\nfunction execInTab(", start)
    # Commentaar telt niet mee: daar mag het woord gewoon in staan.
    code = "\n".join(r for r in BG[start:eind].splitlines()
                     if not r.lstrip().startswith("//"))
    assert "new MutationObserver" in code
    assert code.count("setTimeout") == 1 and "const limiet = setTimeout" in code, \
        "alleen de uiterste grens mag nog een klokje zijn"


def test_het_namaakscherm_bestaat_en_zet_de_oude_code_ernaast():
    tekst = HARNAS.read_text(encoding="utf-8")
    assert "_mwVintedVerwijderen" in tekst
    assert "_oudVintedVerwijderen" in tekst, \
        "zonder de oude code ernaast toont die proef niets aan"
    # De acht schermen die Vinted echt uitserveert.
    for geval in ("vinted.nl", "vinted.fr", "vinted.de", "vinted.com",
                  "zonder role=dialog", "achter het menu", "haar geval",
                  "cookiescherm weggeklikt", "cookiebanner nog zichtbaar"):
        assert geval in tekst
    assert "_vorigVintedVerwijderen" in tekst, \
        "zonder de versie van gisteren ernaast bewijst de proef niet dat er iets gerepareerd is"


def test_de_routine_staat_los_zodat_de_proef_de_echte_code_draait():
    """De harnas snijdt deze functie uit background.js (zie vinted-mock/build.js).
    Staat hij weer als anonieme functie binnen bgDeleteVinted, dan test die
    pagina stilletjes niets meer."""
    assert "async function _mwVintedVerwijderen()" in BG
    assert "execInTab(tabId, _mwVintedVerwijderen)" in BG
    build = (ROOT / "tests/vinted-mock/build.js").read_text(encoding="utf-8")
    assert "_mwVintedVerwijderen" in build


def test_de_geinjecteerde_routine_staat_helemaal_op_zichzelf():
    """DE FOUT VAN 30-08-2026, 15:27 — door mij gemaakt en meteen zichtbaar.

    Chrome injecteert alléén deze ene functie in de pagina; de rest van
    background.js bestaat daar niet. Ik had de hulpfunctie voor het schermbeeld
    ernaast gezet, en dus gooide de pagina bij élke poging meteen een
    ReferenceError. Gevolg: iedereen kreeg "Delete control not found", ongeacht
    wat er op het scherm stond — de verversing was daarmee volledig stuk.

    Het namaakscherm ving dit niet, want daar stonden beide functies wél op de
    pagina. Deze test kijkt naar de enige vraag die telt: roept de geïnjecteerde
    functie iets aan dat straks niet bestaat?
    """
    import re

    start = BG.index("async function _mwVintedVerwijderen()")
    i, diepte, eind = BG.index("{", start), 0, -1
    while i < len(BG):
        if BG[i] == "{":
            diepte += 1
        elif BG[i] == "}":
            diepte -= 1
            if diepte == 0:
                eind = i + 1
                break
        i += 1
    lichaam = BG[start:eind]

    # Alles wat in background.js op het hoogste niveau als functie bestaat.
    buiten = set(re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)\s*\(", BG, re.M))
    buiten.discard("_mwVintedVerwijderen")
    gebruikt = sorted(n for n in buiten if re.search(rf"\b{re.escape(n)}\s*\(", lichaam))
    assert not gebruikt, (
        f"deze functie draait in de PAGINA en kan {gebruikt} daar niet aanroepen — "
        f"zet ze erbinnen neer")


def test_er_wordt_gewacht_tot_de_pagina_is_opgebouwd():
    """Vinted bouwt de pagina met JavaScript op. Te vroeg kijken betekent geen
    enkele knop, en dat heet dan ten onrechte "Delete control not found"."""
    assert "knoppen(document).some(e => zichtbaar(e) && !isToestemming(e))" in BG
