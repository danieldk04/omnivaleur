"""
Google Search Console integration voor de content-pijplijn: levert twee signalen die
voorheen ontbraken (research.py was een blinde DuckDuckGo-scrape zonder echte
performance-data) — welke gepubliceerde pagina's al verkeer trekken (voor interne
linking en cannibalisatie-detectie) en of een kandidaat-keyword al ergens impressies
scoort op een bestaande pagina.

Vereist een Google Cloud service-account met "Restricted" toegang toegevoegd in
Search Console (Instellingen > Gebruikers en machtigingen) voor GSC_SITE_URL.
Faalt zacht (lege lijst) als gsc_service_account_json niet is geconfigureerd —
de pipeline mag hier nooit op vastlopen.
"""
import json
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _get_service():
    if not settings.gsc_service_account_json:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(settings.gsc_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
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
