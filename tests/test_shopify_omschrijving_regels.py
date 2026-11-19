"""Mieneke (voordeelsieraden), 18-11-2026: Shopify zet regelovergangen tussen de tags.
Die werden extra witregels onder elke kop en tussen elk opsommingspunt."""
from backend.platforms.shopify_importer import _platte_tekst

HTML = (
    "<p>Intro.</p>\n<h2>Stijl en vakmanschap</h2>\n<p>Het ontwerp.</p>\n"
    "<h2>Specificaties</h2>\n<ul>\n<li>Materiaal: A</li>\n<li><p>Gewicht: 98 gram</p></li>\n</ul>\n"
    "<h2>Veelgestelde vragen (FAQ)</h2>\n<h3>Is dit echt?</h3>\n<p>Ja.</p>\n"
    "<h3>Hoe blijft het?</h3>\n<p>Zo.</p>"
)


def test_geen_witregel_onder_kop_en_tussen_punten():
    assert _platte_tekst(HTML) == (
        "Intro.\n\nStijl en vakmanschap\nHet ontwerp.\n\n"
        "Specificaties\n- Materiaal: A\n- Gewicht: 98 gram\n\n"
        "Veelgestelde vragen (FAQ)\nIs dit echt?\nJa.\n\nHoe blijft het?\nZo."
    )


def test_inline_spaties_blijven():
    assert _platte_tekst("<p>a <strong>b</strong> <em>c</em></p><p>d<br>e</p>") == "a b c\n\nd\ne"
