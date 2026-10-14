"""Eén rem op alles wat onze server bij Marktplaats en 2dehands opvraagt.

WAAROM DIT ER IS (14-10-2026, Egbert Brouwer / Papa's Plectrums)

"Het duurt soms erg lang voordat er daadwerkelijk iets gebeurt, ondanks dat er al
een bestaande lijst is." Gemeten in zijn opdrachten van 10 tot 14 oktober: telkens
gaten van 10 tot 12,5 minuut zonder één plaatsing, met honderden zoekertjes
klaar en zijn extensie die elke 15 seconden netjes om werk vroeg. De server gaf
niets mee: elke 2dehands-plaatsing wacht eerst op de echte Marktplaats-rubriek
(zie _zet_rubriek_van_marktplaats in api/jobs.py), en die opzoeking kreeg 403.

Die 403 kwam niet van zijn eigen opzoekingen. Die doen er een paar per halve
minuut en liepen de hele dag goed. Elk gat begon binnen drie minuten na een
achtergrondklus die in één ruk honderden pagina's van álle verkopers opvroeg:
de fotocontrole (tien minuten na elke deploy en daarna elke zes uur) en de
uurlijkse ronde rond :23 (gereserveerd en het aanvullen van teksten). Ruim één
verzoek per seconde, minutenlang, en bij een 403 gingen ze gewoon door (111 en
185 weigeringen binnen een seconde). Marktplaats sluit dan ons hele serveradres
een kwartier af, en daarmee ook de opzoeking waar de wachtrij van elke klant met
2dehands op wacht.

DE REGELS

1. Werk op de achtergrond (alles wat de planner draait, zie scheduler.py) krijgt
   een vast tempo: één verzoek per ACHTERGROND_TUSSENPOOS seconden, over alle
   klussen samen. Loopt er net een klantopzoeking, dan nog rustiger.
2. Na een 403 of 429, van wie dan ook, stuurt de achtergrond DICHT_RUST lang
   niets meer. Wie dan toch vraagt krijgt meteen MarktplaatsDicht, zonder dat er
   een verzoek de deur uit gaat. Elke beller vangt dat al op als "geen uitspraak".
3. Wat een klant nu nodig heeft (de rubriek vlak voor uitgifte, een knop in het
   dashboard) gaat nooit in de rij. Alleen in de KLANT_STIL_NA_403 seconden na een
   weigering gaat ook een klantverzoek niet de deur uit: dat mislukt dan toch, en
   een knop die in die seconden doorvraagt houdt het adres voor iedereen dicht.
   Gemeten 14-10-2026 16:33 UTC: drie keer "Fill from Marktplaats" achter elkaar,
   daarna 22 geweigerde vragen in twee seconden (25 titels voor het verkopersnummer).

Het zit op httpx.AsyncClient.send en httpx.Client.send, dus elke plek die deze
twee sites vraagt valt eronder, ook een die later wordt toegevoegd.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import time

import httpx

logger = logging.getLogger(__name__)

HOSTS = frozenset({"www.marktplaats.nl", "marktplaats.nl", "www.2dehands.be", "2dehands.be"})
# Een klantopzoeking doet er ~8 per minuut en is nog nooit geweigerd; de klussen
# die het adres lieten afsluiten deden er ~75 per minuut.
ACHTERGROND_TUSSENPOOS = 4.0        # 15 per minuut
TUSSENPOOS_NAAST_KLANT = 10.0       # 6 per minuut zolang een klant zelf vraagt
KLANT_ACTIEF = 120.0                # zo lang na een klantverzoek geldt dat
DICHT_RUST = 15 * 60.0              # gemeten: het adres bleef ~12 minuten dicht
KLANT_STIL_NA_403 = 30.0            # korter dan de 3 min rust van de rubriekopzoeking

_achtergrond: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "marktplaats_achtergrond", default=False)
_slot = threading.Lock()
_staat = {"dicht_tot": 0.0, "volgende": 0.0, "klant": float("-inf"), "gemeld": 0.0,
          "geweigerd": float("-inf")}


class MarktplaatsDicht(httpx.RequestError):
    """Achtergrondverzoek niet verstuurd: Marktplaats of 2dehands weigerde ons net."""


def markeer_achtergrond() -> None:
    """Alles wat vanaf hier in deze context draait, telt als achtergrond."""
    _achtergrond.set(True)


def is_achtergrond() -> bool:
    return _achtergrond.get()


def dicht() -> bool:
    return time.monotonic() < _staat["dicht_tot"]


def _reserveer() -> float:
    """Geeft de wachttijd tot onze beurt, of gooit MarktplaatsDicht."""
    with _slot:
        nu = time.monotonic()
        if nu < _staat["dicht_tot"]:
            raise MarktplaatsDicht(
                f"Marktplaats/2dehands weigerde ons; achtergrond wacht nog "
                f"{int(_staat['dicht_tot'] - nu)} s")
        pauze = (TUSSENPOOS_NAAST_KLANT if nu - _staat["klant"] < KLANT_ACTIEF
                 else ACHTERGROND_TUSSENPOOS)
        beurt = max(nu, _staat["volgende"])
        _staat["volgende"] = beurt + pauze
        return beurt - nu


def _na_verzoek(request: httpx.Request, status: int | None) -> None:
    with _slot:
        nu = time.monotonic()
        if not is_achtergrond():
            _staat["klant"] = nu
        if status not in (403, 429):
            return
        _staat["dicht_tot"] = nu + DICHT_RUST
        _staat["geweigerd"] = nu
        melden = nu - _staat["gemeld"] > 60
        if melden:
            _staat["gemeld"] = nu
    if melden:
        logger.warning("marktplaats_rem: HTTP %s van %s (%s); achtergrondverzoeken "
                       "%d minuten stil", status, request.url.host,
                       "achtergrond" if is_achtergrond() else "klant", DICHT_RUST // 60)


def _geldt(request: httpx.Request) -> bool:
    return request.url.host in HOSTS


def _klant_net_geweigerd() -> None:
    if time.monotonic() - _staat["geweigerd"] < KLANT_STIL_NA_403:
        raise MarktplaatsDicht("Marktplaats/2dehands weigerde ons zojuist; even niet vragen")


_ORIGINEEL_ASYNC_SEND = httpx.AsyncClient.send
_ORIGINEEL_SYNC_SEND = httpx.Client.send


async def _async_send(self, request, *args, **kwargs):
    if not _geldt(request):
        return await _ORIGINEEL_ASYNC_SEND(self, request, *args, **kwargs)
    if not is_achtergrond():
        _klant_net_geweigerd()
    else:
        wacht = _reserveer()
        if wacht > 0:
            await asyncio.sleep(wacht)
            if dicht():
                raise MarktplaatsDicht("Marktplaats/2dehands weigerde ons tijdens het wachten")
    antwoord = await _ORIGINEEL_ASYNC_SEND(self, request, *args, **kwargs)
    _na_verzoek(request, antwoord.status_code)
    return antwoord


def _sync_send(self, request, *args, **kwargs):
    if not _geldt(request):
        return _ORIGINEEL_SYNC_SEND(self, request, *args, **kwargs)
    if not is_achtergrond():
        _klant_net_geweigerd()
    else:
        wacht = _reserveer()
        if wacht > 0:
            time.sleep(wacht)
            if dicht():
                raise MarktplaatsDicht("Marktplaats/2dehands weigerde ons tijdens het wachten")
    antwoord = _ORIGINEEL_SYNC_SEND(self, request, *args, **kwargs)
    _na_verzoek(request, antwoord.status_code)
    return antwoord


def installeer() -> None:
    """Eenmalig; daarna doet een tweede aanroep niets."""
    if httpx.AsyncClient.send is not _async_send:
        httpx.AsyncClient.send = _async_send
    if httpx.Client.send is not _sync_send:
        httpx.Client.send = _sync_send


installeer()
