"""Vangnet voor het vertalen: Gemini springt in als Claude niet kan.

WAAROM DIT ER IS (19-09-2026, op verzoek van Daniel). Zodra het Anthropic-tegoed
op is, gooit `client.messages.create` een `BadRequestError` met "Your credit
balance is too low" — gemeten op 19-09-2026, precies die fout. `_vertaal` in
backend/services/crosslist.py vangt dat op en gooit `VertalingOnbeschikbaar`, en
dan gaat er terecht niets de deur uit: een Engelse tekst op Marktplaats is erger
dan een advertentie die wacht. Maar het gevolg is wel dat publiceren volledig
stilstaat tot iemand de rekening bijvult.

Met dit vangnet stelt Gemini dezelfde vraag als Claude kreeg. Het antwoord gaat
daarna door precies dezelfde controles (§BR§-tekens terug, niet buitensporig
lang, niet in de verkeerde taal). Lukt het niet, dan gebeurt er exact wat er
zonder dit bestand ook gebeurde: de advertentie wacht.

WAT HET NIET DOET. Zolang Claude gewoon antwoordt wordt hier niets aangeroepen.
Dit is een vangnet, geen tweede mening, en ook geen bezuiniging.

DE MODELLENLIJST VAN GOOGLE LIEGT (gemeten 19-09-2026 met de echte sleutel).
De eerste opzet vroeg Google netjes welke modellen er waren en koos daaruit.
`GET /v1beta/models` gaf `gemini-2.5-flash-lite` terug, en een vertaalvraag aan
datzelfde model antwoordde met 404: "This model is no longer available to new
users. Please update your code to use models/gemini-3.5-flash-lite." Hetzelfde
gold voor gemini-2.5-flash en gemini-2.5-pro. De lijst bevat dus namen die de
dienst zelf weigert, en een vangnet dat op die lijst vertrouwt ligt plat op het
moment dat je het nodig hebt.

Daarom telt hier alleen wat er werkelijk uit komt: we proberen de kandidaten op
volgorde tot er één echt antwoordt, onthouden welke dat was, en als een 404 zelf
een opvolger noemt gaat die meteen vooraan in de rij. Gemeten werkt op Daniels
sleutel: gemini-flash-lite-latest, gemini-3.5-flash-lite, gemini-3.1-flash-lite,
gemini-flash-latest, gemini-3.6-flash en gemini-3.8-flash. De pro-modellen geven
429 op de gratis laag, wat nog een reden is om ze niet te proberen.
"""
from __future__ import annotations

import logging
import re

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_BASIS = "https://generativelanguage.googleapis.com/v1beta"
_TIJDSLIMIET = 30.0

# Modellen die geen gewone tekstvertaling horen te doen: beeld, geluid,
# embeddings, onderzoek, en alles wat als proef of voorproefje is gemarkeerd
# (die verdwijnen zonder aankondiging). Pro valt af omdat het duurder is en op
# de gratis laag alleen maar 429 geeft.
_NIET_BRUIKBAAR = ("image", "vision", "tts", "audio", "live", "embedding",
                   "preview", "-exp", "experimental", "thinking", "learnlm",
                   "gemma", "robotics", "computer-use", "lyria", "nano-banana",
                   "transcribe", "omni", "antigravity", "deep-research", "pro")

# De alias die Google zelf bijhoudt. Die blijft goed als er een nieuwe reeks
# uitkomt, dus hij staat vooraan; de rest is de terugval als de alias verdwijnt.
_ALIAS_LITE = "gemini-flash-lite-latest"
_ALIAS_FLASH = "gemini-flash-latest"
_MAX_KANDIDATEN = 4

_GEKOZEN: str | None = None


def beschikbaar() -> bool:
    """Is er een Google-sleutel? Zo niet, dan bestaat het vangnet niet."""
    return bool(settings.google_api_key)


def _versie(naam: str) -> float:
    gevonden = re.search(r"gemini-(\d+(?:\.\d+)?)", naam)
    return float(gevonden.group(1)) if gevonden else 0.0


def _van_google() -> list[str]:
    """Namen die Google noemt. Leeg bij storing; dan doen de aliassen het werk."""
    try:
        antwoord = httpx.get(f"{_BASIS}/models",
                             params={"key": settings.google_api_key},
                             timeout=_TIJDSLIMIET)
        antwoord.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning("Vertaalvangnet: modellenlijst ophalen mislukte (%s)", e)
        return []
    namen = []
    for model in antwoord.json().get("models", []):
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        naam = (model.get("name") or "").replace("models/", "")
        if naam and not any(woord in naam for woord in _NIET_BRUIKBAAR):
            namen.append(naam)
    return namen


def _kandidaten() -> list[str]:
    """Wie we achter elkaar proberen: goedkoopst en meest houdbaar eerst."""
    namen = _van_google()
    lite = sorted((n for n in namen if "flash-lite" in n and n != _ALIAS_LITE),
                  key=_versie, reverse=True)
    flash = sorted((n for n in namen if "flash" in n and "lite" not in n
                    and n != _ALIAS_FLASH), key=_versie, reverse=True)
    rij = [_ALIAS_LITE] + lite + [_ALIAS_FLASH] + flash
    uniek = list(dict.fromkeys(rij))
    return uniek[:_MAX_KANDIDATEN]


def _opvolger_uit_de_klacht(tekst: str) -> str | None:
    """Een 404 noemt vaak zelf welk model ervoor in de plaats is gekomen."""
    gevonden = re.search(r"use\s+models/([A-Za-z0-9._-]+)", tekst or "")
    return gevonden.group(1) if gevonden else None


def _vraag(model: str, opdracht: str) -> httpx.Response:
    return httpx.post(
        f"{_BASIS}/models/{model}:generateContent",
        params={"key": settings.google_api_key},
        json={
            "contents": [{"parts": [{"text": opdracht}]}],
            # Temperatuur 0: een vertaling hoeft niet creatief te zijn.
            "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
        },
        timeout=_TIJDSLIMIET,
    )


def _lees_antwoord(antwoord: httpx.Response) -> str | None:
    kandidaten = antwoord.json().get("candidates") or []
    if not kandidaten:
        logger.warning("Vertaalvangnet: Gemini gaf geen antwoord terug")
        return None
    eerste = kandidaten[0]
    # EEN AFGEKAPT ANTWOORD IS GEEN VERTALING.
    #
    # Loopt het model tegen maxOutputTokens aan, dan komt er een halve
    # omschrijving terug die er verder gaaf uitziet. De controles in `_vertaal`
    # merken dat niet: die kijken naar te lang, niet naar te kort.
    reden = eerste.get("finishReason")
    if reden not in (None, "STOP"):
        logger.warning("Vertaalvangnet: Gemini stopte met %s, antwoord verworpen", reden)
        return None
    delen = (eerste.get("content") or {}).get("parts") or []
    tekst = "".join(d.get("text", "") for d in delen).strip()
    return tekst or None


def vertaal(opdracht: str) -> str | None:
    """Stel dezelfde vertaalopdracht aan Gemini. None betekent: het lukte niet."""
    global _GEKOZEN
    if not beschikbaar():
        return None
    try:
        rij = [_GEKOZEN] if _GEKOZEN else _kandidaten()
        geprobeerd: set[str] = set()
        while rij:
            model = rij.pop(0)
            if model in geprobeerd:
                continue
            geprobeerd.add(model)
            antwoord = _vraag(model, opdracht)

            if antwoord.status_code == 200:
                tekst = _lees_antwoord(antwoord)
                if tekst and _GEKOZEN != model:
                    _GEKOZEN = model
                    logger.info("Vertaalvangnet gebruikt Gemini-model %s", model)
                return tekst

            klacht = antwoord.text[:300]
            if antwoord.status_code in (404, 429):
                # Opgeheven of niet beschikbaar op deze rekening. De volgende
                # kandidaat krijgt hem, en noemt de klacht zelf een opvolger,
                # dan gaat die vooraan.
                logger.warning("Vertaalvangnet: %s doet het niet (HTTP %s), volgende",
                               model, antwoord.status_code)
                if _GEKOZEN == model:
                    _GEKOZEN = None
                    rij = _kandidaten()
                opvolger = _opvolger_uit_de_klacht(klacht)
                if opvolger and opvolger not in geprobeerd:
                    rij.insert(0, opvolger)
                continue

            logger.warning("Vertaalvangnet: Gemini gaf HTTP %s (%s)",
                           antwoord.status_code, klacht)
            return None

        logger.warning("Vertaalvangnet: geen enkel Gemini-model wilde vertalen")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("Vertaalvangnet: Gemini deed het niet (%s: %s)", type(e).__name__, e)
        return None
