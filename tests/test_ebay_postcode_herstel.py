"""Een klant (45f9caba, 25-10-2026) sloeg zijn postcode op als "2221dc". eBay maakte er
een verzendlocatie van en weigerde daarna elke publicatie met "Voer een geldige
postcode in". De locatie bleef staan, ook als de postcode later goed kwam.

Nu: postcode altijd hoofdletters, en een bestaande locatie die afwijkt wordt bijgewerkt.
"""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.platforms import ebay as E  # noqa: E402


class _Antwoord:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data or {}

    def json(self):
        return self._data


class _Client:
    def __init__(self, bestaand):
        self.bestaand, self.posts = bestaand, []

    async def get(self, url, headers=None):
        if self.bestaand is None:
            return _Antwoord(404)
        return _Antwoord(200, {"location": {"address": {"postalCode": self.bestaand}}})

    async def post(self, url, json=None, headers=None):
        self.posts.append((url, json))
        return _Antwoord(204)


def _rij(postcode):
    return {"access_token": "x", "extra_data": {"ship_from": {"postal_code": postcode, "city": "katwijk", "country": "NL"}}}


def test_postcode_gaat_in_hoofdletters_naar_ebay():
    assert E.EbayPlatform._ship_from_address(_rij(" 2221dc "))["postalCode"] == "2221DC"


def test_bestaande_locatie_met_slechte_postcode_wordt_bijgewerkt():
    c = _Client(bestaand="2221dc")
    asyncio.run(E.EbayPlatform()._ensure_location(c, _rij("2221dc")))
    assert len(c.posts) == 1 and c.posts[0][0].endswith("/update_location_details")
    assert c.posts[0][1]["location"]["address"]["postalCode"] == "2221DC"


def test_goede_locatie_blijft_met_rust():
    c = _Client(bestaand="2221DC")
    asyncio.run(E.EbayPlatform()._ensure_location(c, _rij("2221dc")))
    assert c.posts == []
