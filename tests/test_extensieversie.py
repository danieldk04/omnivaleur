"""De ondergrens voor de extensieversie, aan beide kanten.

Aanleiding (27-08-2026, Jaap op Urk): hij draaide drie weken 1.0.218 terwijl de
Chrome Web Store op 1.0.249 stond. Die kopie nam werk aan en leverde het half
af — vandaar dat we nu zowel in het dashboard als op de server een grens
trekken. Deze test bewaakt dat die twee grenzen dezelfde blijven.
"""
import re
from pathlib import Path

from backend.api.jobs import MINIMALE_SCANVERSIE, _kopstuk_versie

WORTEL = Path(__file__).resolve().parents[1]


def test_kopstuk_leest_een_nette_versie():
    assert _kopstuk_versie("1.0.250") == (1, 0, 250)
    assert _kopstuk_versie(" 1.0.244 ") == (1, 0, 244)


def test_kopstuk_houdt_niets_tegen_bij_twijfel():
    # Geen kopstuk, rommel, of iets wat op een versie lijkt maar het niet is:
    # allemaal None, want een kopie ten onrechte stilzetten is erger.
    for waarde in (None, "", "onbekend", "1.0", "v1.0.250", "1.0.250-beta", "9999.0.0.1"):
        assert _kopstuk_versie(waarde) is None, waarde


def test_gate_ligt_op_of_boven_de_versie_die_het_verkocht_venster_kent():
    # 1.0.244 is de eerste kopie die het "Heb je dit verkocht via Marktplaats?"-
    # venster wegklikt. Alles daaronder kan geen advertentie verwijderen en dus
    # ook niet herplaatsen.
    assert MINIMALE_SCANVERSIE >= (1, 0, 244)


def test_dashboard_hanteert_dezelfde_ondergrens_als_de_server():
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    m = re.search(r"const EXT_MIN_VERSION = '(\d+)\.(\d+)\.(\d+)'", app)
    assert m, "EXT_MIN_VERSION niet gevonden in app.html"
    assert tuple(int(g) for g in m.groups()) == MINIMALE_SCANVERSIE


def test_extensie_stuurt_haar_versie_mee_bij_elk_verzoek():
    bg = (WORTEL / "extension" / "background.js").read_text(encoding="utf-8")
    assert "X-Omnivaleur-Ext" in bg
    # ... en wel in getAuthHeaders, zodat het kopstuk op ELKE aanroep meegaat en
    # niet alleen op de een die iemand toevallig aanpaste.
    blok = bg.split("async function getAuthHeaders()")[1].split("\n}")[0]
    assert "X-Omnivaleur-Ext" in blok


def test_verouderde_kopie_wordt_geblokkeerd_in_het_dashboard():
    app = (WORTEL / "frontend" / "app.html").read_text(encoding="utf-8")
    assert 'id="ext-outdated-overlay"' in app
    # De melding moet ook echt getoond worden, niet alleen bestaan.
    assert "extVersionIsOld()" in app.split("function renderExtSetup()")[1][:1500]
