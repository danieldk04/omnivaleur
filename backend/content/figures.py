"""
Gedeelde plaatsingslogica voor beeld in artikelen.

Zowel de app-screenshots (dashboard_images.py), de platform-screenshots
(web_images.py) als de concurrent-screenshots (generator.py) moeten hetzelfde
doen: figuren gelijkmatig over de H2-secties verdelen, de eerste sectie
overslaan, en bij een herhaalde run niets dubbel invoegen. Die logica stond
drie keer bijna-identiek gekopieerd; hier staat hij één keer.

Werkt bewust met string-splicing op de originele HTML in plaats van met een
HTML-parser: herserialiseren van de body heeft in dit project al eens img-src'en
beschadigd (zie infographics.py). Elke byte die we niet zelf toevoegen blijft
gegarandeerd zoals hij was.
"""
from __future__ import annotations

import re


def h2_positions(body_html: str) -> list[int]:
    return [m.start() for m in re.finditer(r"<h2", body_html, re.I)]


def spread_figures(body_html: str, figures: list[str]) -> str:
    """
    Verdeelt `figures` gelijkmatig over de H2-secties. De eerste H2 wordt
    overgeslagen — een artikel hoort niet direct onder de intro op een beeld te
    openen. Zonder bruikbare sectiestructuur komt het eerste figuur bovenaan en
    de rest vervalt (liever één beeld op de goede plek dan vijf op een hoop).
    """
    if not figures:
        return body_html

    usable = h2_positions(body_html)[1:]
    if not usable:
        return figures[0] + body_html

    figures = figures[: len(usable)]
    step = max(len(usable) // max(len(figures), 1), 1)
    slots = usable[::step][: len(figures)]

    # Van achteren naar voren invoegen, zodat eerder bepaalde offsets geldig
    # blijven terwijl de string groeit.
    for pos, fig in sorted(zip(slots, figures), key=lambda pair: pair[0], reverse=True):
        body_html = body_html[:pos] + fig + body_html[pos:]
    return body_html


def _figure_re(needle: str) -> re.Pattern:
    escaped = re.escape(needle)
    return re.compile(
        rf"<figure\b[^>]*>(?:(?!</figure>).)*?{escaped}(?:(?!</figure>).)*?</figure>",
        re.DOTALL,
    )


def strip_figures(body_html: str, needle: str) -> str:
    """
    Haalt eerder ingevoegde <figure>-blokken weg waarvan de inhoud `needle` bevat
    (bv. "/assets/platforms/" of "/assets/dashboard/"). Nodig bij een backfill:
    verouderde of irrelevante beelden moeten eruit vóór de nieuwe erin, anders
    stapelen ze op.
    """
    return _figure_re(needle).sub("", body_html)


def contains_figures(body_html: str, needle: str) -> bool:
    return bool(_figure_re(needle).search(body_html))
