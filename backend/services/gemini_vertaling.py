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

EN FLASH GAAT VOOR FLASH-LITE, HOEWEL DAT DUURDER IS (gemeten 19-09-2026 op zes
echte Engelse advertenties uit de voorraad). Flash-Lite maakte van "Grey Ralph
Lauren Jumper" twee keer achter elkaar een verkeerd gespeld "Grije" en zelfs
"Gri<arabisch teken>e"; dat zou zo als titel op Marktplaats staan, en geen enkele
controle in `_vertaal` ziet een spelfout. Flash schreef "Grijze" en las verder
netjes. Flash gaf wel 3 van de 6 keer een 503 ("high demand"), dus Flash-Lite
blijft erachter staan als terugval: liever een advertentie met een schoonheidsfout
dan een advertentie die blijft wachten. Het vangnet draait alleen tijdens een
storing, dus het prijsverschil valt in het niet bij een verkeerd gespelde titel.
"""
from __future__ import annotations

import collections
import logging
import re
import time

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

# De aliassen die Google zelf bijhoudt. Die blijven goed als er een nieuwe reeks
# uitkomt, dus ze gaan voor op een vaste naam, die ooit wordt opgeheven.
_ALIAS_LITE = "gemini-flash-lite-latest"
_ALIAS_FLASH = "gemini-flash-latest"
_MAX_KANDIDATEN = 4

# WAT WE WÉL ONTHOUDEN EN WAT NIET (19-09-2026). Eerst onthield dit bestand welk
# model gewerkt had. Gevolg, live gemeten: Flash gaf één keer 503 ("high demand"),
# het vangnet week uit naar Flash-Lite, en bleef daar de rest van de dag — dus
# ook alle advertenties daarna kregen de slechtere vertaling. Eén mislukt verzoek
# is geen reden om het betere model af te schrijven. Wat wél blijvend is: een 404
# betekent dat het model is opgeheven, en die naam hoeven we nooit meer te
# proberen. De lijst van Google verandert ook niet per minuut, dus die bewaren we.
_OPGEHEVEN: set[str] = set()
_LIJST: list[str] | None = None

# Wat Google antwoordde sinds de laatste herstart, per HTTP-code (op /health).
# Railway-logs en AI Studio zijn van buitenaf niet te lezen; dit wel.
TELLER: collections.Counter = collections.Counter()


def beschikbaar() -> bool:
    """Is er een Google-sleutel? Zo niet, dan bestaat het vangnet niet."""
    return bool(settings.google_api_key)


def _versie(naam: str) -> float:
    gevonden = re.search(r"gemini-(\d+(?:\.\d+)?)", naam)
    return float(gevonden.group(1)) if gevonden else 0.0


def _van_google() -> list[str]:
    """Namen die Google noemt. Leeg bij storing; dan doen de aliassen het werk."""
    global _LIJST
    if _LIJST is not None:
        return _LIJST
    try:
        antwoord = httpx.get(f"{_BASIS}/models",
                             params={"key": settings.google_api_key},
                             timeout=_TIJDSLIMIET)
        antwoord.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning("Vertaalvangnet: modellenlijst ophalen mislukte (%s)", e)
        return []   # bewust niet bewaren: een storing mag geen blijvend lege lijst worden
    namen = []
    for model in antwoord.json().get("models", []):
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        naam = (model.get("name") or "").replace("models/", "")
        if naam and not any(woord in naam for woord in _NIET_BRUIKBAAR):
            namen.append(naam)
    _LIJST = namen
    return namen


def _kandidaten() -> list[str]:
    """Wie we achter elkaar proberen: beste Nederlands eerst, dan beschikbaarheid."""
    namen = _van_google()
    lite = sorted((n for n in namen if "flash-lite" in n and n != _ALIAS_LITE),
                  key=_versie, reverse=True)
    flash = sorted((n for n in namen if "flash" in n and "lite" not in n
                    and n != _ALIAS_FLASH), key=_versie, reverse=True)
    # Twee keer kwaliteit, dan twee keer zekerheid: de alias die Google zelf
    # bijhoudt en de nieuwste eigen naam, eerst van Flash en daarna van Flash-Lite.
    rij = [_ALIAS_FLASH] + flash[:1] + [_ALIAS_LITE] + lite[:1]
    uniek = [n for n in dict.fromkeys(rij) if n and n not in _OPGEHEVEN]
    return uniek[:_MAX_KANDIDATEN]


def _opvolger_uit_de_klacht(tekst: str) -> str | None:
    """Een 404 noemt vaak zelf welk model ervoor in de plaats is gekomen."""
    gevonden = re.search(r"use\s+models/([A-Za-z0-9._-]+)", tekst or "")
    return gevonden.group(1) if gevonden else None


# DENKRUIMTE BOVENOP HET ANTWOORD (gemeten 23-09-2026 op gemini-3.8-flash).
# Flash denkt eerst na, en die gedachten tellen mee in maxOutputTokens. Met een
# grens van 200, genoeg voor een rubriekantwoord, gingen er 194 op aan denken en
# kwam er '{"gender' terug met finishReason MAX_TOKENS. Het denken uitzetten kan
# niet op elk model hetzelfde: Flash accepteert thinkingBudget 0, Flash-Lite
# weigert precies die instelling met een 400. Daarom geven we ruimte in plaats van
# het denken uit te zetten. Een gratis laag rekent daar niets voor.
_DENKRUIMTE = 8192


def _vraag(model: str, opdracht: str, max_tokens: int = 4096,
           tijdslimiet: float = _TIJDSLIMIET, denken: bool = True) -> httpx.Response:
    config = {"temperature": 0,   # vertalen en indelen hoeven niet creatief te zijn
              "maxOutputTokens": max_tokens + _DENKRUIMTE}
    # ZONDER DENKSTAP (gemeten 23-09-2026 op 199 echte artikelen): Flash deelde
    # zonder denken 182 van de 199 in dezelfde rubriek in als met, in 65 in plaats
    # van 177 seconden. Flash-Lite denkt uit zichzelf niet en weigert
    # thinkingBudget 0 met een 400, dus die krijgt de instelling niet.
    if not denken and "lite" not in model:
        config["thinkingConfig"] = {"thinkingBudget": 0}
    antwoord = httpx.post(
        f"{_BASIS}/models/{model}:generateContent",
        params={"key": settings.google_api_key},
        json={"contents": [{"parts": [{"text": opdracht}]}], "generationConfig": config},
        timeout=tijdslimiet,
    )
    if antwoord.status_code == 400 and "thinkingConfig" in config:
        # Een model dat de instelling niet kent: dan maar mét denkstap.
        del config["thinkingConfig"]
        antwoord = httpx.post(
            f"{_BASIS}/models/{model}:generateContent",
            params={"key": settings.google_api_key},
            json={"contents": [{"parts": [{"text": opdracht}]}], "generationConfig": config},
            timeout=tijdslimiet,
        )
    return antwoord


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
    return vraag(opdracht)


def vraag(opdracht: str, max_tokens: int = 4096,
          tijdslimiet: float = _TIJDSLIMIET, denken: bool = True) -> str | None:
    """Elke tekstvraag aan Gemini, met dezelfde modelkeuze als het vertalen.

    None betekent: het lukte niet (geen sleutel, alle modellen plat, afgekapt).
    backend/services/taalmodel.py is de ingang die de rest van de code gebruikt."""
    if not beschikbaar():
        return None
    try:
        # TE DRUK IS GEEN NEE (24-09-2026). Op de gratis sleutel gaf Google
        # tussen 16:24 en 16:28 zeven van de acht keer 503 "high demand"; alle
        # modellen tegelijk, en dan ging de vraag naar het dure Claude. Zegt
        # iedereen alleen "te druk", dan na een korte pauze nog één ronde.
        for ronde, pauze in enumerate(_DRUKTE_PAUZES_S):
            if pauze:
                logger.info("Gemini: alle modellen te druk, over %ss nog een ronde", pauze)
                time.sleep(pauze)
            antwoord, te_druk = _een_ronde(opdracht, max_tokens, tijdslimiet, denken)
            if antwoord is not None and ronde:
                TELLER["gered_door_tweede_ronde"] += 1
            if antwoord is not None or not te_druk:
                return antwoord
        logger.warning("Vertaalvangnet: geen enkel Gemini-model wilde vertalen")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("Vertaalvangnet: Gemini deed het niet (%s: %s)", type(e).__name__, e)
        return None


# Eerste ronde meteen, bij alleen drukte nog één na een paar seconden.
_DRUKTE_PAUZES_S = (0, 4)


def _een_ronde(opdracht: str, max_tokens: int, tijdslimiet: float,
               denken: bool) -> tuple[str | None, bool]:
    """Alle kandidaten één keer. Geeft (antwoord, te_druk): het tweede is True
    als minstens één model te druk of onbereikbaar was en niemand nee zei."""
    te_druk = False
    rij = _kandidaten()
    geprobeerd: set[str] = set()
    while rij:
        model = rij.pop(0)
        if model in geprobeerd or model in _OPGEHEVEN:
            continue
        geprobeerd.add(model)
        try:
            antwoord = _vraag(model, opdracht, max_tokens, tijdslimiet, denken)
        except httpx.TransportError as e:
            # Een tijdslimiet of weggevallen verbinding bij één model is geen
            # reden om de volgende over te slaan.
            logger.warning("Gemini: %s antwoordde niet (%s), volgende", model,
                           type(e).__name__)
            TELLER["geen_verbinding"] += 1
            te_druk = True
            continue

        TELLER[f"http_{antwoord.status_code}"] += 1
        if antwoord.status_code == 200:
            if len(geprobeerd) > 1:
                logger.info("Vertaalvangnet week uit naar Gemini-model %s", model)
            return _lees_antwoord(antwoord), False

        klacht = antwoord.text[:300]
        if antwoord.status_code in (404, 429, 500, 502, 503, 504):
            # Opgeheven, niet beschikbaar op deze rekening, of te druk
            # (gemeten: Flash gaf 3 van de 6 keer 503). De volgende kandidaat
            # krijgt hem, en noemt de klacht zelf een opvolger, dan gaat die
            # vooraan.
            logger.warning("Vertaalvangnet: %s doet het niet (HTTP %s), volgende",
                           model, antwoord.status_code)
            if antwoord.status_code != 404:
                te_druk = True
            else:
                _OPGEHEVEN.add(model)
                opvolger = _opvolger_uit_de_klacht(klacht)
                if opvolger and opvolger not in geprobeerd:
                    rij.insert(0, opvolger)
            continue

        logger.warning("Vertaalvangnet: Gemini gaf HTTP %s (%s)",
                       antwoord.status_code, klacht)
        return None, False
    return None, te_druk
