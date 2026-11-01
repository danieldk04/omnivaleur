"""Vertalen via Azure Translator, vóór de taalmodellen.

WAAROM (01-11-2026, Daniel)
Op 31-10 kostte vertalen via Gemini EUR 5,49 op één dag en was het tegoed op:
Goudlief zette 2.588 artikelen tegelijk door naar Marktplaats en 2dehands, en
titel en omschrijving gingen elk naar het taalmodel (~1.380 vragen à ~0,4 cent).
Azure Translator F0 geeft 2 miljoen tekens per maand gratis. Gemeten: in oktober
moest er ~670.000 tekens vertaald worden, en ~237.000 als elke regel maar één keer
gaat. Dat past ruim.

HOE
Per regel, niet per tekst. Goudliefs omschrijvingen zijn specificatieblokken
("Material:", "Four Seasons") die in duizenden artikelen terugkomen; een regel die
al eens vertaald is komt uit het geheugen en kost niets. Een regel die Azure zelf
al als doeltaal herkent blijft letterlijk staan. Het merk gaat via een vaste
vertaling van Azure (mstrans:dictionary) ongewijzigd terug.

None betekent: lukte niet (geen sleutel, tegoed op, storing). De aanroeper valt
dan terug op het taalmodel, precies zoals het hiervoor ging.
"""
from __future__ import annotations

import collections
import html
import logging
import re

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

_URL = "https://api.cognitive.microsofttranslator.com/translate"
_TIJDSLIMIET = 20.0
# Azure neemt hooguit 1.000 stukken en 50.000 tekens per verzoek.
_PER_VERZOEK = 100
_TEKENS_PER_VERZOEK = 40_000
_GEHEUGEN_MAX = 50_000

# (doeltaal, merk, regel) -> vertaalde regel. Per proces; een herstart begint leeg.
_GEHEUGEN: "collections.OrderedDict[tuple, str]" = collections.OrderedDict()

# Sinds de laatste herstart, op /health: http-codes, uit_geheugen, tekens_gevraagd.
TELLER: collections.Counter = collections.Counter()

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def beschikbaar() -> bool:
    return bool(settings.azure_translator_key)


def _beschermd(regel: str, merk: str | None) -> str:
    if not merk or merk.lower() not in regel.lower():
        return regel
    vast = html.escape(merk, quote=True)
    return re.sub(re.escape(merk),
                  lambda m: f'<mstrans:dictionary translation="{vast}">{m.group(0)}</mstrans:dictionary>',
                  regel, flags=re.IGNORECASE)


def _vraag(regels: list[str], doeltaal: str, merk: str | None) -> list[str] | None:
    headers = {"Ocp-Apim-Subscription-Key": settings.azure_translator_key,
               "Content-Type": "application/json"}
    if settings.azure_translator_region:
        headers["Ocp-Apim-Subscription-Region"] = settings.azure_translator_region
    TELLER["tekens_gevraagd"] += sum(len(r) for r in regels)
    antwoord = httpx.post(_URL, params={"api-version": "3.0", "to": doeltaal},
                          headers=headers,
                          json=[{"Text": _beschermd(r, merk)} for r in regels],
                          timeout=_TIJDSLIMIET)
    TELLER[f"http_{antwoord.status_code}"] += 1
    if antwoord.status_code != 200:
        # 401 sleutel fout, 403/429 gratis tegoed of tempo op: het taalmodel neemt over.
        logger.warning("Azure-vertaling gaf %s: %s", antwoord.status_code, antwoord.text[:200])
        return None
    uit = []
    for regel, stuk in zip(regels, antwoord.json()):
        taal = ((stuk.get("detectedLanguage") or {}).get("language") or "").lower()
        tekst = ((stuk.get("translations") or [{}])[0].get("text") or "").strip()
        uit.append(regel if taal == doeltaal or not tekst else tekst)
    return uit if len(uit) == len(regels) else None


def vertaal(tekst: str, doeltaal: str, merk: str | None = None) -> str | None:
    """De tekst in `doeltaal`, met dezelfde regelindeling. None als het niet lukte."""
    if not beschikbaar() or not tekst or not tekst.strip():
        return None
    regels = tekst.split("\n")
    nodig = list(dict.fromkeys(
        r.strip() for r in regels
        if r.strip() and _LETTER.search(r) and (doeltaal, merk, r.strip()) not in _GEHEUGEN))
    TELLER["uit_geheugen"] += sum(1 for r in regels if r.strip() and _LETTER.search(r)) - len(nodig)
    try:
        blok: list[str] = []
        for regel in nodig + [None]:
            if regel is not None and len(blok) < _PER_VERZOEK and \
                    sum(map(len, blok)) + len(regel) < _TEKENS_PER_VERZOEK:
                blok.append(regel)
                continue
            if blok:
                vertaald = _vraag(blok, doeltaal, merk)
                if vertaald is None:
                    return None
                for oud, nieuw in zip(blok, vertaald):
                    _GEHEUGEN[(doeltaal, merk, oud)] = nieuw
                    if len(_GEHEUGEN) > _GEHEUGEN_MAX:
                        _GEHEUGEN.popitem(last=False)
            blok = [regel] if regel is not None else []
    except Exception as e:  # noqa: BLE001
        TELLER["fout"] += 1
        logger.warning("Azure-vertaling deed het niet (%s: %s)", type(e).__name__, e)
        return None

    def _regel(r: str) -> str:
        kern = r.strip()
        if not kern or not _LETTER.search(kern):
            return r
        nieuw = _GEHEUGEN.get((doeltaal, merk, kern), kern)
        return r[:len(r) - len(r.lstrip())] + nieuw

    return "\n".join(_regel(r) for r in regels)
