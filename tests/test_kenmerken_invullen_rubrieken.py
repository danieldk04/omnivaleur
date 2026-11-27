"""Wat het dashboard automatisch invult (kenmerken-uit-tekst.js) moet op Marktplaats
en 2dehands een geldige rubriek en een bekende kleur geven. De waarden komen uit
dezelfde lijsten als een handmatige keuze, dus hier staat vast dat elke mogelijke
uitkomst door de bestaande vertaling heen komt."""
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

from backend.services.kleur import normaliseer_kleur

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "kenmerken-uit-tekst.js").read_text()

_spec = importlib.util.spec_from_file_location("mpv", ROOT / "tests" / "test_marktplaats_verversen.py")
mpv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mpv)

CATEGORIEEN = {
    "heren": ["heren jassen", "heren hoodies", "heren truien", "heren jeans", "heren chinos",
              "heren shorts", "heren polo's", "heren t-shirts", "heren overhemden"],
    "dames": ["jassen", "hoodies", "truien", "jeans", "broeken", "shorts", "tops", "blouses",
              "jurken casual", "rokken"],
}


def test_de_lijst_hier_is_de_lijst_van_de_module():
    """Staat er in de module een rubriek bij die deze proef niet kent, dan is die niet bewezen."""
    gebruikt = set(re.findall(r'"((?:heren )?[a-z\' -]+)"', JS[JS.index("const SLEUTEL"):JS.index("// Alleen de TITEL")]))
    bekend = {x for lijst in CATEGORIEEN.values() for x in lijst}
    gebruikt -= {"heren", "dames"}
    assert gebruikt <= bekend, gebruikt - bekend


@pytest.mark.skipif(mpv.NODE is None, reason="node is niet geïnstalleerd")
@pytest.mark.parametrize("platform", ["marktplaats", "2dehands"])
def test_elke_ingevulde_rubriek_heeft_een_plek(platform):
    items = [{"title": "x", "category": c, "gender": g} for g, lijst in CATEGORIEEN.items() for c in lijst]
    driver = (f"{mpv._mp_url_js()}\nfor (const it of {json.dumps(items)}) {{"
              f" try {{ console.log(it.gender + '|' + it.category + '|' + getMpSyiUrl('{platform}', it)); }}"
              f" catch (e) {{ console.log(it.gender + '|' + it.category + '|FOUT ' + e.message); }} }}")
    r = subprocess.run([mpv.NODE, "-e", driver], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    regels = r.stdout.strip().splitlines()
    assert len(regels) == len(items)
    kapot = [x for x in regels if "FOUT" in x or "/plaats/" not in x]
    assert not kapot, kapot
    # Heren komt nooit in de damesafdeling (cat1 621) en andersom (1776 = heren).
    for x in regels:
        g, _, url = x.split("|", 2)
        assert ("/1776/" in url) == (g == "heren"), x


def test_elke_ingevulde_kleur_wordt_een_marktplaatskleur():
    """Lijsten uit het echte plaatsformulier (30-09-2026). Een kleur die Marktplaats
    niet schrijft, mag alleen via een bekende uitwijk (Bordeaux → Rood), nooit leeg of fout."""
    lijsten = json.loads((ROOT / "tests/fixtures/marktplaats_kleurlijsten_30-09-2026.json").read_text())["lijsten"]
    alle = {v for l in lijsten for v in l["values"]}
    kleuren = re.findall(r'\["([A-Z][A-Za-z ]+)", /', JS[JS.index("const KLEUREN"):JS.index("function kleurIn")])
    assert len(kleuren) >= 20
    shared = (ROOT / "extension/content/shared.js").read_text()
    uitwijk = {"bordeaux": "Rood"}
    for k in kleuren:
        nl = normaliseer_kleur(k)
        assert nl, k
        assert nl in alle or (nl.lower() in uitwijk and uitwijk[nl.lower()] in alle), (k, nl)
        if nl not in alle:
            assert f'{nl.lower()}: ["{uitwijk[nl.lower()]}"]' in shared
