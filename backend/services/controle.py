"""
Wanneer is elke marktplaats voor het laatst echt nagekeken (15-11-2026).

WAAROM DIT BESTAAT
Een verkoper ziet nu alleen "je computer is online" of "je extensie meldt zich
niet". Dat zegt niets over WAT er is nagekeken. Een verkoper die een koper wil
antwoorden moet kunnen zien dat de verkoopcontrole van Marktplaats een uur
geleden liep, en dat die van Vinted sinds gisteren stilstaat. Zo weet hij of
een artikel nog te koop kan zijn dat hij net elders verkocht heeft.

WAAR HET STAAT
Net als de instellingen in `platform_credentials`, één rij per verkoper met
platform `_controle`, zodat er geen tabel met de hand aangemaakt hoeft te worden.
Geen platformcode kijkt naar die naam. In extra_data staat per kanaal het
laatste moment waarop een controle echt is afgerond.

WIE DE STEMPEL ZET
Alleen een controle die daadwerkelijk iets heeft gelezen: de verkoopcontrole van
de extensie (Marktplaats, 2dehands) en een afgeronde scan (alle kanalen). Een
controle die niets kon lezen zet geen stempel, anders zegt het scherm "net
nagekeken" terwijl er niets is nagekeken.

CACHE
Het dashboard vraagt dit elke 20 seconden en de server draait op één werker met
een blokkerende databaseclient. Daarom één leesvraag per minuut per verkoper.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from backend.database import get_db

logger = logging.getLogger(__name__)

RIJ = "_controle"

# Alleen kanalen waarvoor een verkoopcontrole bestaat. Een verzonnen naam van
# buiten mag nooit een nieuwe sleutel in de rij zetten.
KANALEN = ("marktplaats", "2dehands", "vinted")

_CACHE_SECONDEN = 60.0
_cache: dict[str, tuple[float, dict]] = {}


def _schoon(rauw) -> dict:
    """Alleen bekende kanalen met een leesbare tijd; de rest verdwijnt."""
    uit: dict[str, str] = {}
    if not isinstance(rauw, dict):
        return uit
    for kanaal in KANALEN:
        waarde = rauw.get(kanaal)
        if not isinstance(waarde, str):
            continue
        try:
            datetime.fromisoformat(waarde.replace("Z", "+00:00"))
        except ValueError:
            continue
        uit[kanaal] = waarde
    return uit


def lees(user_id: str, db=None) -> dict:
    """{kanaal: iso-tijd} voor de kanalen die ooit zijn nagekeken. Een storing
    geeft een lege lijst: dit scherm mag een pagina nooit slopen."""
    vast = _cache.get(user_id)
    if vast and time.monotonic() - vast[0] < _CACHE_SECONDEN:
        return dict(vast[1])
    try:
        rij = ((db or get_db()).table("platform_credentials").select("extra_data")
               .eq("user_id", user_id).eq("platform", RIJ).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("controletijden niet gelezen voor %s: %s", user_id, e)
        return {}
    waarden = _schoon(rij[0].get("extra_data") if rij else None)
    _cache[user_id] = (time.monotonic(), waarden)
    return dict(waarden)


def zet(user_id: str, kanaal: str, db=None, nu: datetime | None = None) -> bool:
    """Leg vast dat dit kanaal nu is nagekeken. False bij een onbekend kanaal of
    een mislukte opslag; de aanroeper hoeft er niets mee."""
    if kanaal not in KANALEN:
        return False
    stempel = (nu or datetime.now(timezone.utc)).isoformat()
    # Eerst de verse stand uit de database, niet uit de cache: twee kanalen kort
    # na elkaar mogen elkaar niet overschrijven.
    _cache.pop(user_id, None)
    waarden = lees(user_id, db)
    waarden[kanaal] = stempel
    try:
        (db or get_db()).table("platform_credentials").upsert(
            {"user_id": user_id, "platform": RIJ, "extra_data": waarden},
            on_conflict="user_id,platform",
        ).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("controletijd niet bewaard voor %s/%s: %s", user_id, kanaal, e)
        _cache.pop(user_id, None)
        return False
    _cache[user_id] = (time.monotonic(), dict(waarden))
    return True
