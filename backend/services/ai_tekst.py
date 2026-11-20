"""Zoekslimme titels en beschrijvingen per kanaal, met harde controle (20-11-2026).

Het model schrijft alleen VOORSTELLEN. Een voorstel komt pas door als gewone
code bewijst dat het niets nieuws bevat:

- titel: elk woord staat in de eigen velden van het artikel (titel, merk, kleur,
  maat, materiaal, rubriek), binnen de grens van het kanaal, het merk blijft,
  elk getal en elke maat uit de oude titel blijft, een haakjescode vooraan blijft.
- beschrijving: geen getal dat niet al in het artikel stond, hooguit 6 nieuwe
  woorden, geen adres, link of telefoonnummer dat niet al in de bron stond, en
  alle getallen en maten van de bron blijven.

Faalt een voorstel, dan krijgt het model EEN tweede poging met de precieze
reden. Faalt ook die, dan blijft de oude tekst staan: nooit iets half goeds.
Claude wordt hier nooit gebruikt (kosten), alleen Gemini via taalmodel.py.
"""
from __future__ import annotations

import json
import logging
import re

from backend.services import taalmodel
from backend.services.titel_ai import _lengte, _woorden, _CODE_VOORAAN, _MAAT

logger = logging.getLogger(__name__)

TITEL_GRENS = {"marktplaats": 60, "2dehands": 60, "vinted": 60, "ebay": 80}
BESCHRIJVING_GRENS = {"marktplaats": 3000, "2dehands": 3000, "vinted": 2000, "ebay": 4000}
PER_VRAAG = 10
MAX_NIEUWE_WOORDEN = 6
_GETAL = re.compile(r"\d+(?:[.,]\d+)?")
_LINK = re.compile(r"https?://|www\.|@\w+\.\w+|\b\d{2}[- ]?\d{3,}[- ]?\d{3,}\b", re.I)


def _velden(item: dict) -> str:
    return " ".join(str(item.get(k) or "") for k in
                    ("title", "brand", "color", "size", "material", "category", "gender"))


def titel_woordenschat(item: dict) -> set[str]:
    return set(_woorden(_velden(item)))


def titel_fout(item: dict, kanaal: str, nieuw: str) -> str | None:
    """None als het voorstel veilig is, anders de reden (ook voor de 2e poging)."""
    oud = str(item.get("title") or "")
    grens = TITEL_GRENS.get(kanaal, 60)
    if not nieuw or not isinstance(nieuw, str):
        return "empty"
    if _lengte(nieuw) > grens:
        return f"longer than {grens} characters"
    nieuw_w = _woorden(nieuw)
    vreemd = sorted(set(nieuw_w) - titel_woordenschat(item))
    if vreemd:
        return "contains words that are not in the item data: " + ", ".join(vreemd[:5])
    code = _CODE_VOORAAN.match(oud)
    if code and not nieuw.lstrip().startswith(code.group(1)):
        return "the code at the start must stay exactly"
    oud_w = _woorden(oud)
    for w in oud_w:
        if (w.isdigit() or w in _MAAT) and w not in nieuw_w:
            return f"the number or size '{w}' is missing"
    merk = _woorden(str(item.get("brand") or ""))
    if merk and not set(merk) <= set(nieuw_w):
        return "the brand is missing"
    return None


def _titel_opdracht(items: list[dict], kanaal: str, fouten: dict | None = None) -> str:
    grens = TITEL_GRENS.get(kanaal, 60)
    rijen = []
    for i, it in enumerate(items):
        r = {"i": i, "title": it.get("title"), "brand": it.get("brand"),
             "color": it.get("color"), "size": it.get("size"),
             "material": it.get("material"), "category": it.get("category")}
        if fouten and i in fouten:
            r["previous_attempt_rejected_because"] = fouten[i]
        rijen.append({k: v for k, v in r.items() if v})
    return (
        f"Rewrite each second-hand product title for the marketplace '{kanaal}' so buyers find it "
        f"in search: at most {grens} characters. Put what people search for first: product type, "
        "then brand, colour, size, material. Use ONLY words that appear in the item's own fields "
        "(title, brand, color, size, material, category); never add, translate or invent a word. "
        "Keep the language of the title. Keep brand, every number and every size. A code like (658) "
        "or #644 at the start stays exactly at the start. No filler like 'nice' or 'great', no emojis.\n"
        "Answer with ONLY a JSON array of strings, same order and count as the input.\n\nINPUT:\n"
        + json.dumps(rijen, ensure_ascii=False))


def _vraag_lijst(opdracht: str, n: int, wat: str) -> list | None:
    try:
        tekst = taalmodel.vraag(opdracht, max_tokens=2048, wat=wat, denken=False,
                                claude_toegestaan=False)
        tekst = re.sub(r"^```(?:json)?|```$", "", tekst.strip(), flags=re.M).strip()
        antwoord = json.loads(tekst)
    except (taalmodel.TaalmodelOnbeschikbaar, ValueError) as e:
        logger.warning("%s: blok overgeslagen: %s", wat, e)
        return None
    if not isinstance(antwoord, list) or len(antwoord) != n:
        return None
    return antwoord


def zoekslimme_titels(items: list[dict], kanaal: str) -> tuple[dict[str, str], dict]:
    """({item_id: nieuwe titel}, tellingen). Alleen voorstellen die de controle haalden.

    Twee pogingen per blok: de tweede krijgt de reden van de afkeuring mee."""
    uit: dict[str, str] = {}
    tel = {"gevraagd": 0, "goed_1": 0, "goed_2": 0, "afgekeurd": 0, "geen_antwoord": 0}
    for i in range(0, len(items), PER_VRAAG):
        blok = items[i:i + PER_VRAAG]
        tel["gevraagd"] += len(blok)
        antw = _vraag_lijst(_titel_opdracht(blok, kanaal), len(blok), "AI-titels per kanaal")
        if antw is None:
            tel["geen_antwoord"] += len(blok)
            continue
        fouten: dict[int, str] = {}
        for j, (it, nieuw) in enumerate(zip(blok, antw)):
            nieuw = nieuw.strip() if isinstance(nieuw, str) else ""
            f = titel_fout(it, kanaal, nieuw)
            if f is None:
                uit[it["id"]] = nieuw
                tel["goed_1"] += 1
            else:
                fouten[j] = f
        if not fouten:
            continue
        rest = [blok[j] for j in fouten]
        antw2 = _vraag_lijst(_titel_opdracht(rest, kanaal, {k: fouten[j] for k, j in enumerate(fouten)}),
                             len(rest), "AI-titels per kanaal, tweede poging")
        for k, it in enumerate(rest):
            nieuw = antw2[k].strip() if antw2 and isinstance(antw2[k], str) else ""
            if nieuw and titel_fout(it, kanaal, nieuw) is None:
                uit[it["id"]] = nieuw
                tel["goed_2"] += 1
            else:
                tel["afgekeurd"] += 1
    return uit, tel


# ── Beschrijving per kanaal ────────────────────────────────────────────────

def _getallen(tekst: str) -> set[str]:
    return {g.replace(",", ".") for g in _GETAL.findall(tekst or "")}


def beschrijving_fout(item: dict, kanaal: str, nieuw: str) -> str | None:
    bron = str(item.get("description") or "")
    kennis = bron + " " + _velden(item)
    if not isinstance(nieuw, str) or not nieuw.strip():
        return "empty"
    if len(nieuw) > BESCHRIJVING_GRENS.get(kanaal, 3000):
        return "too long"
    extra_getallen = _getallen(nieuw) - _getallen(kennis)
    if extra_getallen:
        return "contains numbers that are not in the source: " + ", ".join(sorted(extra_getallen)[:5])
    weg = _getallen(bron) - _getallen(nieuw)
    if weg:
        return "numbers from the source are missing: " + ", ".join(sorted(weg)[:5])
    if _LINK.search(nieuw) and not _LINK.search(kennis):
        return "contains a link, address or phone number that is not in the source"
    nieuwe_w = set(_woorden(nieuw)) - set(_woorden(kennis))
    if len(nieuwe_w) > MAX_NIEUWE_WOORDEN:
        return f"{len(nieuwe_w)} new words ({', '.join(sorted(nieuwe_w)[:8])}); at most {MAX_NIEUWE_WOORDEN} allowed"
    for w in _woorden(bron):
        if w in _MAAT and w not in _woorden(nieuw):
            return f"the size '{w}' is missing"
    return None


def _beschrijving_opdracht(item: dict, kanaal: str, fout: str | None) -> str:
    stijl = {"marktplaats": "short, practical, clear paragraphs, condition and pickup/shipping facts only if given",
             "2dehands": "short, practical, clear paragraphs, condition and pickup/shipping facts only if given",
             "vinted": "friendly and casual, short lines, easy to scan on a phone",
             "ebay": "neutral and complete, factual bullet-like lines"}.get(kanaal, "clear and factual")
    return (
        f"Rewrite this second-hand listing description for '{kanaal}': {stijl}. Keep the language of "
        "the original. STRICT: use only facts and words already in the item data; add NO new facts, "
        "numbers, measurements, links or promises; you may reorder, shorten and tidy, and add at most a "
        "few connecting words. Keep every number and size exactly. Answer with ONLY the new description "
        "text, no quotes, no explanation.\n"
        + (f"Your previous attempt was rejected because: {fout}. Fix exactly that.\n" if fout else "")
        + "ITEM DATA:\n" + json.dumps({k: item.get(k) for k in
                                     ("title", "brand", "color", "size", "material", "condition", "description")
                                     if item.get(k)}, ensure_ascii=False))


def herschrijf_beschrijving(item: dict, kanaal: str) -> tuple[str | None, dict]:
    """(nieuwe tekst of None, tellingen). Twee pogingen, daarna blijft het oude staan."""
    fout = None
    for poging in (1, 2):
        try:
            tekst = taalmodel.vraag(_beschrijving_opdracht(item, kanaal, fout), max_tokens=1500,
                                    wat="AI-beschrijving", denken=False, claude_toegestaan=False).strip()
        except taalmodel.TaalmodelOnbeschikbaar:
            return None, {"geen_antwoord": 1}
        tekst = re.sub(r"^```\w*|```$", "", tekst, flags=re.M).strip().strip('"')
        fout = beschrijving_fout(item, kanaal, tekst)
        if fout is None:
            return tekst, {f"goed_{poging}": 1}
    return None, {"afgekeurd": 1, "reden": fout}
