"""De Etsy-pagina is wat Etsy bij de API-aanvraag leest (API-voorwaarden §1, §3).
Valt een van deze zinnen weg, dan is de aanvraag niet meer compliant."""
from pathlib import Path

import pytest

FRONTEND = Path(__file__).parent.parent / "frontend"
TM_EN = ("The term &lsquo;Etsy&rsquo; is a trademark of Etsy, Inc. This application uses the Etsy API "
         "but is not endorsed or certified by Etsy, Inc.")


@pytest.mark.parametrize("bestand", ["etsy.html", "etsy.nl.html"])
def test_etsy_pagina_heeft_verplichte_stukken(bestand):
    html = (FRONTEND / bestand).read_text(encoding="utf-8")
    assert TM_EN in html                      # verplichte trademarktekst, letterlijk Engels
    assert "mailto:info@omnivaleur.com" in html  # bewaakt supportadres
    assert "Etsy, Inc." in html and "Revaleur" in html  # disclaimer van de ontwikkelaar
    assert "/terms" in html and "/privacy" in html
    assert "scrap" in html.lower()            # belofte: geen scrapen


@pytest.mark.parametrize("bestand", ["etsy.html", "etsy.nl.html"])
def test_etsy_pagina_belooft_geen_prijs_of_datum(bestand):
    html = (FRONTEND / bestand).read_text(encoding="utf-8").lower()
    for woord in ("ultra", "\u20ac", "per month", "per maand", "coming soon", "binnenkort"):
        assert woord not in html
