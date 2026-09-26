"""De zoek-API van Marktplaats en 2dehands filtert alleen op subrubriek met
`l2CategoryIds` (meervoud).

AANLEIDING, 26-09-2026. Met `l2CategoryId` (enkelvoud) negeert de API het filter
stil: "Badmode", "Blouses" en "Bodywarmers" gaven alle drie dezelfde 782.574
advertenties van heel Kleding Dames terug. Elke sweep zag daardoor alleen de
nieuwste 5.000 advertenties per hoofdrubriek, en de rubrieken leken "uitgeput".
Live gemeten: `l2CategoryIds=631` geeft 98.413 advertenties, allemaal Jurken.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts import leadgen_marktplaats as mp  # noqa: E402


class NepClient:
    def __init__(self):
        self.params = None

    def get(self, url, params=None):
        self.params = params

        class R:
            status_code = 200

            @staticmethod
            def json():
                return {"listings": []}
        return R()


def test_subrubriek_gaat_als_meervoud_mee():
    c = NepClient()
    mp._search(c, 621, 631, 0)
    assert c.params.get("l2CategoryIds") == 631
    assert "l2CategoryId" not in c.params


def test_zonder_subrubriek_geen_filter():
    c = NepClient()
    mp._search(c, 621, None, 0)
    assert "l2CategoryIds" not in c.params and "l2CategoryId" not in c.params
