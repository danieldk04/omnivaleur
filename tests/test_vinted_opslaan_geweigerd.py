"""Een geweigerde opslag op Vinted moet zeggen WAT er miste.

WAT ER GEBEURDE (31-08-2026, gemeld door Daniel)
Hij liet Stale stock de prijs van een Ralph Lauren-trui verlagen naar 27,99. De
extensie zette die prijs netjes in het veld en het leek daarna te stoppen: "hij
drukt niet op opslaan". Toen Daniel zelf op Save drukte, kleurde het maatveld
rood met "Fill in size to continue".

Wat er echt gebeurde: er WERD op Save gedrukt. Vinted keurt bij het opslaan de
hele advertentie, niet alleen het veld dat wij veranderden, en weigerde omdat de
maat leeg stond. Het formulier bleef daardoor staan. De controle daarna zocht
alleen naar klachten over de PRIJS, vond niets, en eindigde na zeven seconden met
"clicked Save but the edit form never closed — the update could not be verified".
Die zin noemt het maatveld niet, en dus las het van buitenaf als een knop die
nooit werd ingedrukt.

Twee dingen zijn daarom veranderd:
1. Vóór het opslaan wordt een leeg maatveld alsnog gevuld vanuit het dashboard.
2. Wordt de opslag tóch geweigerd, dan staat Vinted's eigen rode regel in de
   foutmelding, plus welk verplicht veld leeg bleef.

De foutlezers zelf draaien echt in tests/vinted-mock/opslaan-geweigerd-test.js.
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VINTED = (ROOT / "extension/content/vinted.js").read_text(encoding="utf-8")
HARNAS = ROOT / "tests/vinted-mock/opslaan-geweigerd-test.js"


def test_de_foutlezers_doen_wat_ze_beloven():
    """Draait de echte functies uit vinted.js tegen een namaakscherm."""
    uit = subprocess.run(["node", str(HARNAS)], capture_output=True, text=True)
    assert uit.returncode == 0, uit.stdout + uit.stderr


def test_lege_velden_worden_aangevuld_voordat_er_wordt_opgeslagen():
    """De volgorde is de hele reparatie: eerst aanvullen, dan pas klikken.
    Andersom vult het formulier zich na de weigering en gebeurt er niets meer."""
    aanvullen = VINTED.index("await topUpRequiredFieldsVinted(item);")
    klikken = VINTED.index("saveBtn.click();")
    assert aanvullen < klikken, "de aanvulronde staat na de opslaanklik en doet dan niets meer"


def test_de_maat_wordt_uit_het_dashboarditem_gehaald():
    blok = VINTED[VINTED.index("async function topUpRequiredFieldsVinted"):]
    blok = blok[:blok.index("function formErrorsVinted")]
    assert 'fillAttributeVinted(["size"], String(item.size))' in blok
    assert "sizeIsFilledVinted()" in blok, "zonder nameten weten we niet of de maat er echt in staat"


def test_alleen_lege_velden_worden_aangeraakt():
    """Een prijsverlaging mag nooit stilletjes iets anders overschrijven dat de
    verkoper zelf op Vinted had staan."""
    blok = VINTED[VINTED.index("async function topUpRequiredFieldsVinted"):]
    blok = blok[:blok.index("function formErrorsVinted")]
    assert "!sizeIsFilledVinted() && String(item.size" in blok


def test_de_controle_zoekt_niet_meer_alleen_naar_prijsklachten():
    """Dit was de kern: de weigering stond op het scherm, maar de lus keek er
    langs omdat er geen prijswoord in stond."""
    lus = VINTED[VINTED.index("saveBtn.click();"):]
    lus = lus[:lus.index("async function topUpRequiredFieldsVinted")]
    assert "formErrorsVinted()" in lus
    assert "price must|greater than|at least" not in lus, \
        "de oude prijs-only filter staat er nog; dan blijft een maatklacht onzichtbaar"


def test_zonder_zichtbare_melding_wordt_het_lege_veld_alsnog_genoemd():
    lus = VINTED[VINTED.index("saveBtn.click();"):]
    lus = lus[:lus.index("async function topUpRequiredFieldsVinted")]
    assert "emptyRequiredFieldsVinted()" in lus
    assert "Still empty on the Vinted form" in lus


@pytest.mark.parametrize("naam", ["formErrorsVinted", "emptyRequiredFieldsVinted", "saveHintVinted"])
def test_de_hulpfuncties_bestaan_nog(naam):
    """De proef in vinted-mock snijdt op deze namen; hernoemen zonder daar te
    kijken laat de proef stil niets meer testen."""
    assert f"function {naam}(" in VINTED


def test_de_meldingsherkenner_staat_voor_de_eerste_await():
    """Een const bestaat pas als de uitvoering die regel bereikt. Stond hij
    onderaan, dan viel de controle om met 'Cannot access before initialization'
    — precies wat eerder met PRICE_ERR_RE gebeurde."""
    assert VINTED.index("const FORM_ERR_RE") < VINTED.index("const job = await getJob();")
