"""Eén ingang voor elke tekstvraag aan een taalmodel: Gemini eerst, Claude als reserve.

WAAROM (23-09-2026, Daniel)
Het Anthropic-tegoed liep leeg, en daarmee stonden het indelen in rubrieken, de
tweelingzoeker tussen talen, de Shopify-collecties, de eBay-rubrieknamen en de
blog stil. Alleen het vertalen had al een vangnet (Gemini). Daniel: "zet alles op
Gemini". Gemini draait op zijn Google-sleutel; Claude blijft erachter staan voor
als Google plat ligt en er toevallig wél tegoed is.

HOE
`vraag()` probeert Gemini (met de modelkeuze en uitwijkregels uit
gemini_vertaling.py), en pas als dat niets oplevert Claude. Lukt geen van beide,
dan gooit hij TaalmodelOnbeschikbaar, zodat elke aanroeper zijn eigen terugval
houdt (woordenlijst, geen suggestie, advertentie laten wachten). Een afgekapt
antwoord telt nooit als antwoord.
"""
from __future__ import annotations

import asyncio
import collections
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

# Wie elke vraag beantwoordde sinds de laatste herstart (op /health): zo is van
# buitenaf te zien hoeveel werk er naar het betaalde Claude gaat.
TELLER: collections.Counter = collections.Counter()

HAIKU = "claude-haiku-4-5-20251001"


class TaalmodelOnbeschikbaar(Exception):
    """Gemini en Claude gaven allebei geen bruikbaar antwoord."""


def vraag(opdracht: str, *, max_tokens: int = 1024, claude_model: str = HAIKU,
          tijdslimiet: float = 30.0, wat: str = "taalvraag", denken: bool = True) -> str:
    """Het antwoord als tekst. Gooit TaalmodelOnbeschikbaar als niets lukte."""
    from backend.services import gemini_vertaling

    if gemini_vertaling.beschikbaar():
        antwoord = gemini_vertaling.vraag(opdracht, max_tokens=max_tokens,
                                          tijdslimiet=tijdslimiet, denken=denken)
        if antwoord:
            TELLER["gemini"] += 1
            return antwoord
        logger.warning("%s: Gemini gaf niets bruikbaars, Claude als reserve", wat)

    reden: Exception | str = "geen Google-sleutel en geen Anthropic-sleutel"
    if settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                         timeout=tijdslimiet)
            bericht = client.messages.create(
                model=claude_model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": opdracht}])
            if getattr(bericht, "stop_reason", None) == "max_tokens":
                raise TaalmodelOnbeschikbaar(f"{wat}: Claude-antwoord afgekapt")
            tekst = "".join(getattr(b, "text", "") or ""
                            for b in (bericht.content or [])).strip()
            if tekst:
                TELLER["claude"] += 1
                return tekst
            reden = "leeg Claude-antwoord"
        except TaalmodelOnbeschikbaar:
            TELLER["geen_antwoord"] += 1
            raise
        except Exception as e:  # noqa: BLE001
            reden = e
    TELLER["geen_antwoord"] += 1
    raise TaalmodelOnbeschikbaar(f"{wat}: geen model beschikbaar ({reden})")


async def vraag_async(opdracht: str, **kw) -> str:
    """Zelfde vraag, in een werkdraad: beide clients zijn synchroon."""
    return await asyncio.to_thread(vraag, opdracht, **kw)
