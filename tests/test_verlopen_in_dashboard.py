"""Een verlopen advertentie is in het dashboard als verlopen te zien (16-11-2026).

Daniel: "bij mij gaan er een aantal verlopen, dan wil ik in het dashboard terug
kunnen zien dat ze daadwerkelijk verlopen zijn." De server zette een verlopen
advertentie al op 'delisted' met een vaste reden, maar het dashboard toonde die
reden nergens: verlopen zag er precies zo uit als zelf offline gehaald.

Deze proef draait de ECHTE functies uit frontend/app.html in node. Op de versie
van voor deze wijziging bestaan ze niet en faalt alles hieronder.

Draaien:  python3 -m pytest tests/test_verlopen_in_dashboard.py -q
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HTML = (ROOT / "frontend" / "app.html").read_text()

from backend.api.listings import VERDENKING_REDENEN   # noqa: E402

REDEN = VERDENKING_REDENEN["verlopen"]


def _functies() -> str:
    blok = re.search(r"const VERLOPEN_REDEN = .*?(?=\nfunction verlopenDatum)", HTML, re.S)
    assert blok, "isVerlopen/verlopenPerItem staan niet meer in app.html"
    return blok.group(0)


def _draai(listings, jobs=(), items=("a",)):
    if not shutil.which("node"):
        pytest.skip("node ontbreekt")
    code = (f"const state = {json.dumps({'listings': list(listings), 'jobs': list(jobs), 'items': [{'id': i} for i in items]})};\n"
            + _functies()
            + "\nconst uit = {}; for (const [k, v] of verlopenPerItem()) uit[k] = Object.keys(v).sort();"
              "\nconsole.log(JSON.stringify(uit));")
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _rij(status, platform="marktplaats", reden=None, tijd="2026-11-10T10:00:00+00:00", item="a"):
    return {"item_id": item, "platform": platform, "status": status,
            "error_message": reden, "last_checked": tijd, "listed_at": "2026-10-01T10:00:00+00:00"}


def test_de_herkenning_past_op_de_tekst_van_de_server():
    patroon = re.search(r"const VERLOPEN_REDEN = /(.+?)/;", HTML).group(1)
    assert re.search(patroon, REDEN), "dashboard herkent de verlopen-reden van de server niet meer"
    for sleutel, tekst in VERDENKING_REDENEN.items():
        if sleutel != "verlopen":
            assert not re.search(patroon, tekst), f"reden '{sleutel}' wordt ten onrechte als verlopen gezien"


def test_verlopen_advertentie_staat_in_de_lijst():
    assert _draai([_rij("delisted", reden=REDEN)]) == {"a": ["marktplaats"]}


def test_zelf_offline_gehaald_is_niet_verlopen():
    assert _draai([_rij("delisted")]) == {}


def test_verlopen_op_een_kanaal_terwijl_een_ander_nog_live_staat():
    uit = _draai([_rij("delisted", reden=REDEN), _rij("active", platform="vinted")])
    assert uit == {"a": ["marktplaats"]}


def test_weer_online_gezet_telt_niet_meer():
    assert _draai([_rij("delisted", reden=REDEN), _rij("active")]) == {}
    assert _draai([_rij("delisted", reden=REDEN)],
                  jobs=[{"item_id": "a", "platform": "marktplaats", "action": "create", "status": "pending"}]) == {}


def test_later_zelf_weggehaald_telt_niet_meer():
    assert _draai([_rij("delisted", reden=REDEN, tijd="2026-11-01T10:00:00+00:00"),
                   _rij("delisted", tijd="2026-11-12T10:00:00+00:00")]) == {}


def test_verkocht_artikel_hoeft_niet_terug_online():
    assert _draai([_rij("delisted", reden=REDEN), _rij("sold", platform="vinted")]) == {}


def test_tabblad_tegelregel_en_melding_staan_erin():
    assert 'data-tab="expired"' in HTML and 'id="tabcount-expired"' in HTML
    assert "'expired'" in re.search(r"const ITEMS_TABS = \[(.*?)\]", HTML).group(1)
    assert 'data-verlopen="${p}"' in HTML
    assert re.search(r"expired:\s*\{ h:", HTML), "lege-lijsttekst voor het tabblad ontbreekt"
