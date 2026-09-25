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


def _platte_tekst(body_html: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body_html or ""))).lower()


def _staat_in_tekst(waarde: str, tekst: str) -> bool:
    w = re.sub(r"\s+", " ", (waarde or "").strip().lower())
    return bool(w) and w in tekst


def _prompt(title: str, body_html: str, language: str) -> str:
    taal = "Dutch" if language == "nl" else "English"
    tekst = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body_html))[:14000]
    return f"""You design visual summary cards for a blog article. Article title: "{title}".

Return ONLY JSON, no markdown fences, in {taal}, in exactly this shape:
{{"cijfers": [{{"waarde": "...", "label": "..."}}],
  "checklist": {{"titel": "...", "punten": ["...", "..."]}},
  "voorbeeld": {{"artikel": "...", "prijs": 45, "kanalen": {{"Vinted": "live"}}}}}}

Rules:
- cijfers: 0 to 3 items. "waarde" MUST be copied character for character from the article text below (e.g. "€6,95", "14 days", "30%"). If the article has no striking numbers, return an empty list. Never invent or round a number. "label": max 6 words saying what the number is.
- checklist: 4 to 6 short, concrete action points a reader can tick off, each max 60 characters, taken from the article's advice. "titel": max 6 words.
- voorbeeld: one realistic second-hand item that fits this article's topic (e.g. a vintage denim jacket for a clothing article), a plausible euro price as a number, and 2 to 4 channels from exactly this list: {", ".join(PLATFORMS)}, each with a status from: live, publishing, sold, queued. At most one "sold". If the article is about a platform, include that platform.

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


def cijfers_html(items: list[dict], body_html: str, language: str) -> str | None:
    tekst = _platte_tekst(body_html)
    goed = [i for i in items or [] if isinstance(i, dict) and _staat_in_tekst(str(i.get("waarde", "")), tekst)
            and 0 < len(str(i.get("label", ""))) <= 60 and len(str(i["waarde"])) <= 14][:3]
    if len(goed) < 2:
        return None
    tegels = "".join(
        '<div style="flex:1 1 150px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 16px">'
        f'<div style="font-size:30px;font-weight:800;color:#2563eb;line-height:1.1">{html.escape(str(i["waarde"]))}</div>'
        f'<div style="margin-top:6px;font-size:14px;color:#475569;line-height:1.35">{html.escape(str(i["label"]))}</div></div>'
        for i in goed)
    kop = (f'<div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
           f'color:#047857;margin-bottom:12px">{_TEKST[language]["cijfers"]}</div>')
    return _figure(f'<div style="background:linear-gradient(135deg,#eff6ff,#ecfdf5);border-radius:18px;padding:20px">'
                   f'{kop}<div style="display:flex;flex-wrap:wrap;gap:12px">{tegels}</div></div>', "cijfers")


def checklist_html(data: dict, language: str) -> str | None:
    punten = [str(p).strip() for p in (data or {}).get("punten") or [] if 3 < len(str(p).strip()) <= 70][:6]
    if len(punten) < 4:
        return None
    titel = str((data or {}).get("titel") or _TEKST[language]["check"])[:60]
    regels = "".join(
        '<li style="display:flex;gap:12px;align-items:flex-start;padding:9px 0;border-top:1px solid #f1f5f9">'
        '<span style="flex:0 0 22px;height:22px;border-radius:50%;background:#34d399;color:#fff;'
        'font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center">&#10003;</span>'
        f'<span style="font-size:15px;color:#0f172a;line-height:1.45">{html.escape(p)}</span></li>'
        for p in punten)
    return _figure(
        '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:20px 22px;'
        'box-shadow:0 1px 3px rgba(15,23,42,.06)">'
        f'<div style="font-size:17px;font-weight:800;color:#0f172a;margin-bottom:6px">{html.escape(titel)}</div>'
        f'<ul style="list-style:none;margin:0;padding:0">{regels}</ul></div>', "checklist")


def voorbeeld_html(data: dict, language: str) -> str | None:
    data = data or {}
    artikel = str(data.get("artikel") or "").strip()[:60]
    try:
        prijs = float(str(data.get("prijs")).replace("€", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    kanalen = [(k, v) for k, v in (data.get("kanalen") or {}).items() if k in PLATFORMS and v in STATUS][:4]
    if not artikel or not (1 <= prijs <= 20000) or len(kanalen) < 2 or [v for _, v in kanalen].count("sold") > 1:
        return None
    prijs_tekst = f"€{prijs:,.0f}".replace(",", ".") if prijs >= 100 else f"€{prijs:.2f}".replace(".", ",").replace(",00", "")
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;'
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
        '<div style="padding:18px"><div style="display:flex;gap:14px;align-items:center;background:#fff;'
        'border:1px solid #e2e8f0;border-radius:12px;padding:14px">'
        '<div style="flex:0 0 56px;height:56px;border-radius:10px;background:linear-gradient(135deg,#2563eb,#34d399);'
        f'color:#fff;font-weight:800;font-size:22px;display:flex;align-items:center;justify-content:center">'
        f'{html.escape(artikel[:1].upper())}</div>'
        '<div style="flex:1;min-width:0">'
        f'<div style="font-size:15px;font-weight:700;color:#0f172a">{html.escape(artikel)}</div>'
        f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px">{chips}</div></div>'
        f'<div style="font-size:18px;font-weight:800;color:#0f172a;white-space:nowrap">{prijs_tekst}</div>'
        '</div></div></div>')
    return _figure(venster, "voorbeeld", _TEKST[language]["bijschrift"])


def build_cards(title: str, body_html: str, language: str = "en", data: dict | None = None) -> list[str]:
    data = data if data is not None else extract(title, body_html, language)
    if not data:
        return []
    kaarten = [
        cijfers_html(data.get("cijfers") or [], body_html, language),
        voorbeeld_html(data.get("voorbeeld") or {}, language),
        checklist_html(data.get("checklist") or {}, language),
    ]
    return [k for k in kaarten if k]


def inject_cards(body_html: str, title: str, language: str = "en") -> str:
    """Idempotent: een artikel dat al kaarten heeft, blijft ongemoeid."""
    if MARKER in (body_html or ""):
        return body_html
    kaarten = build_cards(title, body_html, language)
    return spread_figures(body_html, kaarten) if kaarten else body_html
