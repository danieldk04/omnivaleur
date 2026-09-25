"""
Informatieve beelden in de huisstijl, gemaakt in HTML (25-09-2026).

Daniel: de blogs toonden steeds dezelfde acht app-screenshots, ook waar die niets
met het onderwerp te maken hadden, en betaalde beeldgeneratie wil hij niet. Dit
maakt per artikel drie soorten kaarten, gratis en altijd over het onderwerp:

  1. kerncijfers  — hooguit drie getallen uit het artikel zelf
  2. checklist    — vier tot zes korte actiepunten uit het artikel
  3. voorbeeld    — een nagebouwd Omnivaleur-scherm met een artikel dat bij het
                    onderwerp past, duidelijk gelabeld als illustratie

Een taalmodel kiest de inhoud, de code tekent. Net als bij infographics.py geldt:
geen getal dat niet letterlijk in de tekst staat (`_staat_in_tekst`), anders
wordt de kaart niet getekend. Het is HTML met inline stijl, geen plaatje: scherp
op elk scherm, leesbaar voor Google, en geen bestand dat pas na de deploy
meekomt. Invoegen gaat met string-splicing (figures.spread_figures), nooit via
BeautifulSoup opnieuw opschrijven.
"""
from __future__ import annotations

import html
import json
import logging
import re

from backend.content.figures import spread_figures

logger = logging.getLogger(__name__)

MARKER = 'class="info-kaart'
PLATFORMS = ["Marktplaats", "2dehands", "Vinted", "eBay", "Etsy", "Shopify"]
STATUS = {"live", "publishing", "sold", "queued"}
_STATUS_TEKST = {
    "en": {"live": "Live", "publishing": "Publishing", "sold": "Sold", "queued": "Queued"},
    "nl": {"live": "Live", "publishing": "Wordt geplaatst", "sold": "Verkocht", "queued": "In de rij"},
}
_STATUS_KLEUR = {
    "live": ("#ecfdf5", "#047857"), "publishing": ("#eff6ff", "#1d4ed8"),
    "sold": ("#f1f5f9", "#475569"), "queued": ("#fefce8", "#a16207"),
}
_TEKST = {
    "en": {"cijfers": "Key numbers", "check": "Checklist", "voorbeeld": "Example in Omnivaleur",
           "bijschrift": "Illustration: how an item like this shows up in the Omnivaleur dashboard."},
    "nl": {"cijfers": "In cijfers", "check": "Checklist", "voorbeeld": "Voorbeeld in Omnivaleur",
           "bijschrift": "Illustratie: zo staat een artikel als dit in het Omnivaleur-dashboard."},
}
_FONT = "font-family:Inter,system-ui,-apple-system,sans-serif"

# Lijntekening per soort artikel, in plaats van een losse letter in een
# kleurvlak (dat oogde als een automatisch gemaakt plaatje).
_ICOON = {
    "clothing": '<path d="M9 4l3 2 3-2 5 3-2 4-2-1v10H8V10l-2 1-2-4z"/>',
    "shoes": '<path d="M3 16h18v2H3zM4 16l1-7h4l2 3 6 1a4 4 0 014 3"/>',
    "bag": '<path d="M5 9h14l-1 11H6zM9 9V7a3 3 0 016 0v2"/>',
    "jewelry": '<circle cx="12" cy="14" r="6"/><path d="M9 5h6l-3 3z"/>',
    "camera": '<rect x="3" y="7" width="18" height="12" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 7l2-3h4l2 3"/>',
    "book": '<path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 19V5"/>',
    "furniture": '<path d="M6 11V5h12v6M4 11h16v4H4zM6 15v5M18 15v5"/>',
    "electronics": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>',
    "toys": '<circle cx="12" cy="8" r="4"/><path d="M6 21c0-4 3-7 6-7s6 3 6 7z"/>',
    "records": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/>',
    "watch": '<circle cx="12" cy="12" r="6"/><path d="M9 3h6l1 3M9 21h6l1-3M12 9v3l2 1"/>',
    "home": '<path d="M4 11l8-7 8 7v9H4zM10 20v-6h4v6"/>',
    "other": '<path d="M3 12l9-9h8v8l-9 9zM15 7h.01"/>',
}
CATEGORIEEN = list(_ICOON)
# Accentkleur wisselt per artikel binnen de huisstijl, zodat niet elke blog
# exact hetzelfde blok toont.
_ACCENTEN = [("#2563eb", "#eff6ff"), ("#047857", "#ecfdf5"), ("#7c3aed", "#f5f3ff"), ("#0e7490", "#ecfeff")]


def _accent(title: str) -> tuple[str, str]:
    return _ACCENTEN[sum(map(ord, title or "")) % len(_ACCENTEN)]


def _platte_tekst(body_html: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body_html or ""))).lower()


def _staat_in_tekst(waarde: str, tekst: str) -> bool:
    """Letterlijk en als los woord in de tekst. Een kaal getal onder de tien
    zonder eenheid ("0", "6") staat altijd wel ergens en bewijst dus niets; zo
    kwam "0 Marktplaats-sjablonen bij List Perfectly" door de eerste proef."""
    w = re.sub(r"\s+", " ", (waarde or "").strip().lower())
    if not w or re.fullmatch(r"\d", w):
        return False
    return re.search(r"(?<![\w.,])" + re.escape(w) + r"(?![\w])", tekst) is not None


def _prompt(title: str, body_html: str, language: str) -> str:
    taal = "Dutch" if language == "nl" else "English"
    tekst = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body_html))[:14000]
    return f"""You design visual summary cards for a blog article. Article title: "{title}".

Return ONLY JSON, no markdown fences, in {taal}, in exactly this shape:
{{"cijfers": [{{"waarde": "...", "label": "..."}}],
  "checklist": {{"titel": "...", "punten": ["...", "..."]}},
  "voorbeeld": {{"artikel": "...", "categorie": "...", "prijs": 45, "kanalen": {{"Vinted": "live"}}}}}}

Write like an experienced second-hand seller jotting notes for a colleague, not like a marketing tool or an AI. {"Use informal Dutch with 'je', never 'u', and plain Dutch words: 'advertentie' not 'listing', 'verkoper' not 'reseller', 'plaatsen' not 'listen'." if language == "nl" else ""}
- Normal sentence case everywhere. Never Title Case, never a colon in a title, no emoji, no exclamation marks.
- Full, natural sentences with articles and small words ("Weigh the box before you buy the label"), not telegram style ("Weigh sealed box in grams").
- Avoid: seamless, effortless, streamline, unlock, boost, leverage, game-changer, ultimate, essential, robust.

Rules:
- cijfers: 0 to 3 items that matter for THIS article's main question (not side topics: no tax or DAC7 thresholds unless the article is mainly about tax). "waarde" is ONE short number or amount (max 12 characters, e.g. "€6,95", "14 days", "30%"), never a list of names, and MUST be copied character for character from the article text below. If there are no numbers that answer the main question, return an empty list. Never invent or round a number. "label": 3 to 8 plain words saying what the number means for the reader.
- checklist: 4 to 6 concrete things to do, each one line of at most 80 characters, taken from the article's advice, in the order a reader would do them. "titel": a short plain phrase (max 6 words) like "Before you drop off the parcel".
- voorbeeld: one realistic second-hand item that fits this article's topic, named like a real seller would list it, at most 45 characters (brand, model, size or detail; e.g. "Levi's 501 jeans, W32 L32"), "categorie" from exactly: {", ".join(CATEGORIEEN)}, a price as a number the way sellers price (e.g. 25, 35, 49, 120), and 2 to 4 channels from exactly this list: {", ".join(PLATFORMS)}, each with a status from: live, publishing, sold, queued. At most one "sold". If the article is about a platform, include that platform.

ARTICLE TEXT:
{tekst}
"""


def extract(title: str, body_html: str, language: str = "en") -> dict | None:
    from backend.services import taalmodel
    try:
        raw = taalmodel.vraag(_prompt(title, body_html, language), max_tokens=1500,
                              tijdslimiet=90.0, wat="infokaarten")
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Infokaarten: geen bruikbare inhoud ({e})")
        return None


def _figure(inhoud: str, soort: str, bijschrift: str = "") -> str:
    onder = (f'<figcaption style="margin-top:10px;font-size:13px;color:#64748b;text-align:center">'
             f'{html.escape(bijschrift)}</figcaption>') if bijschrift else ""
    return (f'<figure class="info-kaart info-kaart-{soort}" style="margin:32px 0;{_FONT}">'
            f'{inhoud}{onder}</figure>')


_BELASTING = re.compile(r"dac7|tax|belasting|btw|vat|omzetgrens|reporting|rapportage", re.I)


def cijfers_html(items: list[dict], body_html: str, language: str, accent: tuple[str, str] = _ACCENTEN[0],
                 title: str = "") -> str | None:
    tekst = _platte_tekst(body_html)
    # De DAC7-grens staat in bijna elk artikel en werd steeds als "kerncijfer"
    # gekozen, ook in een horlogeblog. Alleen tonen als het artikel erover gaat.
    if not _BELASTING.search(title or ""):
        items = [i for i in items or [] if isinstance(i, dict) and not _BELASTING.search(str(i.get("label", "")))]
    goed = [i for i in items or [] if isinstance(i, dict) and _staat_in_tekst(str(i.get("waarde", "")), tekst)
            and 0 < len(str(i.get("label", ""))) <= 70 and len(str(i["waarde"])) <= 14
            and re.search(r"\d", str(i["waarde"]))][:3]
    if len(goed) < 2:
        return None
    tegels = "".join(
        '<div style="flex:1 1 150px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 16px">'
        f'<div style="font-size:28px;font-weight:800;color:{accent[0]};line-height:1.1">{html.escape(str(i["waarde"]))}</div>'
        f'<div style="margin-top:6px;font-size:14px;color:#475569;line-height:1.35">{html.escape(str(i["label"]))}</div></div>'
        for i in goed)
    kop = (f'<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
           f'color:{accent[0]};margin-bottom:12px">{_TEKST[language]["cijfers"]}</div>')
    return _figure(f'<div style="background:{accent[1]};border-radius:18px;padding:20px">'
                   f'{kop}<div style="display:flex;flex-wrap:wrap;gap:12px">{tegels}</div></div>', "cijfers")


def checklist_html(data: dict, language: str, accent: tuple[str, str] = _ACCENTEN[0]) -> str | None:
    punten = [str(p).strip().rstrip(".") for p in (data or {}).get("punten") or [] if 3 < len(str(p).strip()) <= 110][:6]
    if len(punten) < 4:
        return None
    titel = str((data or {}).get("titel") or _TEKST[language]["check"])[:60].rstrip(":").strip()
    titel = titel[:1].upper() + titel[1:]
    regels = "".join(
        '<li style="display:flex;gap:12px;align-items:flex-start;padding:9px 0;border-top:1px solid #f1f5f9">'
        f'<span style="flex:0 0 22px;height:22px;border-radius:6px;border:2px solid {accent[0]};color:{accent[0]};'
        'font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center">&#10003;</span>'
        f'<span style="font-size:15px;color:#0f172a;line-height:1.45">{html.escape(p)}</span></li>'
        for p in punten)
    return _figure(
        '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:20px 22px;'
        'box-shadow:0 1px 3px rgba(15,23,42,.06)">'
        f'<div style="font-size:17px;font-weight:800;color:#0f172a;margin-bottom:6px">{html.escape(titel)}</div>'
        f'<ul style="list-style:none;margin:0;padding:0">{regels}</ul></div>', "checklist")


def voorbeeld_html(data: dict, language: str, accent: tuple[str, str] = _ACCENTEN[0]) -> str | None:
    data = data or {}
    categorie = str(data.get("categorie") or "other")
    artikel = str(data.get("artikel") or "").strip()
    if len(artikel) > 52:
        artikel = artikel[:52].rsplit(" ", 1)[0].rstrip(",;") 
    try:
        prijs = float(str(data.get("prijs")).replace("€", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    kanalen = [(k, v) for k, v in (data.get("kanalen") or {}).items() if k in PLATFORMS and v in STATUS][:4]
    if not artikel or not (1 <= prijs <= 20000) or len(kanalen) < 2 or [v for _, v in kanalen].count("sold") > 1:
        return None
    # Bedrag zoals het in die taal geschreven wordt: €1.250 / €1,250, €12,50 / €12.50.
    if prijs == int(prijs):
        prijs_tekst = f"€{int(prijs):,}".replace(",", "." if language == "nl" else ",")
    else:
        prijs_tekst = f"€{prijs:.2f}".replace(".", "," if language == "nl" else ".")
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;white-space:nowrap;'
        f'background:{_STATUS_KLEUR[v][0]};color:{_STATUS_KLEUR[v][1]};font-size:12.5px;font-weight:600">'
        f'{html.escape(k)} · {_STATUS_TEKST[language][v]}</span>' for k, v in kanalen)
    punt = '<span style="width:10px;height:10px;border-radius:50%;background:{}"></span>'
    venster = (
        '<div style="border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;background:#f8fafc;'
        'box-shadow:0 8px 24px rgba(15,23,42,.08)">'
        '<div style="display:flex;align-items:center;gap:6px;padding:10px 14px;background:#fff;border-bottom:1px solid #e2e8f0">'
        + punt.format("#f87171") + punt.format("#fbbf24") + punt.format("#34d399")
        + '<span style="margin-left:10px;font-size:13px;font-weight:700;color:#0f172a">Omnivaleur</span>'
        f'<span style="margin-left:auto;font-size:12px;color:#64748b">{_TEKST[language]["voorbeeld"]}</span></div>'
        '<div style="padding:18px"><div style="display:flex;flex-wrap:wrap;gap:14px;align-items:center;background:#fff;'
        'border:1px solid #e2e8f0;border-radius:12px;padding:14px">'
        f'<div style="flex:0 0 56px;height:56px;border-radius:10px;background:{accent[1]};'
        'display:flex;align-items:center;justify-content:center">'
        f'<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="{accent[0]}" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICOON.get(categorie, _ICOON["other"])}</svg></div>'
        '<div style="flex:1 1 200px;min-width:0">'
        f'<div style="font-size:15px;font-weight:700;color:#0f172a">{html.escape(artikel)}</div>'
        f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">{chips}</div></div>'
        f'<div style="margin-left:auto;font-size:18px;font-weight:800;color:#0f172a;white-space:nowrap">{prijs_tekst}</div>'
        '</div></div></div>')
    return _figure(venster, "voorbeeld", _TEKST[language]["bijschrift"])


def build_cards(title: str, body_html: str, language: str = "en", data: dict | None = None) -> list[str]:
    data = data if data is not None else extract(title, body_html, language)
    if not data:
        return []
    accent = _accent(title)
    kaarten = [
        cijfers_html(data.get("cijfers") or [], body_html, language, accent, title),
        voorbeeld_html(data.get("voorbeeld") or {}, language, accent),
        checklist_html(data.get("checklist") or {}, language, accent),
    ]
    return [k for k in kaarten if k]


_KAART = re.compile(r'\n?<figure class="info-kaart.*?</figure>', re.S)


def strip_cards(body_html: str) -> str:
    """Kaarten eruit, bv. vóór het vertalen: de Nederlandse versie krijgt eigen
    kaarten uit de Nederlandse tekst, niet een vertaalde kopie van de Engelse."""
    return _KAART.sub("", body_html or "")


def inject_cards(body_html: str, title: str, language: str = "en") -> str:
    """Idempotent: een artikel dat al kaarten heeft, blijft ongemoeid."""
    if MARKER in (body_html or ""):
        return body_html
    kaarten = build_cards(title, body_html, language)
    return spread_figures(body_html, kaarten) if kaarten else body_html
