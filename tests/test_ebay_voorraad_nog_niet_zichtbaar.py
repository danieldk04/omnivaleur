"""Toon (96e30080), 05-11-2026: tapijt tl06 stond op "mislukt" met

    eBay error while publishing offer: Input error. Seller Inventory Service can not
    publish the data. Availability not found. Please try again ...

eBay had de voorraad (quantity 1) van het net gezette inventarisitem bij het publiceren
nog niet gezien; een paar minuten later stond hij er wel. Een tweede poging had gewerkt.
Deze proef laat eBay de eerste N publicaties zo weigeren.

Draaien:  python3.13 -m pytest tests/test_ebay_voorraad_nog_niet_zichtbaar.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.platforms import ebay as ebay_mod  # noqa: E402
from test_ebay_staat_per_rubriek import _FakeEbay, _Antwoord, _plaats  # noqa: E402


class _Haperend(_FakeEbay):
    def __init__(self, hoe_vaak):
        super().__init__({"1000", "3000"})
        self.hoe_vaak, self.pogingen = hoe_vaak, 0

    def client(self):
        basis = super().client()
        eb = self
        origineel = basis.post

        async def post(url, json=None, headers=None):
            if url.endswith("/publish"):
                eb.pogingen += 1
                if eb.pogingen <= eb.hoe_vaak:
                    return _Antwoord(400, {"errors": [{
                        "errorId": 25001,
                        "message": "Input error. Seller Inventory Service can not publish "
                                   "the data. Availability not found. Please try again or "
                                   "contact customer support.."}]})
            return await origineel(url, json=json, headers=headers)

        basis.post = post
        return basis


@pytest.fixture(autouse=True)
def _niet_echt_wachten(monkeypatch):
    async def slaap(_):
        return None
    monkeypatch.setattr(ebay_mod.asyncio, "sleep", slaap)


def test_twee_keer_voorraad_niet_gevonden_en_dan_toch_online(monkeypatch):
    eb = _Haperend(2)
    uit = _plaats(monkeypatch, eb, "good")
    assert uit["platform_listing_id"] == "L1"
    assert eb.pogingen == 3


def test_blijft_het_misgaan_dan_komt_de_fout_gewoon_terug(monkeypatch):
    eb = _Haperend(99)
    with pytest.raises(RuntimeError) as fout:
        _plaats(monkeypatch, eb, "good")
    assert "Availability not found" in str(fout.value)
    assert eb.pogingen == 1 + len(ebay_mod._BESCHIKBAARHEID_WACHT)
