"""De tweelingzoeker mag de server niet stilzetten.

WAAROM DIT ER IS (31-08-2026, Egbert Brouwer)
Egbert stuurde een schermafbeelding: zijn importlijst blijft leeg en het scherm
zegt "Server error (500). Please try again in a moment." Zijn extensie stond op
1.0.273 en de Admarkt-schakelaar aan — daar lag het dus niet aan.

Wat er in de code gebeurde: bij 500 kandidaten maakt `_find_twins` dertien
brokken en vuurt die allemaal tegelijk af. Elke brok doet zijn modelaanroep via
`asyncio.to_thread`, en die draden worden gedeeld met de inlogcontrole die op
élk verzoek draait. Op Railway zijn dat er zes. Dertig seconden lang was er dus
geen draad meer over voor wie dan ook.

Dat is dezelfde valkuil die bovenaan backend/scheduler.py al beschreven staat en
die eerder 502'en opleverde voor iedereen tegelijk. Deze proef legt de rem vast.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api import imports as api  # noqa: E402


def test_er_lopen_er_nooit_meer_dan_de_rem_tegelijk():
    """DE KERN. Zonder rem lopen alle brokken tegelijk en is de draadvoorraad
    van de hele server op."""
    tegelijk = {"nu": 0, "hoogste": 0}

    async def traag(_brok):
        tegelijk["nu"] += 1
        tegelijk["hoogste"] = max(tegelijk["hoogste"], tegelijk["nu"])
        await asyncio.sleep(0.01)
        tegelijk["nu"] -= 1
        return {}

    brokken = [[{"id": f"c{i}"}] for i in range(13)]
    asyncio.run(api._asyncio_gather_safe(brokken, traag))

    assert tegelijk["hoogste"] <= api._TWIN_TEGELIJK, (
        f"er liepen er {tegelijk['hoogste']} tegelijk; hooguit "
        f"{api._TWIN_TEGELIJK} mag de draadvoorraad heel houden")


def test_alle_brokken_worden_alsnog_gedaan():
    """Een rem die werk laat vallen zou erger zijn dan geen rem: dan mist de
    verkoper dubbelherkenning zonder dat iemand het ziet."""
    gedaan = []

    async def een(brok):
        gedaan.append(brok[0]["id"])
        return {brok[0]["id"]: "item"}

    brokken = [[{"id": f"c{i}"}] for i in range(13)]
    uit = asyncio.run(api._asyncio_gather_safe(brokken, een))

    assert len(gedaan) == 13
    assert len(uit) == 13


def test_de_rem_geldt_ook_over_de_platforms_heen():
    """`_find_twins` roept zichzelf aan per platform. Kreeg elk platform zijn
    eigen budget, dan zijn we bij drie platforms alsnog met negen bezig."""
    bron = (ROOT / "backend" / "api" / "imports.py").read_text(encoding="utf-8")
    blok = bron.split("if len(by_platform) > 1:", 1)[1][:600]
    assert "_rem=rem" in blok, "elk platform krijgt weer zijn eigen budget"
    assert "rem = _rem or" in blok


def test_een_doorgegeven_rem_wordt_gebruikt_en_niet_vervangen():
    """Anders is de doorgifte hierboven zinloos."""
    gebruikt = []

    class Rem:
        async def __aenter__(self):
            gebruikt.append(1)

        async def __aexit__(self, *a):
            return False

    async def een(_brok):
        return {}

    asyncio.run(api._asyncio_gather_safe([[{"id": "a"}], [{"id": "b"}]], een, Rem()))
    assert len(gebruikt) == 2
