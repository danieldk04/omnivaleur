"""Het dashboard moet vier statussen uit elkaar houden, niet twee.

WAAROM DIT ER IS (31-08-2026, Daniel: "kopje marketing en werkplaats zijn een
chaos")

Twee dingen liepen door elkaar op dat scherm:

1. De storingentabel deelde in met `status === 'opgelost' ? 'klaar' : 'open'`.
   Een melding die bewust was afgewezen, of die vanzelf was uitgedoofd, las
   daardoor als openstaand werk. Zo kwam Daniel aan een lijst van 46 "open"
   storingen terwijl er negen speelden.
2. "Dit ligt bij jou" toonde de laatste 25 niet-afgehandelde escalaties. In de
   praktijk was dat een muur van 25 regels waarin de urgente van vandaag
   verdween tussen die van twee weken terug. Een lijst die alles toont, toont
   niets.

Het onderscheid dat hier bewaakt wordt is niet cosmetisch: `opgelost` betekent
dat de klant bericht krijgt, `verlopen` betekent uitdrukkelijk dat hij dat NIET
krijgt. Wie die twee op één hoop gooit, stuurt vroeg of laat post over
problemen die niemand zich nog herinnert.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import beheer as B  # noqa: E402

NU = datetime.now(timezone.utc)


def _escalatie(dagen_geleden, soort="geld", adres="info@zilverwebsite.nl"):
    return {"adres": adres, "escalatie": soort, "samenvatting": "iets",
            "wanneer": (NU - timedelta(days=dagen_geleden)).isoformat()}


def test_oude_escalaties_verdwijnen_van_het_scherm():
    """DE KERN van de chaos: 25 regels waarin de urgente niet meer opviel."""
    lijst = [_escalatie(1), _escalatie(30), _escalatie(45), _escalatie(2)]

    uit = B._escalaties_die_er_toe_doen(lijst)

    assert len(uit) == 2, f"oude escalaties staan er nog bij: {uit}"


def test_geld_en_vertrek_staan_bovenaan():
    """Dat zijn de twee die geld kosten als ze blijven liggen."""
    lijst = [_escalatie(1, "kan_niet_onderbouwen"),
             _escalatie(1, "geld"),
             _escalatie(1, "vertrek")]

    soorten = [e["escalatie"] for e in B._escalaties_die_er_toe_doen(lijst)]

    assert soorten[0] == "vertrek"
    assert soorten[1] == "geld"


def test_afgehandelde_escalaties_tellen_niet_mee():
    lijst = [dict(_escalatie(1), afgehandeld=True), _escalatie(1)]

    assert len(B._escalaties_die_er_toe_doen(lijst)) == 1


def test_de_lijst_wordt_nooit_eindeloos_lang():
    """Ook binnen twee weken kunnen er tientallen zijn. Dan is afkappen beter
    dan alles tonen."""
    lijst = [_escalatie(1) for _ in range(40)]

    assert len(B._escalaties_die_er_toe_doen(lijst)) <= 12


def test_uitgedoofd_en_opgelost_zijn_niet_hetzelfde():
    """Het verschil dat ertoe doet: bij `opgelost` krijgt de klant bericht, bij
    `verlopen` uitdrukkelijk niet. Het scherm moet dat kunnen laten zien, en
    daarvoor moeten de velden gescheiden blijven."""
    opgelost = B._storing_rij("a", {
        "status": "opgelost", "uitleg": "de knop werkt weer",
        "gerepareerd_op": "2026-08-31T10:00:00+00:00"}, None)
    verlopen = B._storing_rij("b", {
        "status": "verlopen", "reden": "na 19-08 nog contact zonder dat het terugkwam",
        "verlopen_op": "2026-08-31T10:00:00+00:00"}, None)

    assert opgelost["uitleg"] == "de knop werkt weer"
    assert not opgelost["reden"], "een reparatie heeft geen afwijsreden"
    assert verlopen["reden"].startswith("na 19-08"), (
        "zonder eigen veld is niet te zien waaróm iets is uitgedoofd")
    assert verlopen["klaar_op"], "een uitgedoofde melding hoort een datum te hebben"
