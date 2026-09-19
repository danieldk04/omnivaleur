"""Vangnet voor het vertalen: Gemini springt in als Claude niet kan.

WAAROM DIT ER IS (19-09-2026, op verzoek van Daniel). Zodra het Anthropic-tegoed
op is, gooit `client.messages.create` een `BadRequestError` met "Your credit
balance is too low" — gemeten op 19-09-2026, precies die fout. `_vertaal` in
backend/services/crosslist.py vangt dat op en gooit `VertalingOnbeschikbaar`, en
dan gaat er terecht niets de deur uit: een Engelse tekst op Marktplaats is erger
dan een advertentie die wacht. Maar het gevolg is wel dat publiceren volledig
stilstaat tot iemand de rekening bijvult.

Met dit vangnet stelt Gemini dezelfde vraag als Claude kreeg. Het antwoord gaat
daarna door precies dezelfde controles als dat van Claude (§BR§-tekens terug,
niet buitensporig lang, niet in de verkeerde taal). Lukt het niet, dan gebeurt er
exact wat er zonder dit bestand ook gebeurde: de advertentie wacht.

WAT HET NIET DOET. Zolang Claude gewoon antwoordt wordt hier niets aangeroepen.
Dit is een vangnet, geen tweede mening, en ook geen bezuiniging.

HET MODEL WORDT GEVRAAGD, NIET GERADEN. De namen van Gemini-modellen veranderen
regelmatig, en een naam die er niet meer is geeft een 404 die je pas tijdens een
storing ontdekt. Daarom vraagt dit bestand één keer per serverproces aan Google
welke modellen er zijn en kiest daaruit de goedkoopste die tekst kan maken.
"""
from __future__ import annotations

import logging

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_BASIS = "https://generativelanguage.googleapis.com/v1beta"
_TIJDSLIMIET = 30.0

# Modellen die geen gewone tekstvertaling horen te doen: beeld, geluid, embeddings,
# en alles wat als proef of voorproefje is gemarkeerd (die verdwijnen zonder
# aankondiging). Wat overblijft is een gewoon, stabiel tekstmodel.
_NIET_BRUIKBAAR = ("image", "vision", "tts", "audio", "live", "embedding",
                   "preview", "-exp", "experimental", "thinking", "learnlm",
                   "gemma", "robotics", "computer-use")

_GEKOZEN: str | None = None


def beschikbaar() -> bool:
    """Is er een Google-sleutel? Zo niet, dan bestaat het vangnet niet."""
    return bool(settings.google_api_key)


def _kies_model() -> str | None:
    global _GEKOZEN
    if _GEKOZEN:
        return _GEKOZEN
    antwoord = httpx.get(f"{_BASIS}/models",
                         params={"key": settings.google_api_key},
                         timeout=_TIJDSLIMIET)
    antwoord.raise_for_status()
    namen = []
    for model in antwoord.json().get("models", []):
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        naam = (model.get("name") or "").replace("models/", "")
        if not naam or any(woord in naam for woord in _NIET_BRUIKBAAR):
            continue
        namen.append(naam)
    # Flash-Lite is het goedkoopste, daarna Flash. Binnen een soort wint de
    # kortste naam: dat is de stabiele naam, de langere zijn datumversies.
    lite = [n for n in namen if "flash-lite" in n]
    flash = [n for n in namen if "flash" in n]
    kandidaten = sorted(lite or flash or namen, key=lambda n: (len(n), n))
    if not kandidaten:
        logger.warning("Vertaalvangnet: Google gaf geen bruikbaar tekstmodel terug")
        return None
    _GEKOZEN = kandidaten[0]
    logger.info("Vertaalvangnet gebruikt Gemini-model %s", _GEKOZEN)
    return _GEKOZEN


def vertaal(opdracht: str) -> str | None:
    """Stel dezelfde vertaalopdracht aan Gemini. None betekent: het lukte niet."""
    global _GEKOZEN
    if not beschikbaar():
        return None
    try:
        model = _kies_model()
        if not model:
            return None
        antwoord = httpx.post(
            f"{_BASIS}/models/{model}:generateContent",
            params={"key": settings.google_api_key},
            json={
                "contents": [{"parts": [{"text": opdracht}]}],
                # Temperatuur 0: een vertaling hoeft niet creatief te zijn.
                "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
            },
            timeout=_TIJDSLIMIET,
        )
        if antwoord.status_code == 404:
            # Model hernoemd of ingetrokken. Volgende keer opnieuw vragen welke
            # er zijn, anders blijft dit proces de rest van de dag tegen een
            # verdwenen naam praten.
            logger.warning("Vertaalvangnet: Gemini-model %s bestaat niet meer", model)
            _GEKOZEN = None
            return None
        if antwoord.status_code != 200:
            logger.warning("Vertaalvangnet: Gemini gaf HTTP %s (%s)",
                           antwoord.status_code, antwoord.text[:200])
            return None
        kandidaten = antwoord.json().get("candidates") or []
        if not kandidaten:
            logger.warning("Vertaalvangnet: Gemini gaf geen antwoord terug")
            return None
        eerste = kandidaten[0]
        # EEN AFGEKAPT ANTWOORD IS GEEN VERTALING.
        #
        # Loopt het model tegen maxOutputTokens aan, dan komt er een halve
        # omschrijving terug die er verder gaaf uitziet. De controles in
        # `_vertaal` merken dat niet: die kijken naar te lang, niet naar te kort.
        # Alleen een nette afronding telt.
        reden = eerste.get("finishReason")
        if reden not in (None, "STOP"):
            logger.warning("Vertaalvangnet: Gemini stopte met %s, antwoord verworpen", reden)
            return None
        delen = (eerste.get("content") or {}).get("parts") or []
        tekst = "".join(d.get("text", "") for d in delen).strip()
        return tekst or None
    except Exception as e:  # noqa: BLE001
        logger.warning("Vertaalvangnet: Gemini deed het niet (%s: %s)", type(e).__name__, e)
        return None
