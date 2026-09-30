"""Eén kleurenlijst voor alle kanalen: keuzemenu, server en Marktplaats/2dehands.

De Vinted-kant staat in tests/kleurenlijst-vinted-test.js.
"""
import re
from pathlib import Path

import pytest

from backend.services.kleur import KLEUREN, canonieke_kleur, normaliseer_kleur

WORTEL = Path(__file__).resolve().parent.parent


def test_menu_in_het_dashboard_is_dezelfde_lijst():
    html = (WORTEL / "frontend/app.html").read_text()
    blok = re.search(r'<select id="f-color">(.*?)</select>', html, re.S).group(1)
    opties = re.findall(r'<option value="([^"]*)">', blok)
    assert opties == [""] + [en for en, _, _ in KLEUREN]


@pytest.mark.parametrize("en,nl,code", KLEUREN)
def test_elke_menukleur_blijft_zichzelf_en_geeft_marktplaats_een_kleur(en, nl, code):
    assert canonieke_kleur(en) == en
    assert canonieke_kleur(nl) == en          # de Nederlandse naam ook
    assert normaliseer_kleur(en), f"{en} geeft Marktplaats/2dehands geen kleur"


@pytest.mark.parametrize("geschreven,verwacht", [
    ("grijze", "Grey"), ("Rode", "Red"), ("zwarte", "Black"), ("gray", "Grey"),
    ("dark blue", "Navy"), ("lichtblauw", "Light blue"), ("zilveren", "Silver"),
    ("Turkoois", "Turquoise"), ("olijf", "Khaki"), ("divers", "Various"),
    ("beige, bruin", "Beige, Brown"), ("blue/white", "Blue, White"),
    ("Blauw en wit", "Blue, White"), ("  GREY ", "Grey"), ("Crème", "Cream"),
])
def test_geschreven_kleuren_komen_op_de_lijst(geschreven, verwacht):
    assert canonieke_kleur(geschreven) == verwacht


@pytest.mark.parametrize("onbekend", ["Sunburst", "Very Good", "bordeuax", "", None, "blauw, sunburst"])
def test_onbekend_blijft_onbekend(onbekend):
    assert canonieke_kleur(onbekend) == ""


def test_server_zet_kleur_om_bij_opslaan():
    from backend.api.items import _kleur_op_de_lijst
    d = {"color": "grijze"}; _kleur_op_de_lijst(d); assert d["color"] == "Grey"
    d = {"color": "Sunburst"}; _kleur_op_de_lijst(d); assert d["color"] == "Sunburst"
    d = {"title": "x"}; _kleur_op_de_lijst(d); assert "color" not in d
