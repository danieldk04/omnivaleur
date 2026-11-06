"""Eén kopregel en één voettekst voor de hele openbare site.

De losse pagina's (home, /nl, marketplaces, privacy, terms, ai-info, mp-video,
404) hadden elk een eigen, met de hand gekopieerde nav en footer. Die groeiden
uit elkaar: de ene had een taalknop, de andere niet, /ai-info had helemaal geen
menu. Nu staat in die bestanden alleen nog <!--site-nav--> en <!--site-footer-->
en vult de server ze bij het uitserveren in uit dezelfde Jinja-stukken die de
blog gebruikt (frontend/templates/_nav.html en _footer.html).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi.responses import HTMLResponse

from backend.api.content import MERK_LINKS, templates

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
NAV = "<!--site-nav-->"
FOOTER = "<!--site-footer-->"


@lru_cache(maxsize=64)
def _render(bestand: str, taal: str, pad: str, wissel: str, mtime: float) -> str:
    html = (FRONTEND / bestand).read_text(encoding="utf-8")
    env = templates.env
    ctx = {"taal": taal, "pad": pad, "wissel": wissel, "merk_links": MERK_LINKS}
    stijl = env.get_template("_site_chrome_style.html").render()
    html = html.replace("</head>", stijl + "\n</head>", 1)
    html = html.replace(NAV, env.get_template("_nav.html").render(ctx), 1)
    html = html.replace(FOOTER, env.get_template("_footer.html").render(ctx), 1)
    return html


def met_site_chrome(bestand: str, taal: str = "en", pad: str = "", status_code: int = 200,
                    wissel: str = "") -> HTMLResponse:
    """Serveer een statische pagina met de gedeelde kopregel en voettekst.
    wissel: adres van dezelfde pagina in de andere taal, voor de EN/NL-knop."""
    mtime = (FRONTEND / bestand).stat().st_mtime
    return HTMLResponse(_render(bestand, taal, pad, wissel, mtime), status_code=status_code)
