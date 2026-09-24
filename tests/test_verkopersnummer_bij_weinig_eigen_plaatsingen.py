"""Verkopersnummer vinden bij een verkoper met maar een paar eigen plaatsingen.

24-09-2026, f8c0cce9: twee advertenties via ons op Marktplaats gezet, 54
geïmporteerd. Alleen die twee titels werden geprobeerd, één vond hem, dus één
stem en geen verkopersnummer. Zijn vijftien 2dehands-zoekertjes wachtten daardoor
op een rubriek die nooit kwam. De geïmporteerde titels moeten meetellen.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services import mp_enrich as M

VERKOPER = 6250337
EIGEN = ["Inkoop en verkoop gitaren", "Eastman Parlor"]
GEIMPORTEERD = ["Bluebird Standard Series - Grey Blue",
                "Magrabo Stripe Sc Entry Olded Black"]
# Wat de zoek-API teruggeeft: "Eastman Parlor" vindt hem niet (andere titel op
# Marktplaats), de rest wel.
AANBOD = [{"itemId": f"m{i}", "title": t, "sellerInformation": {"sellerId": VERKOPER}}
          for i, t in enumerate([EIGEN[0]] + GEIMPORTEERD)]


class NepDb:
    def __init__(self):
        self._tabel = None

    def table(self, naam):
        self._tabel = naam
        return self

    def __getattr__(self, _naam):
        return lambda *a, **k: self

    def execute(self):
        class R: pass
        r = R()
        if self._tabel == "jobs":
            r.data = [{"payload": {"title": t}} for t in EIGEN]
        else:
            r.data = [{"items": {"title": t}} for t in GEIMPORTEERD]
        return r


def test_geimporteerde_titels_vullen_een_handvol_eigen_plaatsingen_aan(monkeypatch):
    async def nep_json(client, url, params=None):
        vraag = M._sleutel((params or {}).get("query") or "")
        return {"listings": [a for a in AANBOD if M._sleutel(a["title"]) == vraag]}

    class NepClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    async def geen_pauze(_s):
        return None

    monkeypatch.setattr(M, "_json", nep_json)
    monkeypatch.setattr(M.asyncio, "sleep", geen_pauze)
    M._VERKOPERNUMMERS.clear()

    async def ronde():
        return await M._verkopersnummer(NepDb(), "f8c0cce9", "marktplaats",
                                        NepClient(), M.ZOEK)

    assert asyncio.run(ronde()) == VERKOPER
