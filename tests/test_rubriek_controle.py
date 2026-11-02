"""De rubriekcontrole: staat een geplaatste advertentie in de rubriek die we bedoelden?

Waarom (02-11-2026, Esther): op Marktplaats is de rubriek na het plaatsen niet meer te
wijzigen. Draaien: python3.13 -m pytest tests/test_rubriek_controle.py
Voor-en-na: de oude code had geen controle; zonder de module faalt de import hieronder.
"""
import asyncio
import httpx
import pytest

from backend.services import rubriek_controle as rc

PAGINA = ('<html>..."l1CategoryId":621,"l1CategoryName":"Kleding | Dames",'
          '"l2CategoryId":631,"l2CategoryName":"Jurken"...</html>')


def _client(zoek_antwoord, pagina=PAGINA, status=200):
    def handler(request: httpx.Request):
        if "lrp/api/search" in str(request.url):
            return httpx.Response(status, json=zoek_antwoord)
        return httpx.Response(200, text=pagina)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_beoordeel_gelijk_is_ok():
    assert rc.beoordeel({"l1": 621, "l2": 631}, {"l1": 621, "l2": 631}) == "ok"


def test_beoordeel_andere_rubriek_is_afwijkend():
    assert rc.beoordeel({"l1": 621, "l2": 636}, {"l1": 621, "l2": 631}) == "afwijkend"


def test_beoordeel_andere_hoofdrubriek_met_zelfde_rubriek_is_ok():
    # Gemeten in het ingelogde formulier: /plaats/621/626 (handtassen) landt bij hoofdrubriek 1826,
    # /plaats/784/982 (duiken) bij 976. Het rubrieknummer zelf is uniek en beslist.
    assert rc.beoordeel({"l1": 621, "l2": 626}, {"l1": 1826, "l2": 626}) == "ok"
    assert rc.beoordeel({"l1": 784, "l2": 982}, {"l1": 976, "l2": 982}) == "ok"


def test_beoordeel_diepere_rubriek_telt_als_dezelfde():
    # Steps: het adres noemt het blad (465), de advertentie meldt tweede niveau 445.
    assert rc.beoordeel({"l1": 565, "l2": 465}, {"l1": 565, "l2": 445, "blad": 465}) == "ok"
    assert rc.beoordeel({"l1": 565, "l2": 466}, {"l1": 565, "l2": 445, "blad": 465}) == "afwijkend"


def test_beoordeel_zonder_meting_zegt_nooit_afwijkend():
    assert rc.beoordeel({"l1": 621, "l2": 631}, None) == "onbekend"
    assert rc.beoordeel(None, {"l1": 621, "l2": 631}) == "onbekend"
    assert rc.beoordeel({"l1": 621, "l2": 631}, {"l1": None, "l2": None}) == "onbekend"


def test_verwachte_rubriek_extensie_gaat_voor_opdracht():
    res = {"rubriek": {"l1": 621, "l2": 631}}
    assert rc.verwachte_rubriek(res, {"mp_category": {"l1": 1, "l2": 2}}) == {"l1": 621, "l2": 631}
    assert rc.verwachte_rubriek({}, {"mp_category": {"l1": "621", "l2": "631"}}) == {"l1": 621, "l2": 631}
    assert rc.verwachte_rubriek({}, {}) is None
    assert rc.verwachte_rubriek({"rubriek": None}, None) is None


def test_echte_rubriek_leest_de_advertentiepagina():
    zoek = {"listings": [{"itemId": "m111111111", "categoryId": 631, "vipUrl": "/v/x/y/m111111111-t"}]}

    async def run():
        async with _client(zoek) as c:
            return await rc.echte_rubriek(c, "marktplaats", "m111111111")
    echt = asyncio.run(run())
    assert (echt["l1"], echt["l2"], echt["blad"]) == (621, 631, 631)
    assert echt["l2_naam"] == "Jurken"


def test_echte_rubriek_andere_advertentie_in_resultaat_telt_niet():
    zoek = {"listings": [{"itemId": "m222222222", "categoryId": 631, "vipUrl": "/v/x/y/m222222222-t"}]}

    async def run():
        async with _client(zoek) as c:
            return await rc.echte_rubriek(c, "marktplaats", "m111111111")
    assert asyncio.run(run()) is None


@pytest.mark.parametrize("status,zoek", [(403, {}), (429, {}), (200, {"listings": []})])
def test_weigering_of_leeg_antwoord_is_geen_uitspraak(status, zoek):
    async def run():
        async with _client(zoek, status=status) as c:
            return await rc.echte_rubriek(c, "marktplaats", "m111111111")
    echt = asyncio.run(run())
    assert echt is None
    assert rc.beoordeel({"l1": 621, "l2": 631}, echt) == "onbekend"


def test_onleesbare_pagina_is_onbekend_en_niet_afwijkend():
    zoek = {"listings": [{"itemId": "m111111111", "categoryId": 631, "vipUrl": "/v/x/y/m111111111-t"}]}

    async def run():
        async with _client(zoek, pagina="<html>geen rubriek</html>") as c:
            return await rc.echte_rubriek(c, "marktplaats", "m111111111")
    assert asyncio.run(run()) is None
