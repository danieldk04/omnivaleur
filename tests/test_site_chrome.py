"""Eén kopregel en één voettekst op de hele openbare site.

Aanleiding, 24-09-2026: /ai-info had geen menu, en home, /nl, marketplaces,
privacy, terms en de blog hadden elk een eigen, net iets andere kopie van nav en
footer (taalknop hier wel, daar niet; eBay ontbrak in de footer). Nu staat er in
de bestanden alleen een plekhouder en vult backend/site_chrome.py die in uit
frontend/templates/_nav.html en _footer.html, dezelfde die de blog gebruikt.
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

from backend.site_chrome import met_site_chrome  # noqa: E402

PAGINAS = [
    ("index.html", "en"), ("nl.html", "nl"), ("marketplaces.html", "en"),
    ("privacy.html", "en"), ("terms.html", "en"), ("ai-info.html", "en"),
    ("mp-video.html", "nl"), ("not-found.html", "en"),
]


@pytest.mark.parametrize("bestand,taal", PAGINAS)
def test_bestand_heeft_geen_eigen_kopregel_of_voettekst(bestand, taal):
    bron = (REPO / "frontend" / bestand).read_text(encoding="utf-8")
    assert "<!--site-nav-->" in bron and "<!--site-footer-->" in bron
    assert not re.search(r"<nav[ >]", bron), f"{bestand} heeft weer een eigen <nav>"
    assert "<footer" not in bron, f"{bestand} heeft weer een eigen <footer>"


@pytest.mark.parametrize("bestand,taal", PAGINAS)
def test_pagina_krijgt_precies_een_gedeelde_kopregel_en_voettekst(bestand, taal):
    html = met_site_chrome(bestand, taal).body.decode("utf-8")
    assert html.count('<nav class="site-nav">') == 1
    assert html.count('<footer class="site-footer">') == 1
    assert html.count('id="site-chrome"') == 1
    assert "<!--site-" not in html
    assert ('Inloggen' in html) == (taal == "nl")
    for pad in ("/marketplaces", "/ai-info", "/privacy", "/terms", "/register", "/login"):
        assert f'href="{pad}"' in html


def test_blog_gebruikt_dezelfde_stukken():
    for sjabloon in ("content_page.html", "blog_index.html"):
        bron = (REPO / "frontend" / "templates" / sjabloon).read_text(encoding="utf-8")
        assert '{% include "_nav.html" %}' in bron
        assert '{% include "_footer.html" %}' in bron
        assert '{% include "_site_chrome_style.html" %}' in bron
