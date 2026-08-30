"""
Google Analytics 4 (Data API) reader voor het wekelijkse marketingrapport.

Levert de signalen die Search Console niet heeft: echt bezoekersverkeer, welke
kanalen (organic / social / referral / direct) de bezoekers binnenbrengen, en
welke landingspagina's het meeste verkeer trekken — inclusief per-kanaal-uitsplitsing
zodat 'welke contentkanalen leveren de meeste (waardevolle) gebruikers' beantwoord
kan worden.

Auth: hergebruikt dezelfde Google OAuth-client als Search Console (org policy blokkeert
service-account keys op dit project). Alleen een apart refresh token met de
analytics.readonly-scope is nodig — plus het numerieke GA4 property-ID.

Faalt overal ZACHT (lege lijst / nul): zolang GA4 nog niet is aangemaakt en de
env-vars leeg zijn, draait het rapport gewoon op Search Console + signups en toont
GA4-secties als 'nog niet gekoppeld'. Er breekt niets.
"""
from __future__ import annotations

import logging

from backend.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _oauth_client() -> tuple[str, str]:
    """De OAuth-client wordt gedeeld met Search Console / Google Ads (zelfde Google
    Cloud-project). In Railway staan alleen de GOOGLE_ADS_* varianten, dus val daarop
    terug als de GSC_* niet zijn gezet."""
    client_id = settings.gsc_client_id or settings.google_ads_client_id
    client_secret = settings.gsc_client_secret or settings.google_ads_client_secret
    return client_id, client_secret


def is_configured() -> bool:
    client_id, client_secret = _oauth_client()
    return bool(
        settings.ga4_property_id
        and settings.ga4_refresh_token
        and client_id
        and client_secret
    )


def _get_client():
    if not is_configured():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.analytics.data_v1beta import BetaAnalyticsDataClient

        client_id, client_secret = _oauth_client()
        credentials = Credentials(
            token=None,
            refresh_token=settings.ga4_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        return BetaAnalyticsDataClient(credentials=credentials)
    except Exception as e:
        logger.error(f"GA4-client kon niet worden opgebouwd: {e}")
        return None


def probe(start: str, end: str) -> dict:
    """Werkt de koppeling, en zo nee: waarom niet?

    _run vangt elke fout af en geeft een lege lijst terug. Handig voor een
    rapport dat door moet draaien, maar op een dashboard betekent het dat
    "geen toegang" er precies zo uitziet als "geen bezoekers" — nul. Dit
    doet één kale sessie-telling en geeft de echte melding terug.
    """
    if not is_configured():
        return {"ok": False, "reden": "Analytics niet gekoppeld"}
    try:
        from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest

        client = _get_client()
        if client is None:
            return {"ok": False, "reden": "Analytics-verbinding kon niet worden opgebouwd"}
        antwoord = client.run_report(RunReportRequest(
            property=_property(),
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start, end_date=end)],
        ))
        sessies = int(antwoord.rows[0].metric_values[0].value) if antwoord.rows else 0
        return {"ok": True, "sessies": sessies}
    except Exception as e:
        melding = str(e)
        if "SERVICE_DISABLED" in melding or "has not been used in project" in melding:
            kort = ("De Google Analytics Data API staat uit in je Google Cloud-project. "
                    "Zet hem aan, daarna vult dit blok zichzelf.")
        elif "PermissionDenied" in type(e).__name__ or "403" in melding:
            kort = "Geen toegang tot deze Analytics-property met de huidige koppeling."
        else:
            kort = f"Analytics gaf een fout: {type(e).__name__}"
        logger.warning("GA4-probe mislukt: %s", melding[:300])
        return {"ok": False, "reden": kort}


def _property() -> str:
    return f"properties/{settings.ga4_property_id}"


def _run(dimensions: list[str], metrics: list[str], start: str, end: str, limit: int = 25) -> list[dict]:
    """Draait één GA4-rapport en geeft platte dicts terug (dimensie- + metriek-namen als keys)."""
    client = _get_client()
    if not client:
        return []
    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=_property(),
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            date_ranges=[DateRange(start_date=start, end_date=end)],
            limit=limit,
        )
        response = client.run_report(request)
    except Exception as e:
        logger.error(f"GA4-rapport mislukt ({dimensions}/{metrics} {start}..{end}): {e}")
        return []

    out = []
    for row in response.rows:
        rec: dict = {}
        for i, d in enumerate(dimensions):
            rec[d] = row.dimension_values[i].value
        for i, m in enumerate(metrics):
            raw = row.metric_values[i].value
            try:
                rec[m] = float(raw) if "." in raw else int(raw)
            except (ValueError, TypeError):
                rec[m] = raw
        out.append(rec)
    return out


def channels(start: str, end: str) -> list[dict]:
    """
    Verkeer per default-kanaalgroep (Organic Search, Organic Social, Referral, Direct, …)
    met sessies, actieve gebruikers en conversies. Dit is de kern van 'waar komen mijn
    (waardevolle) gebruikers vandaan'.
    """
    rows = _run(
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "activeUsers", "newUsers", "conversions"],
        start=start,
        end=end,
        limit=25,
    )
    return sorted(rows, key=lambda r: r.get("sessions", 0), reverse=True)


def sessions_by_day(start: str, end: str) -> dict[str, int]:
    """Sessies per dag als {'YYYY-MM-DD': n} — de bron voor de weektrend.

    GA4 geeft de datum terug als '20260815'; die wordt hier meteen omgezet naar
    de ISO-vorm die de rest van het rapport gebruikt.
    """
    out: dict[str, int] = {}
    for r in _run(dimensions=["date"], metrics=["sessions"], start=start, end=end, limit=400):
        d = str(r.get("date") or "")
        if len(d) == 8 and d.isdigit():
            out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = r.get("sessions", 0)
    return out


def top_landing_pages(start: str, end: str, limit: int = 15) -> list[dict]:
    """Waar bezoekers binnenkomen — 'welke pagina vangt het verkeer op'.

    Met engagementRate erbij, want een landingspagina die veel sessies trekt en
    waar iedereen meteen weer weg is, is geen succes maar een lek."""
    rows = _run(
        dimensions=["landingPagePlusQueryString"],
        metrics=["sessions", "activeUsers", "conversions", "engagementRate"],
        start=start,
        end=end,
        limit=limit,
    )
    return sorted(rows, key=lambda r: r.get("sessions", 0), reverse=True)


def top_pages(start: str, end: str, limit: int = 12) -> list[dict]:
    """Wat bezoekers bekijken zodra ze binnen zijn.

    Landingspagina's vertellen waar iemand aankomt; dit vertelt waar hij daarna
    heen loopt. Het verschil tussen die twee is het enige zicht op gedrag dat
    zonder extra meetwerk te krijgen is — en het beantwoordt de vraag die er
    echt toe doet: halen bezoekers de registratiepagina wel?"""
    rows = _run(
        dimensions=["pagePath"],
        metrics=["screenPageViews", "activeUsers"],
        start=start,
        end=end,
        limit=limit,
    )
    return sorted(rows, key=lambda r: r.get("screenPageViews", 0), reverse=True)


def totals(start: str, end: str) -> dict:
    """Kerncijfers voor de hele site over het venster."""
    rows = _run(
        dimensions=[],
        metrics=["sessions", "activeUsers", "newUsers", "conversions",
                 "engagementRate", "averageSessionDuration"],
        start=start,
        end=end,
        limit=1,
    )
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Per-platform social + post-niveau (UTM)
# ---------------------------------------------------------------------------
# GA4's default-kanaalgroep gooit alle social op één hoop ("Organic Social").
# Om te weten WELK platform (TikTok vs Instagram vs YouTube vs Pinterest vs
# Reddit) de bezoekers levert, kijken we naar de ruwe bron (sessionSource) en
# mappen die naar een leesbaar platform. Substring-match, want GA4 rapporteert
# bronnen wisselend (tiktok / tiktok.com, l.instagram.com, m.youtube.com, …).
_PLATFORM_MAP: list[tuple[str, str]] = [
    ("tiktok", "TikTok"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube"),
    ("pinterest", "Pinterest"),
    ("reddit", "Reddit"),
    ("linkedin", "LinkedIn"),
    ("lnkd", "LinkedIn"),
    ("facebook", "Facebook"),
    ("fb.me", "Facebook"),
    ("t.co", "X / Twitter"),
    ("twitter", "X / Twitter"),
    ("x.com", "X / Twitter"),
    ("threads", "Threads"),
    ("snapchat", "Snapchat"),
]


def platform_of(source: str) -> str | None:
    """Mapt een GA4-bron (sessionSource) naar een leesbaar social-platform, of None
    als het geen (herkend) social kanaal is."""
    s = (source or "").lower()
    for needle, label in _PLATFORM_MAP:
        if needle in s:
            return label
    return None


def traffic_sources(start: str, end: str, limit: int = 100) -> list[dict]:
    """Ruwe bron/medium-uitsplitsing — grondstof voor de per-platform social-analyse."""
    return _run(
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "activeUsers", "newUsers", "conversions"],
        start=start,
        end=end,
        limit=limit,
    )


def social_posts(start: str, end: str, limit: int = 50) -> list[dict]:
    """
    Post-niveau attributie via UTM-tags: campagne (utm_campaign) + content (utm_content).
    Werkt alleen voor links die je zelf getagd hebt (zie de UTM-bouwer in het dashboard).
    Zonder UTM's is dit leeg — GA4 kan een individuele TikTok/Reel/Pin niet raden.
    """
    rows = _run(
        dimensions=["sessionSource", "sessionCampaignName", "sessionManualAdContent"],
        metrics=["sessions", "newUsers", "conversions"],
        start=start,
        end=end,
        limit=limit,
    )
    # Filter de ruis weg: alleen rijen met een echte utm_content of utm_campaign.
    out = []
    for r in rows:
        content = r.get("sessionManualAdContent", "")
        campaign = r.get("sessionCampaignName", "")
        if content in ("(not set)", "", "(direct)") and campaign in ("(not set)", "", "(direct)", "(organic)", "(referral)"):
            continue
        out.append(r)
    return sorted(out, key=lambda r: r.get("sessions", 0), reverse=True)
