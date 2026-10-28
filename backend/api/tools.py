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
from backend.tools_data import GEWIJZIGD, GROEP_NAAM, GROEPEN, HUB, SITE, TOOLS, tool_pad, vind_tool

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
            "pad": tool_pad(t, taal), "gated": t["gated"], "groep": t["groep"], "nieuw": t["nieuw"]}


MAANDEN = {"nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
                  "oktober", "november", "december"],
           "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"]}


def _datum(taal: str) -> str:
    j, m, d = (int(x) for x in GEWIJZIGD.split("-"))
    return f"{d} {MAANDEN[taal][m - 1]} {j}"


def _kop_blok(tool: dict, taal: str) -> str:
    """Antwoord vooraan (voor lezers en voor AI-samenvattingen) en drie vertrouwensregels."""
    nl = taal == "nl"
    tweede = ("Met e-mailadres" if nl else "With email") if tool["gated"] else ("Geen inlog" if nl else "No login")
    chips = ["Gratis" if nl else "Free", tweede, ("Bijgewerkt " if nl else "Updated ") + _datum(taal)]
    kop = "In het kort" if nl else "In short"
    return (f'<p class="kr-kort"><strong>{kop}:</strong> {html.escape(tool["antwoord"][taal])}</p>'
            f'<p class="kr-chips">{"".join(f"<span>{html.escape(c)}</span>" for c in chips)}</p>')


def _render(taal: str, *, tool: dict | None) -> HTMLResponse:
    nl = taal == "nl"
    env = templates.env
    hub = HUB[taal]
    ctx_basis = {"taal": taal, "nl": nl, "merk_links": MERK_LINKS, "hub_pad": hub["pad"], "css_v": _versie("tools.css")}
    if tool is None:
        en_pad, nl_pad = HUB["en"]["pad"], HUB["nl"]["pad"]
        kaarten = [_kaart(t, taal) for t in TOOLS]
        groepen = [{"naam": GROEP_NAAM[taal][g], "kaarten": [k for k in kaarten if k["groep"] == g]} for g in GROEPEN]
        body = env.get_template("tools/_hub.html").render({**ctx_basis, "kaarten": kaarten, "groepen": groepen, "h1": hub["h1"]})
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
        body = body.replace("</h1>", "</h1>\n" + _kop_blok(tool, taal), 1)
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
        "js_v": _versie(*[s for s in scripts]), "ux_v": _versie("tools/ux.js"),
        "toolkey": tool["key"] if tool else "",
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


# ── "Mail mij dit resultaat" ──────────────────────────────────────────────
# Een rekentool blijft vrij te gebruiken. Wie zijn uitkomst wil bewaren, laat
# hem naar zichzelf mailen. Alleen als iemand het aanvinkt komt het adres ook
# in tool_aanmeldingen; anders bewaren we niets.
MAX_MAILS_PER_UUR = 6
MAX_MAILS_PER_ADRES_PER_DAG = 3
_mail_per_ip: dict[str, list[float]] = defaultdict(list)
_mail_per_adres: dict[str, list[float]] = defaultdict(list)
STUUR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class ResultaatMail(BaseModel):
    email: str
    taal: str = "nl"
    bron: str = ""
    tekst: str = ""
    link: str = ""
    tips: bool = False
    website: str = ""  # lokveld


def _te_vaak_lijst(sleutel: str, lijst: dict[str, list[float]], venster: float, max_: int) -> bool:
    nu = time.time()
    lijst[sleutel] = [t for t in lijst[sleutel] if nu - t < venster]
    if len(lijst[sleutel]) >= max_:
        return True
    lijst[sleutel].append(nu)
    return False


def _mailtekst(taal: str, naam: str, tekst: str, link: str) -> tuple[str, str]:
    if taal == "nl":
        onderwerp = f"Je resultaat uit de {naam}"
        body = (f"Hier is je resultaat uit de {naam} van Omnivaleur.\n\n{tekst}\n\n"
                + (f"Opnieuw openen met je invoer: {link}\n\n" if link else "")
                + "Dit is een rekenhulp en geen advies. Tarieven en regels kunnen veranderen.\n\n"
                "Omnivaleur zet je artikelen in één keer op Marktplaats, 2dehands, Vinted en eBay. "
                f"7 dagen gratis proberen: {SITE}/register\n\n"
                "Je krijgt deze mail eenmalig, omdat je hem zelf op de website aanvroeg.")
    else:
        onderwerp = f"Your result from the {naam}"
        body = (f"Here is your result from the Omnivaleur {naam}.\n\n{tekst}\n\n"
                + (f"Open it again with your input: {link}\n\n" if link else "")
                + "This is a calculation aid, not advice. Fees and rules can change.\n\n"
                "Omnivaleur puts your items on Marktplaats, 2dehands, Vinted and eBay in one go. "
                f"Try it free for 7 days: {SITE}/register\n\n"
                "You get this email once, because you asked for it on the website.")
    return onderwerp, body


@router.post("/api/tools/mail-resultaat")
def mail_resultaat(body: ResultaatMail, request: Request):
    taal = "nl" if body.taal == "nl" else "en"
    email = body.email.strip().lower()
    if body.website:  # bot
        return {"ok": True}
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="email")
    tool = next((t for t in TOOLS if t["key"] == body.bron and not t["gated"]), None)
    tekst = STUUR_RE.sub("", body.tekst).strip()[:4000]
    if not tool or not tekst:
        raise HTTPException(status_code=422, detail="resultaat")
    link = body.link.strip()
    if not link.startswith(SITE + "/") or len(link) > 600 or any(c in link for c in " \n\r"):
        link = ""
    ip = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "-"))
    if (_te_vaak_lijst(ip, _mail_per_ip, 3600, MAX_MAILS_PER_UUR)
            or _te_vaak_lijst(email, _mail_per_adres, 86400, MAX_MAILS_PER_ADRES_PER_DAG)):
        raise HTTPException(status_code=429, detail="te vaak")
    onderwerp, tekst_uit = _mailtekst(taal, tool[taal]["naam"], tekst, link)
    if not send_email(onderwerp, tekst_uit, to=email):
        raise HTTPException(status_code=503, detail="mail")
    if body.tips:
        try:
            get_db().table("tool_aanmeldingen").upsert(
                {"email": email, "taal": taal, "bron": f"mail-{tool['key']}"[:40], "toestemming": True},
                on_conflict="email").execute()
        except Exception as e:  # noqa: BLE001 — de mail is al weg; het adres gaat anders naar de eigenaar
            logger.error("tool_aanmeldingen: opslaan mislukt (%s)", e)
            send_email("Tool-aanmelding niet opgeslagen",
                       f"Opslaan mislukte ({e}). Adres: {email}, taal {taal}, bron mail-{tool['key']}, toestemming gegeven.")
    return {"ok": True}
