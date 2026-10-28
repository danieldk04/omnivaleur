"""Openbare tools-hub: pagina's en de aanmelding voor downloads.

Pagina's: /tools en /nl/tools (hub), /tools/<slug> en /nl/tools/<slug> (tool).
Alles komt uit backend/tools_data.py. De tekst van elke tool staat in
frontend/templates/tools/<key>.<taal>.html; de veelgestelde vragen die daarin
staan (<details><summary>) worden ook als FAQPage-schema uitgevoerd, zodat de
zichtbare tekst en het schema nooit uit elkaar lopen.

Aanmelding: POST /api/tools/aanmelden schrijft naar de tabel tool_aanmeldingen
(zie schema.sql). Lukt dat niet, dan gaat het adres per mail naar Daniel in
plaats van verloren, en krijgt de bezoeker zijn download toch.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

from backend.api.content import MERK_LINKS, templates
from backend.config import settings
from backend.database import get_db
from backend.services.email import send_email
from backend.tools_data import HUB, SITE, GEWIJZIGD, TOOLS, tool_pad, vind_tool

logger = logging.getLogger(__name__)
router = APIRouter()

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"
DOWNLOADS = Path(__file__).resolve().parent.parent / "downloads"
FAQ_RE = re.compile(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _versie(*delen: str) -> str:
    """Wijzigt een bestand, dan wijzigt ?v= mee (Cloudflare houdt assets vast)."""
    t = 0.0
    for d in delen:
        p = FRONTEND / "assets" / d
        if p.exists():
            t = max(t, p.stat().st_mtime)
    return str(int(t))


def _platte_tekst(s: str) -> str:
    return html.unescape(TAG_RE.sub("", s)).replace("\xa0", " ").strip()


def _faq_schema(body: str) -> dict | None:
    vragen = FAQ_RE.findall(body)
    if not vragen:
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": _platte_tekst(q),
         "acceptedAnswer": {"@type": "Answer", "text": _platte_tekst(a)}} for q, a in vragen]}


def _alternatieven(en_pad: str, nl_pad: str) -> list[tuple[str, str]]:
    return [("en", SITE + en_pad), ("nl", SITE + nl_pad)]


def _kaart(t: dict, taal: str) -> dict:
    return {"key": t["key"], "icon": t["icon"], "naam": t[taal]["naam"], "kort": t[taal]["kort"],
            "pad": tool_pad(t, taal), "gated": t["gated"]}


def _render(taal: str, *, tool: dict | None) -> HTMLResponse:
    nl = taal == "nl"
    env = templates.env
    hub = HUB[taal]
    ctx_basis = {"taal": taal, "nl": nl, "merk_links": MERK_LINKS, "hub_pad": hub["pad"], "css_v": _versie("tools.css")}
    if tool is None:
        en_pad, nl_pad = HUB["en"]["pad"], HUB["nl"]["pad"]
        kaarten = [_kaart(t, taal) for t in TOOLS]
        body = env.get_template("tools/_hub.html").render({**ctx_basis, "kaarten": kaarten, "h1": hub["h1"]})
        titel, meta, pad = hub["titel"], hub["meta"], hub["pad"]
        naam, scripts, andere, gedeeld_js = hub["h1"], [], [], ""
        grafiek = [
            {"@type": "CollectionPage", "name": hub["h1"], "url": SITE + pad, "inLanguage": taal,
             "dateModified": GEWIJZIGD, "description": meta,
             "mainEntity": {"@type": "ItemList", "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": k["naam"], "url": SITE + k["pad"]}
                 for i, k in enumerate(kaarten)]}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Omnivaleur", "item": SITE + ("/nl" if nl else "/")},
                {"@type": "ListItem", "position": 2, "name": "Gratis tools" if nl else "Free tools", "item": SITE + pad}]},
        ]
    else:
        tekst = tool[taal]
        en_pad, nl_pad = tool_pad(tool, "en"), tool_pad(tool, "nl")
        pad, naam = tool_pad(tool, taal), tekst["naam"]
        titel, meta = tekst["titel"], tekst["meta"]
        body = env.get_template(f"tools/{tool['key']}.{taal}.html").render(ctx_basis)
        scripts = tool["scripts"]
        andere = [_kaart(t, taal) for t in TOOLS if t["key"] != tool["key"]]
        grafiek = [
            {"@type": "WebPage" if tool["gated"] else "WebApplication", "name": naam, "url": SITE + pad,
             "inLanguage": taal, "dateModified": GEWIJZIGD, "description": meta,
             **({} if tool["gated"] else {"applicationCategory": "BusinessApplication", "operatingSystem": "Web",
                                          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}),
             "publisher": {"@type": "Organization", "name": "Omnivaleur", "url": SITE + "/", "logo": SITE + "/logo.png"}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Omnivaleur", "item": SITE + ("/nl" if nl else "/")},
                {"@type": "ListItem", "position": 2, "name": "Gratis tools" if nl else "Free tools", "item": SITE + hub["pad"]},
                {"@type": "ListItem", "position": 3, "name": naam, "item": SITE + pad}]},
        ]
        faq = _faq_schema(body)
        if faq:
            grafiek.append(faq)
    html_uit = env.get_template("tools/_pagina.html").render({
        **ctx_basis, "tool": tool, "titel": titel, "meta": meta, "naam": naam, "body": body,
        "canonical": SITE + pad, "alternatieven": _alternatieven(en_pad, nl_pad), "x_default": SITE + en_pad,
        "json_ld": json.dumps({"@context": "https://schema.org", "@graph": grafiek}, ensure_ascii=False),
        "pad": pad, "wissel": (nl_pad if not nl else en_pad), "scripts": scripts, "andere": andere,
        "js_v": _versie(*[s for s in scripts]),
    })
    return HTMLResponse(html_uit)


@router.get("/tools", include_in_schema=False)
def hub_en():
    return _render("en", tool=None)


@router.get("/nl/tools", include_in_schema=False)
def hub_nl():
    return _render("nl", tool=None)


@router.get("/tools/{slug}", include_in_schema=False)
def tool_en(slug: str):
    tool = vind_tool("en", slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Page not found")
    return _render("en", tool=tool)


@router.get("/nl/tools/{slug}", include_in_schema=False)
def tool_nl(slug: str):
    tool = vind_tool("nl", slug)
    if not tool:
        raise HTTPException(status_code=404, detail="Page not found")
    return _render("nl", tool=tool)


# De eerste kostenrekenaar stond een paar uur op deze twee adressen (28-10-2026).
@router.get("/fee-calculator", include_in_schema=False)
def oud_en():
    return RedirectResponse("/tools/fee-calculator", status_code=301)


@router.get("/nl/kostenrekenaar", include_in_schema=False)
def oud_nl():
    return RedirectResponse("/nl/tools/kostenrekenaar", status_code=301)


# ── Aanmelding voor downloads ─────────────────────────────────────────────
DOWNLOAD_BESTANDEN = {
    "voorraad-winst-nl": "voorraad-winst-spreadsheet-nl.xlsx",
    "voorraad-winst-en": "inventory-profit-spreadsheet-en.xlsx",
}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,24}$")
_per_ip: dict[str, list[float]] = defaultdict(list)
MAX_PER_UUR = 8


class Aanmelding(BaseModel):
    email: str
    taal: str = "nl"
    bron: str = "voorraadsheet"
    toestemming: bool = False
    website: str = ""  # lokveld: een mens laat dit leeg


def _token(email: str, naam: str) -> str:
    sleutel = (settings.secret_key or "").encode()
    return hmac.new(sleutel, f"{email.lower()}|{naam}".encode(), hashlib.sha256).hexdigest()[:32]


def _te_vaak(ip: str) -> bool:
    nu = time.time()
    _per_ip[ip] = [t for t in _per_ip[ip] if nu - t < 3600]
    if len(_per_ip[ip]) >= MAX_PER_UUR:
        return True
    _per_ip[ip].append(nu)
    return False


def _download_url(email: str, taal: str) -> str:
    naam = "voorraad-winst-nl" if taal == "nl" else "voorraad-winst-en"
    return f"/api/tools/download/{naam}?e={email}&t={_token(email, naam)}"


@router.post("/api/tools/aanmelden")
def aanmelden(body: Aanmelding, request: Request):
    taal = "nl" if body.taal == "nl" else "en"
    email = body.email.strip().lower()
    if body.website:  # bot: doe alsof het lukte, bewaar niets
        return {"ok": True, "download": "/tools"}
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="email")
    if not body.toestemming:
        raise HTTPException(status_code=422, detail="toestemming")
    ip = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "-"))
    if _te_vaak(ip):
        raise HTTPException(status_code=429, detail="te vaak")
    rij = {"email": email, "taal": taal, "bron": body.bron[:40], "toestemming": True}
    try:
        get_db().table("tool_aanmeldingen").upsert(rij, on_conflict="email").execute()
    except Exception as e:  # noqa: BLE001 — het adres mag niet verloren gaan
        logger.error("tool_aanmeldingen: opslaan mislukt (%s), adres gaat per mail naar de eigenaar", e)
        send_email("Tool-aanmelding niet opgeslagen",
                   f"Opslaan in tool_aanmeldingen mislukte ({e}). Adres: {email}, taal {taal}, bron {body.bron}, "
                   "toestemming gegeven. Staat de tabel er al? Zie schema.sql.")
    return {"ok": True, "download": _download_url(email, taal)}


@router.get("/api/tools/download/{naam}", include_in_schema=False)
def download(naam: str, e: str = "", t: str = ""):
    bestand = DOWNLOAD_BESTANDEN.get(naam)
    if not bestand or not e or not hmac.compare_digest(t, _token(e, naam)):
        raise HTTPException(status_code=404, detail="Page not found")
    pad = DOWNLOADS / bestand
    if not pad.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(pad, filename=bestand,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
