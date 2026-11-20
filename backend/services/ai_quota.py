"""Maandplafond per klant voor het AI-pakket (20-11-2026).

Doel: onder de EUR 0,10 per klant per maand blijven, ook als iemand de knop
blijft indrukken. Het verbruik staat in de bestaande instellingenrij
(`instellingen`, sleutel `ai_pakket`), dus een herstart of deploy zet het niet
op nul en er is geen migratie nodig. Een nieuwe maand begint vanzelf leeg.

Bij twijfel NEE: lukt het lezen niet, dan geen AI-vraag.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.services import instellingen

logger = logging.getLogger(__name__)

# Per klant per maand. Een bulkopdracht is een vraag (~500 tokens), een titel of
# beschrijving een vraag per artikel (in blokken van 20 gaat het per blok).
PLAFOND = {"bulk": 30, "titels": 300, "beschrijvingen": 150, "achtergronden": 100}


def maand() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _stand(user_id: str) -> dict:
    raw = instellingen.lees(user_id).get("ai_pakket")
    raw = raw if isinstance(raw, dict) else {}
    if raw.get("maand") != maand():
        raw = {**{k: v for k, v in raw.items() if k == "laatste"}, "maand": maand()}
    return raw


def gebruikt(user_id: str, soort: str) -> int:
    try:
        return int(_stand(user_id).get(soort) or 0)
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_quota: lezen mislukt voor %s: %s", user_id, e)
        return PLAFOND.get(soort, 0)  # bij twijfel: vol


def ruimte(user_id: str, soort: str, n: int = 1) -> bool:
    return gebruikt(user_id, soort) + n <= PLAFOND[soort]


def tel(user_id: str, soort: str, n: int = 1) -> None:
    stand = _stand(user_id)
    stand[soort] = int(stand.get(soort) or 0) + n
    instellingen.schrijf(user_id, {"ai_pakket": stand})


def bewaar(user_id: str, sleutel: str, waarde) -> None:
    """Een los gegeven (voorbeeld, ongedaan-maken) bij de stand zetten."""
    stand = _stand(user_id)
    if waarde is None:
        stand.pop(sleutel, None)
    else:
        stand[sleutel] = waarde
    instellingen.schrijf(user_id, {"ai_pakket": stand})


def lees_los(user_id: str, sleutel: str):
    return _stand(user_id).get(sleutel)
