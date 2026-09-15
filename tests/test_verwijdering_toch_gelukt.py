"""Het vangnet op de server: een mislukte verwijdering waarin het kanaal zelf 404/410 gaf.

15-09-2026. Extensie 1.0.329 boekte een geslaagde verwijdering als mislukking
(zie tests/marktplaats-verlopen-herkennen-test.mjs). De server sloeg de
bijbehorende plaatsing daarop over en 83 advertenties stonden nergens meer.

De extensie is gerepareerd, maar een verkoper werkt pas bij wanneer Chrome dat
doet. Tot dat moment moet de server het zelf kunnen zien: draagt de mislukte
verwijderopdracht het bewijs dat het kanaal zelf 404 of 410 gaf, dan is de
advertentie weg en gaat de plaatsing gewoon door.

Deze test gebruikt een ECHTE foutmelding uit productie, letterlijk overgenomen
uit opdracht van 15-09-2026, plus de tegenproeven die false moeten blijven.

Draaien:  python3 -m pytest tests/test_verwijdering_toch_gelukt.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.jobs import _kanaal_bevestigde_verwijdering as bevestigd


# Letterlijk uit productie (opdracht van 15-09-2026, verkoper Vintage Freaks).
# De diagnostiek staat achter "| Diag: " en wordt gevolgd door " [extensie …]";
# dat achtervoegsel is precies waar een eerdere versie van dit vangnet op stuk
# liep — die zocht de laatste blokhaak, pakte "[extensie 1.0.329]" erbij, en
# herkende daardoor nul van de 83 echte gevallen.
ECHT = (
    'Error: "Blauwe keramische lantaarn met sterren uitsparingen" cannot be found in your '
    'marktplaats listings overview, and the delete button on its own page '
    '(https://www.marktplaats.nl/seller/view/m2426669865) could not be used either. '
    'Nothing was removed — delete it by hand, or check that you are signed in to the right '
    'account. | Buttons on that page: niet gekeken | Diag: '
    '[{"fase":"bevestigen","stap":0,"clicked":true,"gezien":["","Niet verkocht via Marktplaats",'
    '"Verkocht via Marktplaats"],"knop":"Niet verkocht via Marktplaats","open":true},'
    '{"fase":"bevestigen","stap":1,"clicked":false,"gezien":["Meldingen","Vintage Freaks",'
    '"Privacyvoorkeuren"],"open":false},'
    '{"fase":"fetch-check","poging":0,"status":410,"via":"status","weg":true},'
    '{"fase":"dom-tegencontrole","poging":0,"textHit":null,'
    '"url":"https://www.marktplaats.nl/v/huis-en-inrichting/woonaccessoires-overige/'
    'm2426669865-blauwe-keramische-lantaarn-met-sterren-uitsparingen?c=0aae4f96"},'
    '{"fase":"fetch-check","poging":1,"status":410,"via":"status","weg":true},'
    '{"fase":"dom-tegencontrole","poging":1,"textHit":null,'
    '"url":"https://www.marktplaats.nl/v/huis-en-inrichting/woonaccessoires-overige/'
    'm2426669865-blauwe-keramische-lantaarn-met-sterren-uitsparingen?c=0aae4f96"}] '
    '[extensie 1.0.329]'
)


def _klus(fout):
    return {"result": {"error": fout}}


def test_echte_productiefout_wordt_herkend():
    assert bevestigd(_klus(ECHT)) is True


def test_kanaal_zei_200_blijft_een_mislukking():
    # Zelfde opdracht, maar het kanaal gaf de advertentie gewoon terug. Dan staat
    # hij er nog en zou een plaatsing een dubbele maken.
    assert bevestigd(_klus(ECHT.replace('"status":410', '"status":200'))) is False


def test_laatste_poging_telt_niet_de_eerste():
    fout = ('x | Diag: [{"fase":"fetch-check","status":410},'
            '{"fase":"fetch-check","status":200}] [extensie 1.0.329]')
    assert bevestigd(_klus(fout)) is False


def test_advertentienummer_met_410_erin_doet_niets():
    fout = ('x | Diag: [{"fase":"fetch-check","status":200,'
            '"url":"https://www.marktplaats.nl/v/a/m2410999"}] [extensie 1.0.329]')
    assert bevestigd(_klus(fout)) is False


def test_zonder_diagnostiek_geen_conclusie():
    assert bevestigd(_klus('"X" is still online on marktplaats after confirming the delete')) is False
    assert bevestigd({}) is False
    assert bevestigd({"result": None}) is False


def test_onleesbare_diagnostiek_geeft_false():
    assert bevestigd(_klus("x | Diag: [dit is geen json")) is False


def test_de_uitdeellus_raadpleegt_dit_ook_echt_en_op_tijd():
    """Een helper die klopt maar nergens wordt aangeroepen repareert niets.

    Hier gaat het bovendien om de VOLGORDE: het vangnet moet vóór de tak staan
    die de plaatsing overslaat, anders is de plaatsing al afgeschoten voor het
    aan bod komt.
    """
    bron = (Path(__file__).parent.parent / "backend/api/jobs.py").read_text(encoding="utf-8")
    blok = bron[bron.index('if j["action"] == "create" and j.get("scheduled_for"):'):]
    vangnet = blok.index("_kanaal_bevestigde_verwijdering")
    overslaan = blok.index("Skipped — the paired delist failed")
    assert vangnet < overslaan, "het vangnet moet vóór het overslaan van de plaatsing staan"
    # En de opdracht moet zijn resultaat wel meekrijgen: zonder `result` in de
    # select is er geen diagnostiek om naar te kijken en doet het vangnet niets.
    kop = blok[:blok.index("_kanaal_bevestigde_verwijdering")]
    assert '.select("id,status,payload,result")' in kop
