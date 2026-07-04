"""
Google Search Console integration voor de content-pijplijn: levert twee signalen die
voorheen ontbraken (research.py was een blinde DuckDuckGo-scrape zonder echte
performance-data) — welke gepubliceerde pagina's al verkeer trekken (voor interne
linking en cannibalisatie-detectie) en of een kandidaat-keyword al ergens impressies
scoort op een bestaande pagina.

Auth via OAuth refresh token (niet een service account — het Google Cloud project
staat onder een org policy die service-account key creation blokkeert). Het account
achter gsc_refresh_token moet zelf "Restricted" (of hoger) toegang hebben in Search
Console (Instellingen > Gebruikers en machtigingen) voor GSC_SITE_URL.
Faalt zacht (lege lijst) als de OAuth-settings niet zijn geconfigureerd —
de pipeline mag hier nooit op vastlopen.
"""
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_service():
    if not (settings.gsc_client_id and settings.gsc_client_secret and settings.gsc_refresh_token):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,
            refresh_token=settings.gsc_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gsc_client_id,
            client_secret=settings.gsc_client_secret,
            scopes=SCOPES,
        )
        return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
    except Exception as e:
        logger.error(f"GSC-service kon niet worden opgebouwd: {e}")
        return None


def get_top_pages(days: int = 90, row_limit: int = 200) -> list[dict]:
    """
    Top gepubliceerde pagina's op clicks/impressions/positie over de laatste `days`
    dagen. Gebruikt voor: (a) interne-link-prioritering — verwijs vanuit nieuwe content
    naar pagina's die al traffic hebben, (b) performance-feedback naar de keyword
    planner (welke pillars/onderwerpen het al goed doen).
    """
    service = _get_service()
    if not service:
        return []

    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days)

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=settings.gsc_site_url,
                body={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": ["page"],
                    "rowLimit": row_limit,
                },
            )
            .execute()
        )
    except Exception as e:
        logger.error(f"GSC top-pages query mislukt: {e}")
        return []

    return [
        {
            "url": row["keys"][0],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": row["ctr"],
            "position": row["position"],
        }
        for row in response.get("rows", [])
    ]


def get_queries_for_page(page_url: str, days: int = 90, row_limit: int = 25) -> list[dict]:
    """Zoektermen die al impressies/clicks opleveren voor één specifieke gepubliceerde pagina."""
    service = _get_service()
    if not service:
        return []

    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days)

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=settings.gsc_site_url,
                body={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": ["query"],
                    "dimensionFilterGroups": [
                        {"filters": [{"dimension": "page", "operator": "equals", "expression": page_url}]}
                    ],
                    "rowLimit": row_limit,
                },
            )
            .execute()
        )
    except Exception as e:
        logger.error(f"GSC query-lookup mislukt voor {page_url}: {e}")
        return []

    return [
        {"query": row["keys"][0], "clicks": row["clicks"], "impressions": row["impressions"], "position": row["position"]}
        for row in response.get("rows", [])
    ]


def get_impressions_for_query(keyword: str, days: int = 90) -> int:
    """Totale impressies over alle pagina's voor één specifiek keyword — gebruikt als
    goedkope proxy-check ('bestaat hier al interesse voor?') wanneer geen Ads-volumedata
    beschikbaar is."""
    service = _get_service()
    if not service:
        return 0

    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=days)

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=settings.gsc_site_url,
                body={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": ["query"],
                    "dimensionFilterGroups": [
                        {"filters": [{"dimension": "query", "operator": "contains", "expression": keyword}]}
                    ],
                    "rowLimit": 10,
                },
            )
            .execute()
        )
    except Exception as e:
        logger.error(f"GSC impressie-lookup mislukt voor '{keyword}': {e}")
        return 0

    return sum(row["impressions"] for row in response.get("rows", []))
