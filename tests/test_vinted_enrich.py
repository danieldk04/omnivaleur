"""Tests voor het alsnog ophalen van Vinted-advertentieteksten.

Achtergrond: Toon (dejuistetoon) hield na het importeren 244 artikelen zonder
omschrijving over, en zonder omschrijving weigert het dashboard te publiceren.
De tekst stond wél gewoon op zijn Vinted-advertenties.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.vinted_enrich import tekst_uit_pagina, MAX_TEKST


def test_langste_beschrijving_wint():
    """Vinted zet meerdere "description"-velden in de pagina; de eerste is vaak
    een lege SEO-stomp. Precies daarop gaf de oude code op."""
    html = ('{"description":""}'
            '<div>{"description":"Traditioneel geweven Kelim kleed."}</div>'
            '{"description":"kort"}')
    assert tekst_uit_pagina(html) == "Traditioneel geweven Kelim kleed."


def test_lege_stomp_alleen_geeft_niets():
    assert tekst_uit_pagina('{"description":""}') == ""


def test_ontsnapte_tekens_worden_gewone_tekst():
    html = r'{"description":"Regel een\nRegel twee — met streepje"}'
    uit = tekst_uit_pagina(html)
    assert "Regel een" in uit and "Regel twee" in uit
    assert "\\n" not in uit


def test_og_description_als_tweede_keus():
    html = '<meta property="og:description" content="Mooie jas in de thema hond">'
    assert tekst_uit_pagina(html) == "Mooie jas in de thema hond"


def test_json_velden_gaan_voor_op_og():
    html = ('<meta name="description" content="korte teaser">'
            '{"description":"de volledige advertentietekst met veel meer inhoud"}')
    assert tekst_uit_pagina(html).startswith("de volledige")


def test_html_entiteiten_uit_og_worden_ontcijferd():
    html = '<meta property="og:description" content="Jas &amp; broek">'
    assert tekst_uit_pagina(html) == "Jas & broek"


def test_lege_en_rare_invoer_valt_niet_om():
    assert tekst_uit_pagina("") == ""
    assert tekst_uit_pagina(None) == ""
    assert tekst_uit_pagina("<html>geen json, geen meta</html>") == ""


def test_noodrem_op_lengte():
    html = '{"description":"' + ("a" * (MAX_TEKST + 500)) + '"}'
    assert len(tekst_uit_pagina(html)) == MAX_TEKST


def test_echte_vinted_pagina():
    """De voor-en-na-proef op een echte pagina.

    Advertentie 8832144106 (Toon) stond bij ons zonder tekst en heeft er op
    Vinted wel een. Slaat over als er geen internet is — dan zegt deze test
    niets, en dat is beter dan een groen vinkje dat nergens op slaat.
    """
    import httpx
    try:
        r = httpx.get("https://www.vinted.nl/items/8832144106", timeout=20,
                      follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"})
    except Exception:  # noqa: BLE001
        import pytest
        pytest.skip("geen verbinding met Vinted")
    if r.status_code == 429:
        import pytest
        pytest.skip("Vinted knijpt nu af — meting zou niets zeggen")
    assert r.status_code == 200
    tekst = tekst_uit_pagina(r.text)
    assert len(tekst) > 50, f"geen tekst gevonden, wel {len(r.text)} bytes pagina"
    assert "Kelim" in tekst or "kleed" in tekst.lower()
