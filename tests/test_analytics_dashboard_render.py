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


def _render(report: dict, **extra) -> str:
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
        **extra,
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


def test_mailbezoek_op_de_videopagina_staat_op_het_dashboard():
    """07-10-2026: /mp en /mp-video samen als mailbezoek, met aanmeldingen erbij.
    Lukt de vraag naar aanmeldingen niet, dan 'onbekend' en geen nul."""
    html = _render(LEEG, mailvideo=[
        {"label": "Laatste 30 dagen", "bezoek": 79, "aanmeldingen": 2, "kort": 6, "lang": 73, "anders": 6},
        {"label": "Sinds 1 juni 2026", "bezoek": 5, "aanmeldingen": None, "kort": 1, "lang": 4, "anders": 0},
    ])
    assert "Uit de mail naar de videopagina" in html
    assert "<strong>79</strong>" in html and "onbekend" in html
    assert "Analytics nog niet gekoppeld" in _render(LEEG, mailvideo=[])


def _daily(n: int) -> dict:
    from datetime import date, timedelta
    d0 = date(2026, 9, 9)
    dagen = [(d0 + timedelta(days=i)).isoformat() for i in range(2 * n)]
    reeks = lambda k: {"sessions": [10 + i % 5 for i in range(n)], "newUsers": [5] * n,
                       "signups": [i % 2 for i in range(n)],
                       "clicks": [3] * (n - 3) + [None] * 3 if k else [2] * n}
    return {"dates": dagen[n:], "prev_dates": dagen[:n], "this": reeks(True), "prev": reeks(False)}


def test_vergelijking_per_periode_staat_overal_naast_de_cijfers():
    """07-10-2026, Daniel: de vergelijking met de vorige periode moet zichtbaarder,
    met een grafiek zoals Google Analytics. Elke tabel krijgt een kolom 'vorige',
    de kerncijfers staan als tabs boven de grafiek, en 28 en 90 dagen zijn kiesbaar."""
    rapport = {**VOL,
               "period": {"this": ("2026-09-09", "2026-10-06"), "prev": ("2026-08-12", "2026-09-08"),
                          "dagen": 28, "vorige": "vorige 28 dagen"},
               "daily": _daily(28)}
    rapport["channels"] = {**VOL["channels"],
                           "channels": [{"sessionDefaultChannelGroup": "Direct", "sessions": 92,
                                         "sessions_prev": 54, "newUsers": 59, "conversions": 3,
                                         "conversions_prev": 1},
                                        {"sessionDefaultChannelGroup": "Email", "sessions": 0,
                                         "sessions_prev": 7, "newUsers": 0, "conversions": 0}],
                           "totals_prev": {"sessions": 200, "newUsers": 100, "engagementRate": 0.4,
                                           "averageSessionDuration": 50}}
    html = _render(rapport, periodes=(7, 28, 90))
    assert "Laatste 28 dagen: 9 sep t/m 6 okt" in html
    assert 'class="on">28 dagen' in html and "dagen=90" in html
    assert "vorige 28 dagen 200" in html             # tab bezoeken met de vorige periode
    assert "+22%" in html                             # 244 tegen 200
    assert "+70%" in html and "-100%" in html          # kanaal erbij en kanaal weggevallen
    assert '"prev_dates"' in html                      # dagcijfers gaan mee naar de grafiek
    assert "vorige 28 dagen: 5,0%" in html             # 5 aanmeldingen op 100 nieuwe bezoekers


def test_periode_van_28_dagen_en_de_vorige_sluiten_aan():
    from datetime import date
    from backend.services.analytics_report import _windows
    w = _windows(date(2026, 10, 7), 28)
    assert w["this"] == ("2026-09-09", "2026-10-06") and w["prev"] == ("2026-08-12", "2026-09-08")
    assert _windows(date(2026, 10, 7))["vorige"] == "vorige week"   # de zondagsmail blijft week op week


def test_aanmeldingen_tellen_verder_dan_de_eerste_50(monkeypatch):
    """Supabase geeft zonder paginering alleen de nieuwste 50 accounts terug;
    gemeten 07-10-2026 waren het er 63. Alle pagina's moeten meetellen."""
    from types import SimpleNamespace
    import backend.database as db
    from backend.services.analytics_report import _signup_dates
    alle = [SimpleNamespace(created_at=f"2026-0{6 + i % 4}-1{i % 10}T10:00:00Z") for i in range(1003)]
    admin = SimpleNamespace(list_users=lambda page=1, per_page=50: alle[(page - 1) * per_page: page * per_page])
    monkeypatch.setattr(db, "get_admin_db", lambda: SimpleNamespace(auth=SimpleNamespace(admin=admin)))
    assert len(_signup_dates()) == 1003


def test_dagcijfers_tonen_niet_gemeten_dagen_als_leeg(monkeypatch):
    """Search Console loopt dagen achter: die dagen als nul tekenen leest als een
    instorting. Ze moeten leeg (None) blijven."""
    from backend.services import analytics_report as ar
    monkeypatch.setattr(ar.ga4, "is_configured", lambda: True)
    monkeypatch.setattr(ar.ga4, "by_day", lambda s, e: {"2026-10-06": {"sessions": 9, "newUsers": 4}})
    monkeypatch.setattr(ar.gsc, "query_window", lambda dims, s, e, row_limit=0:
                        [{"keys": ["2026-09-23"], "clicks": 2.0}, {"keys": ["2026-10-03"], "clicks": 5.0}])
    from datetime import date
    d = ar._daily(ar._windows(date(2026, 10, 7), 7), ["2026-10-06", "2026-09-29"])
    assert d["dates"][-1] == "2026-10-06" and d["prev_dates"][0] == "2026-09-23"
    assert d["this"]["sessions"][-1] == 9 and d["this"]["sessions"][0] == 0
    assert d["this"]["clicks"][-3:] == [None, None, None] and d["this"]["clicks"][3] == 5
    assert d["prev"]["clicks"][0] == 2 and d["this"]["signups"] == [0, 0, 0, 0, 0, 0, 1]
    assert d["prev"]["signups"][-1] == 1
