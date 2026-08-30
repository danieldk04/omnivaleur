"""Bewaakt dat het marketing-dashboard blijft renderen.

Aanleiding, 30-08-2026. Het dashboard is toen uitgedund en kreeg een blok over
gedrag op de site. Dat is een Jinja-sjabloon dat alleen op de server draait,
achter een token, met echte GA4-gegevens erachter — er is dus geen enkel moment
waarop een schrijffout opvalt vóórdat Daniel de pagina opent en een foutmelding
krijgt in plaats van zijn cijfers.

Deze test rendert het sjabloon twee keer: één keer met een volledig rapport, en
één keer met een leeg rapport (Analytics niet gekoppeld, geen Search Console,
geen enkele rij). Dat tweede geval is het gevaarlijkste, want zo ziet het eruit
zodra een koppeling wegvalt — en juist dan moet de pagina blijven staan.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

SJABLONEN = Path(__file__).parent.parent / "frontend" / "templates"


def _render(report: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(SJABLONEN)))
    sjabloon = env.get_template("analytics_dashboard.html")
    return sjabloon.render(
        report=report,
        site_url="https://omnivaleur.com",
        token="test",
        kanalen=[{"kanaal": "Instagram", "taal": "EN", "link": "https://omnivaleur.com/?utm_source=instagram",
                  "kortelink": "https://omnivaleur.com/ig"}],
        maillink={"kanaal": "Koude mail", "taal": "NL", "pad": "/mp-video",
                  "link": "https://omnivaleur.com/mp-video?utm_source=koude-mail",
                  "kortelink": "https://omnivaleur.com/mp"},
    )


LEEG = {
    "period": {"this": ("2026-08-23", "2026-08-29"), "prev": ("2026-08-16", "2026-08-22")},
    "patterns": [],
    "seo": {"connected": False},
    "signups": {"available": False},
    "channels": {"connected": False},
    "social": {"connected": False},
    "categories": [],
    "social_content": {},
}

VOL = {
    **LEEG,
    "patterns": ["Meeste verkeer via Direct."],
    "seo": {"connected": True, "has_data": True, "total_clicks": 8, "total_clicks_delta": -38.5,
            "total_impressions": 275,
            "top_pages": [{"url": "https://omnivaleur.com/", "clicks": 5, "clicks_delta": -37.5,
                           "impressions": 19, "position": 3.5}],
            "risers": [{"query": "omnivaleur", "clicks_prev": 0, "clicks": 2, "position": 1.8}]},
    "signups": {"available": True, "this_week": 7, "prev_week": 5, "delta": 40.0},
    "channels": {
        "connected": True,
        "channels": [{"sessionDefaultChannelGroup": "Direct", "sessions": 92, "sessions_delta": 70.4,
                      "newUsers": 59, "conversions": 0}],
        "landing_pages": [{"landingPagePlusQueryString": "/", "sessions": 40,
                           "engagementRate": 0.48, "conversions": 1}],
        "pages": [{"pagePath": "/register", "screenPageViews": 30, "activeUsers": 12}],
        "totals": {"sessions": 244, "newUsers": 110, "conversions": 0,
                   "engagementRate": 0.4877, "averageSessionDuration": 59.2},
    },
    "social": {
        "connected": True,
        "platforms": [{"platform": "Instagram", "sessions": 8, "sessions_delta": 100.0,
                       "newUsers": 6, "conversions": 0, "conv_rate": 0.0}],
        "posts": [{"platform": "Instagram", "sessionCampaignName": "bio-en",
                   "sessionManualAdContent": "", "sessions": 5, "newUsers": 3, "conversions": 0}],
        "has_utm_data": True,
    },
}


def test_dashboard_rendert_met_volledige_gegevens():
    html = _render(VOL)
    assert "Van bezoek naar account" in html
    assert "Wat ze op de site doen" in html
    assert "/register" in html          # het gedragsblok toont echt paginas
    assert "6,4%" in html or "6.4%" in html   # 7 aanmeldingen op 110 nieuwe bezoekers


def test_dashboard_blijft_staan_als_alles_leeg_is():
    """Een weggevallen koppeling mag geen witte pagina opleveren."""
    html = _render(LEEG)
    assert "Marketing-dashboard" in html
    assert "nog niet gekoppeld" in html


def test_categorietabel_blijft_weg_zolang_hij_niets_zegt():
    """Drie categorieen met samen acht clicks is ruis; die tabel hoort pas te
    verschijnen als er iets uit af te lezen valt."""
    weinig = {**VOL, "categories": [
        {"category": "Homepage", "pages": 1, "clicks": 5, "clicks_delta": -37.5, "impressions": 19, "ctr": 26.3},
        {"category": "Crosslisting-guides", "pages": 7, "clicks": 2, "clicks_delta": 100.0, "impressions": 60, "ctr": 3.3},
        {"category": "Blog-index", "pages": 2, "clicks": 1, "clicks_delta": 100.0, "impressions": 10, "ctr": 10.0},
    ]}
    assert "Welk soort artikel trekt zoekverkeer" not in _render(weinig)

    veel = {**VOL, "categories": [
        {**c, "clicks": c["clicks"] * 10} for c in weinig["categories"]
    ]}
    assert "Welk soort artikel trekt zoekverkeer" in _render(veel)
