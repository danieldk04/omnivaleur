"""Onderwerpkeuze en terugverwijzing van de dagelijkse blog (25-09-2026)."""
from unittest.mock import patch

from backend.content import keyword_planner as kp
from backend.content import research


def test_synoniemen_zijn_hetzelfde_onderwerp():
    # Deze drie gingen in augustus/september 2026 alle drie live.
    assert kp._is_duplicate_intent("second-hand-book-reselling-automation", ["used-book-reselling-automation"])
    assert kp._is_duplicate_intent("vintage-books-reselling-automation", ["used-book-reselling-automation"])
    assert kp._is_duplicate_intent("antique-furniture-reselling-automation", ["used-furniture-reselling-automation"])
    assert kp._is_duplicate_intent("omnivaleur-vs-vendoo-which-crosslisting-tool-is-better", ["omnivaleur-vs-vendoo"])
    assert not kp._is_duplicate_intent("how-to-sell-faster-on-vinted", ["vinted-to-ebay-crosslisting-2026"])


def test_mix_is_gevarieerd_en_hooguit_een_niche():
    alleen_niches = [{"pillar": "B"}] * 12
    mix = kp.plan_mix(alleen_niches)
    assert mix.count("niche") == 0
    assert {"howto", "money_rules", "strategy", "competitor"} <= set(mix)
    assert kp.plan_mix([{"pillar": "A"}] * 12).count("niche") == 1


def test_model_mag_de_mix_niet_oprekken():
    antwoord = '[' + ','.join(
        f'{{"format": "niche", "keyword": "niche nummer {i}", "nl_keyword": "niche {i}"}}' for i in range(5)
    ) + ',{"format": "howto", "keyword": "how to sell faster on vinted", "nl_keyword": "sneller verkopen op vinted"}]'
    with patch("backend.services.taalmodel.vraag", return_value=antwoord), \
         patch.object(kp, "meets_volume_threshold", return_value=True), \
         patch.object(research, "competitor_blog_topics", return_value=[]), \
         patch.object(kp, "_zoekdata", return_value={"pages": [], "queries": []}):
        items = kp.suggest_keywords([], [], [{"pillar": "A"}] * 12)
    soorten = [i["format"] for i in items]
    assert soorten.count("niche") == 1
    assert "howto" in soorten
    assert all(i["pillar"] == "B" for i in items)
    assert any(i.get("nl_slug") == "sneller-verkopen-op-vinted" for i in items)


def test_nooit_twee_dezelfde_soorten_na_elkaar():
    items = [{"format": f} for f in ["howto", "howto", "strategy", "competitor"]]
    uit = [i["format"] for i in kp._afwisselen(items)]
    assert all(a != b for a, b in zip(uit, uit[1:]))


def test_eigen_site_en_winkels_tellen_niet_als_concurrent():
    html = "".join(
        f'<a class="result__a" href="{u}">x</a>' for u in [
            "https://omnivaleur.com/reseller-tools/x", "https://www.amazon.com/boek",
            "https://crosslist.com/blog/a", "https://vendoo.co/b", "https://nifty.ai/c", "https://d.nl/d"])

    class Antwoord:
        text = html
        def raise_for_status(self):
            pass

    with patch.object(research.httpx, "get", return_value=Antwoord()):
        urls = research._ddg_search("x", "nl", max_results=3)
    assert urls == ["https://crosslist.com/blog/a", "https://vendoo.co/b", "https://nifty.ai/c"]


def test_terugverwijzing_kiest_verwante_pagina_en_is_herhaalbaar():
    from backend.content.pipeline import link_back
    rijen = [
        {"id": 1, "slug": "used-furniture-reselling-automation", "pillar": "B", "language": "en",
         "primary_keyword": "used furniture reselling automation", "title": "Used furniture", "body_html": "<p>a</p>"},
        {"id": 2, "slug": "sneaker-reselling-automation", "pillar": "B", "language": "en",
         "primary_keyword": "sneaker reselling automation", "title": "Sneakers", "body_html": "<p>b</p>"},
    ]
    doel = "/reseller-tools/office-furniture-reselling-automation"
    eerste = link_back(None, language="en", url_path=doel, title="Office furniture",
                       keyword="office furniture reselling", dry_run=True, rijen=rijen)
    assert eerste == ["used-furniture-reselling-automation"]
    assert rijen[0]["body_html"].endswith(f'<a href="{doel}">Office furniture</a></p>')
    assert link_back(None, language="en", url_path=doel, title="Office furniture",
                     keyword="office furniture reselling", dry_run=True, rijen=rijen) == []
