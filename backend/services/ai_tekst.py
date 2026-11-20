"""Titels inkorten met behoud en beschrijvingen per kanaal, met harde controle (20-11-2026).

Het model schrijft alleen VOORSTELLEN. Een voorstel komt pas door als gewone
code bewijst dat het niets nieuws bevat:

- titel: alleen voor titels die te lang zijn voor het kanaal; elk woord stond al in
  de oude titel, binnen de grens, merk en kleur blijven, elk getal en elke maat
  blijft, een haakjescode vooraan blijft, en minstens de helft van de woorden blijft.
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


# WAT DE METING VAN 20-11 LEERDE: een controle die "alleen woorden uit de eigen
# velden" toestaat laat slechte titels door. 'Zilveren miniatuur snotneus, 19e
# eeuws' werd 'Silver', 'Josh V pantalon' kreeg 'S / 36 / 8' erbij. Daarom mag een
# voorstel nu ALLEEN woorden bevatten die in de oude titel stonden (weglaten en
# het producttype naar voren halen), en alleen als de oude titel te lang is.
# Het model weglaten van te veel (minder dan de helft van de woorden) is ook fout.
MIN_BEHOUD = 0.5


def titel_woordenschat(item: dict) -> set[str]:
    return set(_woorden(str(item.get("title") or "")))


def titel_fout(item: dict, kanaal: str, nieuw: str) -> str | None:
    """None als het voorstel veilig is, anders de reden (ook voor de 2e poging)."""
    oud = str(item.get("title") or "")
    grens = TITEL_GRENS.get(kanaal, 60)
    if not nieuw or not isinstance(nieuw, str):
        return "empty"
    if _lengte(nieuw) > grens:
        return f"longer than {grens} characters"
    nieuw_w = _woorden(nieuw)
    oud_w = _woorden(oud)
    vreemd = sorted(set(nieuw_w) - set(oud_w))
    if vreemd:
        return "contains words that are not in the original title: " + ", ".join(vreemd[:5])
    code = _CODE_VOORAAN.match(oud)
    if code and not nieuw.lstrip().startswith(code.group(1)):
        return "the code at the start must stay exactly"
    for w in oud_w:
        if (w.isdigit() or w in _MAAT) and w not in nieuw_w:
            return f"the number or size '{w}' is missing"
    for veld in ("brand", "color"):
        woorden = _woorden(str(item.get(veld) or ""))
        if woorden and set(woorden) <= set(oud_w) and not set(woorden) <= set(nieuw_w):
            return f"the {veld} is missing"
    if oud_w and len(set(nieuw_w)) < MIN_BEHOUD * len(set(oud_w)):
        return "too many words were removed, keep at least half"
    return None


def _titel_opdracht(items: list[dict], kanaal: str, fouten: dict | None = None) -> str:
    grens = TITEL_GRENS.get(kanaal, 60)
    rijen = []
    for i, it in enumerate(items):
        r = {"i": i, "title": it.get("title"), "brand": it.get("brand"), "color": it.get("color")}
        if fouten and i in fouten:
            r["previous_attempt_rejected_because"] = fouten[i]
        rijen.append({k: v for k, v in r.items() if v})
    return (
        f"Each product title is too long for the marketplace '{kanaal}'. Shorten each to at most "
        f"{grens} characters. ONLY REMOVE words, never add, change or translate a word; you may put the "
        "product type first. Remove filler first (condition phrases like 'Excellent Condition', "
        "'Authentic', 'Size', fit words, repeated words). Keep brand, colour, every number and every "
        "size. A code like (658) or #644 at the start stays exactly at the start. Keep the language of "
        "the title. Do not leave a loose dash, comma or small word at the end.\n"
        "Answer with ONLY a JSON array of strings, same order and count as the input.\n\nINPUT:\n"
        + json.dumps(rijen, ensure_ascii=False))


def _vraag_lijst(opdracht: str, n: int, wat: str) -> list | None:
    try:
        tekst = taalmodel.vraag(opdracht, max_tokens=2048, wat=wat, denken=False,
                                claude_toegestaan=False, alleen_lite=True)
        tekst = re.sub(r"^```(?:json)?|```$", "", tekst.strip(), flags=re.M).strip()
        antwoord = json.loads(tekst)
    except (taalmodel.TaalmodelOnbeschikbaar, ValueError) as e:
        logger.warning("%s: blok overgeslagen: %s", wat, e)
        return None
    if not isinstance(antwoord, list) or len(antwoord) != n:
        return None
    return antwoord


POGINGEN = 3
_LOS_EIND = {"en", "of", "met", "van", "de", "het", "een", "voor", "in", "op", "and", "with", "the", "a", "-", "–", "&"}


def kort_af(nieuw: str, grens: int) -> str:
    """Laatste redmiddel voor een voorstel dat alleen nog te lang is: hele woorden van
    het eind halen. De uitkomst gaat daarna door dezelfde harde controle."""
    woorden = nieuw.split()
    while woorden and _lengte(" ".join(woorden)) > grens:
        woorden.pop()
    while woorden and (woorden[-1].lower() in _LOS_EIND or not woorden[-1].strip(" ,;:/-–|.(")):
        woorden.pop()
    return " ".join(woorden).rstrip(" ,;:/-–|.(")


def _afkeuring_met_cijfers(it: dict, kanaal: str, nieuw: str, f: str) -> str:
    """De reden, met het antwoord erbij en bij te lang precies hoeveel eraf moet."""
    grens = TITEL_GRENS.get(kanaal, 60)
    if f.startswith("longer"):
        f = f"your answer '{nieuw}' is {_lengte(nieuw)} characters, remove at least {_lengte(nieuw) - grens} more"
    else:
        f = f"your answer '{nieuw}' was rejected: {f}"
    return f


def zoekslimme_titels(items: list[dict], kanaal: str) -> tuple[dict[str, str], dict]:
    """({item_id: nieuwe titel}, tellingen). Alleen voorstellen die de controle haalden.

    Hooguit POGINGEN rondes per blok: elke volgende krijgt de reden van de afkeuring
    mee, met het antwoord en bij te lang het aantal tekens dat er nog af moet.
    Titels zonder goedgekeurd voorstel ontbreken in het antwoord (de aanroeper houdt
    dan de gewone inkorting)."""
    uit: dict[str, str] = {}
    tel = {"gevraagd": 0, "goed_1": 0, "goed_2": 0, "goed_3": 0, "afgekeurd": 0,
           "geen_antwoord": 0, "redenen": []}
    grens = TITEL_GRENS.get(kanaal, 60)
    # Alleen titels die echt te lang zijn: een titel die past blijft zoals de klant hem schreef.
    items = [it for it in items if _lengte(str(it.get("title") or "")) > grens]
    for i in range(0, len(items), PER_VRAAG):
        blok = items[i:i + PER_VRAAG]
        tel["gevraagd"] += len(blok)
        open_: list[dict] = list(blok)
        fouten: dict[int, str] = {}
        laatste: dict[str, tuple[str, str]] = {}
        for poging in range(1, POGINGEN + 1):
            antw = _vraag_lijst(_titel_opdracht(open_, kanaal, fouten if poging > 1 else None),
                                len(open_), f"AI-titels per kanaal, poging {poging}")
            if antw is None:
                break
            nog_open, fouten = [], {}
            for it, nieuw in zip(open_, antw):
                nieuw = nieuw.strip() if isinstance(nieuw, str) else ""
                f = titel_fout(it, kanaal, nieuw)
                if f is None:
                    uit[it["id"]] = nieuw
                    tel[f"goed_{poging}"] += 1
                else:
                    fouten[len(nog_open)] = _afkeuring_met_cijfers(it, kanaal, nieuw, f)
                    laatste[it["id"]] = (nieuw, f)
                    nog_open.append(it)
            open_ = nog_open
            if not open_:
                break
        for it in open_:
            nieuw, f = laatste.get(it["id"], ("", ""))
            if f.startswith("longer"):
                kort = kort_af(nieuw, grens)
                if kort and titel_fout(it, kanaal, kort) is None:
                    uit[it["id"]] = kort
                    tel["goed_afgekort"] = tel.get("goed_afgekort", 0) + 1
                    continue
            if it["id"] in laatste:
                tel["afgekeurd"] += 1
                tel["redenen"].append((it.get("title"), *laatste[it["id"]]))
            else:
                tel["geen_antwoord"] += 1
    return uit, tel


# ── Beschrijving per kanaal ────────────────────────────────────────────────

def _getallen(tekst: str) -> set[str]:
    return {g.replace(",", ".") for g in _GETAL.findall(tekst or "")}


# Een herschreven tekst mag niets weglaten wat een koper moet weten. Gemeten 20-11:
# bij 16 van 157 goedgekeurde teksten bleef minder dan de helft van de woorden over.
MIN_BEHOUD_TEKST = 0.7
_GEBREK = {"kapot", "gaatje", "gaten", "vlek", "vlekken", "beschadigd", "kras", "krassen", "scheur",
           "barst", "gebruikssporen", "slijtage", "defect", "damage", "damaged", "stain", "stains",
           "hole", "holes", "scratch", "scratches", "crack", "cracked", "flaw", "flaws", "worn",
           "missing", "mist", "ontbreekt", "loszittend", "reparatie", "repair", "chip", "deuk"}


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
    bron_w, nieuw_w = set(_woorden(bron)), set(_woorden(nieuw))
    weg_gebrek = sorted((bron_w & _GEBREK) - nieuw_w)
    if weg_gebrek:
        return "a flaw or defect mentioned in the source is missing: " + ", ".join(weg_gebrek)
    if bron_w and len(bron_w & nieuw_w) < MIN_BEHOUD_TEKST * len(bron_w):
        return "too much of the source is dropped, keep at least 70% of its words"
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
        "few connecting words. Keep ALL information of the original, every sentence and every flaw or defect, "
        "only reorder and tidy. Keep every number and size exactly. Answer with ONLY the new description "
        "text, no quotes, no explanation.\n"
        + (f"Your previous attempt was rejected because: {fout}. Fix exactly that.\n" if fout else "")
        + "ITEM DATA:\n" + json.dumps({k: item.get(k) for k in
                                     ("title", "brand", "color", "size", "material", "condition", "description")
                                     if item.get(k)}, ensure_ascii=False))


def herschrijf_beschrijving(item: dict, kanaal: str) -> tuple[str | None, dict]:
    """(nieuwe tekst of None, tellingen). Drie pogingen, daarna blijft het oude staan."""
    fout = None
    for poging in (1, 2, 3):
        try:
            tekst = taalmodel.vraag(_beschrijving_opdracht(item, kanaal, fout), max_tokens=1500,
                                    wat="AI-beschrijving", denken=False, claude_toegestaan=False, alleen_lite=True).strip()
        except taalmodel.TaalmodelOnbeschikbaar:
            return None, {"geen_antwoord": 1}
        tekst = re.sub(r"^```\w*|```$", "", tekst, flags=re.M).strip().strip('"')
        fout = beschrijving_fout(item, kanaal, tekst)
        if fout is None:
            return tekst, {f"goed_{poging}": 1}
    return None, {"afgekeurd": 1, "reden": fout}
