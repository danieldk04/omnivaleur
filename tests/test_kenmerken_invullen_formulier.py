"""Het echte koppelblok uit app.html tegen een minimaal formulier met de echte
keuzelijsten (kleur, maat). Bewaakt: vult leeg veld, laat handmatige keuze met
rust, vult niets bij een bewerking of bij twijfel."""
import re
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "frontend" / "app.html").read_text()


def _blok(id_):
    m = re.search(r'<select id="%s".*?</select>' % id_, APP, re.S)
    return m.group(0)


def _wiring():
    m = re.search(r'<script src="/kenmerken-uit-tekst.js[^>]*></script>\s*<script>(.*?)</script>', APP, re.S)
    assert m, "koppelblok niet gevonden"
    return m.group(1)


PAGINA = """<input id=edit-id><input id=f-title><textarea id=f-desc></textarea>
<select id=f-item-type><option value=clothing selected>c</option></select>
<select id=f-gender><option value=''>-</option><option value=dames>W</option><option value=heren>M</option></select>
%s %s %s
<div id=autofill-note style='display:none'>x</div>
<script>
function currentItemType(){return 'clothing'}
const CAT={heren:['heren jassen','heren truien'],dames:['jassen','truien']};
function updateCategoryOptions(sel){const s=document.getElementById('f-category');
 const g=document.getElementById('f-gender').value; s.innerHTML='<option value=\"\">-</option>';
 for(const k of [...(CAT[g]||[]),...CAT.heren,...CAT.dames]){const o=document.createElement('option');o.value=k;o.textContent=k;s.appendChild(o)}
 if(sel) s.value=sel}
function onCategoryPicked(){}
updateCategoryOptions('');
</script>
<script>%s</script><script>%s</script>"""


@pytest.fixture(scope="module")
def pagina():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            try:
                b = p.chromium.launch()
            except Exception:
                pytest.skip("geen browser beschikbaar voor Playwright")
        pg = b.new_page()
        html = PAGINA % (
            _blok("f-size"), '<select id=f-category></select>', _blok("f-color"),
            (ROOT / "frontend" / "kenmerken-uit-tekst.js").read_text(), _wiring())
        pg.set_content(html)
        yield pg
        b.close()


def typ(pg, titel, omschr=""):
    pg.fill("#f-title", titel)
    pg.fill("#f-desc", omschr)
    pg.wait_for_timeout(900)


def waarden(pg):
    return pg.evaluate("['f-gender','f-category','f-color','f-size'].map(i=>document.getElementById(i).value)")


def test_vult_lege_velden(pagina):
    pagina.evaluate("kenmerkenReset(); ['f-gender','f-category','f-color','f-size'].forEach(i=>document.getElementById(i).value='')")
    typ(pagina, "(721) Beige Ralph Lauren Fleece Jacket - Men M - Very Good")
    assert waarden(pagina) == ["heren", "heren jassen", "Beige", "M"]
    assert pagina.is_visible("#autofill-note")


def test_handmatige_keuze_blijft(pagina):
    pagina.evaluate("kenmerkenReset(); ['f-gender','f-category','f-color','f-size'].forEach(i=>document.getElementById(i).value='')")
    pagina.select_option("#f-color", "Red")   # echte gebruikershandeling
    typ(pagina, "Beige Ralph Lauren Fleece Jacket - Men M")
    assert waarden(pagina)[2] == "Red"


def test_twijfel_laat_leeg(pagina):
    pagina.evaluate("kenmerkenReset(); ['f-gender','f-category','f-color','f-size'].forEach(i=>document.getElementById(i).value='')")
    typ(pagina, "Zwart wit trui jas")
    assert waarden(pagina) == ["", "", "", ""]


def test_bewerken_blijft_ongemoeid(pagina):
    pagina.evaluate("kenmerkenReset(); ['f-gender','f-category','f-color','f-size'].forEach(i=>document.getElementById(i).value='')")
    pagina.evaluate("document.getElementById('edit-id').value='abc'")
    typ(pagina, "Beige Ralph Lauren Fleece Jacket - Men M")
    pagina.evaluate("document.getElementById('edit-id').value=''")
    assert waarden(pagina) == ["", "", "", ""]
