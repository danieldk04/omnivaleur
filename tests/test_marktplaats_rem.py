"""De rem op Marktplaats/2dehands-verzoeken (backend/services/marktplaats_rem.py).

Egbert, 14-10-2026: achtergrondklussen vroegen ruim één pagina per seconde op en
vroegen na een 403 gewoon door; Marktplaats sloot ons serveradres dan een kwartier
af en zijn 2dehands-wachtrij stond stil. Hier: achtergrond krijgt een tempo en
zwijgt na een weigering, een klantverzoek wacht nooit.
"""
import asyncio
import threading
import time

import httpx
import pytest

from backend.services import marktplaats_rem as rem


@pytest.fixture(autouse=True)
def schone_rem(monkeypatch):
    monkeypatch.setattr(rem, "ACHTERGROND_TUSSENPOOS", 0.2)
    monkeypatch.setattr(rem, "TUSSENPOOS_NAAST_KLANT", 0.5)
    rem._staat.update({"dicht_tot": 0.0, "volgende": 0.0, "klant": float("-inf"), "gemeld": 0.0})
    yield
    rem._staat.update({"dicht_tot": 0.0, "volgende": 0.0, "klant": float("-inf"), "gemeld": 0.0})


def _nep_marktplaats(status=200):
    verzoeken = []

    def antwoord(request):
        verzoeken.append(time.monotonic())
        code = status(len(verzoeken)) if callable(status) else status
        return httpx.Response(code, json={"listings": []})
    return httpx.MockTransport(antwoord), verzoeken


def _in_achtergrond(coro_fn):
    """Zoals de planner het doet: eigen thread, eigen lus, gemarkeerd."""
    uit = {}

    def werk():
        rem.markeer_achtergrond()
        uit["r"] = asyncio.run(coro_fn())
    t = threading.Thread(target=werk)
    t.start()
    t.join(30)
    return uit.get("r")


def test_achtergrond_krijgt_een_tempo():
    transport, verzoeken = _nep_marktplaats()

    async def ronde():
        async with httpx.AsyncClient(transport=transport) as c:
            for _ in range(5):
                await c.get("https://www.marktplaats.nl/lrp/api/search")
    _in_achtergrond(ronde)
    assert len(verzoeken) == 5
    assert verzoeken[-1] - verzoeken[0] >= 4 * 0.2 - 0.05


def test_na_een_403_vraagt_de_achtergrond_niets_meer():
    transport, verzoeken = _nep_marktplaats(status=lambda n: 403)

    async def ronde():
        fouten = 0
        async with httpx.AsyncClient(transport=transport) as c:
            for _ in range(25):            # zoals _verkopersnummer: 25 titels
                try:
                    r = await c.get("https://www.2dehands.be/lrp/api/search")
                    r.raise_for_status()
                except Exception:          # noqa: BLE001 — zo vangen de rondes het op
                    fouten += 1
        return fouten
    assert _in_achtergrond(ronde) == 25
    assert len(verzoeken) == 1             # oud: alle 25 gingen de deur uit
    assert rem.dicht()


def test_klantverzoek_wacht_nooit_en_gaat_ook_als_het_dicht_is():
    transport, verzoeken = _nep_marktplaats()
    rem._staat["dicht_tot"] = time.monotonic() + 60
    rem._staat["volgende"] = time.monotonic() + 60     # achtergrond heeft een lange rij

    async def klant():
        async with httpx.AsyncClient(transport=transport) as c:
            begin = time.monotonic()
            r = await c.get("https://www.marktplaats.nl/lrp/api/search")
            return r.status_code, time.monotonic() - begin
    code, duur = asyncio.run(klant())
    assert code == 200 and duur < 0.1 and len(verzoeken) == 1


def test_naast_een_klant_nog_rustiger():
    transport, verzoeken = _nep_marktplaats()

    async def klant():
        async with httpx.AsyncClient(transport=transport) as c:
            await c.get("https://www.marktplaats.nl/lrp/api/search")
    asyncio.run(klant())

    async def ronde():
        async with httpx.AsyncClient(transport=transport) as c:
            for _ in range(3):
                await c.get("https://www.marktplaats.nl/lrp/api/search")
    _in_achtergrond(ronde)
    assert verzoeken[-1] - verzoeken[1] >= 2 * 0.5 - 0.05


def test_andere_sites_vallen_er_buiten():
    transport, verzoeken = _nep_marktplaats(status=403)

    async def ronde():
        async with httpx.AsyncClient(transport=transport) as c:
            for _ in range(3):
                await c.get("https://example.com/")
    _in_achtergrond(ronde)
    assert len(verzoeken) == 3 and not rem.dicht()


def test_planner_markeert_zijn_klussen_als_achtergrond():
    from backend.scheduler import _off_the_request_loop
    gezien = {}

    async def klus():
        gezien["achtergrond"] = rem.is_achtergrond()

    asyncio.run(_off_the_request_loop(klus)())
    assert gezien["achtergrond"] is True
    assert rem.is_achtergrond() is False   # de webserver zelf blijft klant
