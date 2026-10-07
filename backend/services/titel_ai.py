"""Lange titels laten inkorten door een taalmodel, met een harde controle erachter.

WAAROM (07-10-2026, Goudlief)
Marktplaats en 2dehands nemen 60 tekens. `_mp_titel` kapt af op een heel woord,
maar kan niet kiezen wat weg mag: "Navy Ralph Lauren Polo Bear Sweater - Size S -
Excellent Condition" verliest dan het stuk dat de koper wil lezen. Een taalmodel
kan opvulwoorden weglaten en het merk en de maat laten staan.

VEILIGHEID: het model mag nooit iets toevoegen of verzinnen. Een voorstel telt
alleen als het binnen de grens past, elk woord ervan in de oude titel staat, een
haakjescode vooraan (het eigen nummer van de verkoper) blijft staan en elk getal
en elke maat uit de oude titel terugkomt. Klopt iets niet of is het model er niet,
dan krijgt de aanroeper niets terug en houdt hij de gewone inkorting.
"""
from __future__ import annotations

import json
import logging
import re

from backend.services import taalmodel

logger = logging.getLogger(__name__)

MAX_TITEL = 60
PER_VRAAG = 20

_WOORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_CODE_VOORAAN = re.compile(r"^\s*(\(\d+\)|#\d+)")
_MAAT = {"xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl"}


def _lengte(tekst: str) -> int:
    """Lengte zoals de browser hem telt (een emoji telt daar als twee)."""
    return len(tekst.encode("utf-16-le")) // 2


def _woorden(tekst: str) -> list[str]:
    return [w.lower() for w in _WOORD.findall(tekst)]


def voorstel_is_veilig(oud: str, nieuw: str) -> bool:
    """Of `nieuw` een inkorting van `oud` is en niets anders."""
    if not nieuw or nieuw == oud or _lengte(nieuw) > MAX_TITEL:
        return False
    oud_w, nieuw_w = _woorden(oud), _woorden(nieuw)
    if not nieuw_w or not set(nieuw_w) <= set(oud_w):
        return False
    code = _CODE_VOORAAN.match(oud)
    if code and not nieuw.lstrip().startswith(code.group(1)):
        return False
    # Getallen en maten zijn wat een koper zoekt; die mogen niet wegvallen.
    for w in oud_w:
        if (w.isdigit() or w in _MAAT) and w not in nieuw_w:
            return False
    return True


def _opdracht(titels: list[str]) -> str:
    return (
        "Shorten each product title to at most 55 characters for a second-hand "
        "marketplace. Rules: keep the original language of each title, never "
        "translate. Only remove words, never add or change words. Keep brand, "
        "product type, colour, size and any number. A code like (658) or #644 at "
        "the start must stay exactly as is. Remove filler first: condition "
        "phrases like 'Very Good Condition' or 'Excellent', 'Authentic', "
        "'Size', repeated words. Do not leave a loose dash, comma or small word "
        "at the end.\n"
        "Answer with only a JSON array of strings, same order and same count as "
        "the input, no explanation.\n\nINPUT:\n" + json.dumps(titels, ensure_ascii=False)
    )


def kort_titels(titels: list[str]) -> dict[str, str]:
    """{oude titel: kortere titel} voor elke titel waar een veilig voorstel voor kwam.

    Titels die al binnen de grens passen worden niet gevraagd. Een titel zonder
    voorstel ontbreekt in het antwoord; de aanroeper valt dan terug op _mp_titel."""
    te_lang = list(dict.fromkeys(t for t in titels if t and _lengte(t) > MAX_TITEL))
    uit: dict[str, str] = {}
    for i in range(0, len(te_lang), PER_VRAAG):
        blok = te_lang[i:i + PER_VRAAG]
        try:
            tekst = taalmodel.vraag(_opdracht(blok), max_tokens=2048,
                                    wat="AI-titels", denken=False)
            tekst = re.sub(r"^```(?:json)?|```$", "", tekst.strip(), flags=re.M).strip()
            antwoord = json.loads(tekst)
        except (taalmodel.TaalmodelOnbeschikbaar, ValueError) as e:
            logger.warning("AI-titels: blok van %d overgeslagen: %s", len(blok), e)
            continue
        if not isinstance(antwoord, list) or len(antwoord) != len(blok):
            logger.warning("AI-titels: antwoord past niet bij de vraag, blok overgeslagen")
            continue
        for oud, nieuw in zip(blok, antwoord):
            if isinstance(nieuw, str) and voorstel_is_veilig(oud, nieuw.strip()):
                uit[oud] = nieuw.strip()
    return uit
