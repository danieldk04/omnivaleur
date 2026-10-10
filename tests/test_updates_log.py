"""De updatelog (#view-nieuw in frontend/app.html) en de melding blijven één verhaal.

Daniel, 10-10-2026: elke grote ontwikkeling komt in de tijdlijn én krijgt een melding
met rondleiding. Deze proef faalt zodra iemand alleen het ene of het andere bijwerkt.
"""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "frontend" / "app.html").read_text()


def _berichten():
    return re.findall(
        r'<article class="upd[^"]*" data-id="([^"]+)" data-datum="(\d{4}-\d{2}-\d{2})" data-cat="(\w+)"', HTML)


def test_bovenste_bericht_is_de_melding():
    nieuws_id = re.search(r"const NIEUWS_ID = '([^']+)'", HTML).group(1)
    assert _berichten()[0][0] == nieuws_id, (
        "Zet een nieuw bericht BOVENAAN de tijdlijn met dezelfde id als NIEUWS_ID "
        "(of laat NIEUWS_ID staan als je geen nieuwe melding wilt).")


def test_tijdlijn_nieuwste_eerst_en_ids_uniek():
    b = _berichten()
    assert len(b) >= 10
    datums = [d for _, d, _ in b]
    assert datums == sorted(datums, reverse=True)
    ids = [i for i, _, _ in b]
    assert len(ids) == len(set(ids))
    assert {c for _, _, c in b} <= {"channels", "dashboard", "automation", "plans"}


def test_elke_rondleiding_bestaat_en_heeft_stappen():
    tours = set(re.findall(r"startRondleiding\('([\w-]+)'\)", HTML))
    for t in tours:
        blok = re.search(rf'<section data-tour="{t}">(.*?)</section>', HTML, re.S)
        assert blok, f"rondleiding {t} ontbreekt"
        assert 'data-doel=' in blok.group(1)
    tour = re.search(r"const NIEUWS_TOUR = '([^']+)'", HTML).group(1)
    assert re.search(rf'<section data-tour="{tour}">', HTML)
