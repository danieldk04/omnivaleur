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
    # De OAuth-client wordt gedeeld met Google Ads (zelfde Cloud-project). In Railway
    # staan alleen de GOOGLE_ADS_* varianten, dus val daarop terug voor client id/secret.
    client_id = settings.gsc_client_id or settings.google_ads_client_id
    client_secret = settings.gsc_client_secret or settings.google_ads_client_secret
    refresh_token = settings.gsc_refresh_token
    if not (client_id and client_secret and refresh_token):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
    except Exception as e:
        logger.error(f"GSC-service kon niet worden opgebouwd: {e}")
        return None


_RESOLVED_SITE_URL: str | None = None


def _resolve_site_url(service) -> str:
    """
    De GSC-API vereist dat siteUrl EXACT matcht met de geregistreerde property. Die kan
    een domain-property zijn (`sc-domain:crosslisteu.com`) of een URL-prefix mét slash
    (`https://crosslisteu.com/`) — onze config-default (`https://crosslisteu.com`) matcht
    dan niet en levert lege data op. We halen daarom de echte lijst met properties op en
    kiezen de match voor het geconfigureerde domein. Resultaat wordt gecachet.
    """
    global _RESOLVED_SITE_URL
    if _RESOLVED_SITE_URL:
        return _RESOLVED_SITE_URL

    configured = settings.gsc_site_url
    # Domein zonder scheme/slash, voor losse vergelijking (crosslisteu.com).
    bare = configured.replace("https://", "").replace("http://", "").strip("/")

    try:
        entries = service.sites().list().execute().get("siteEntry", [])
        candidates = [e["siteUrl"] for e in entries
                      if e.get("permissionLevel") not in ("siteUnverifiedUser",)]
        # Voorkeur: exacte config-match > domain-property > URL-prefix met slash > wat dan ook.
        pick = None
        for s in candidates:
            if s == configured:
                pick = s; break
        if not pick:
            for s in candidates:
                if s == f"sc-domain:{bare}":
                    pick = s; break
        if not pick:
            for s in candidates:
                if bare in s:
                    pick = s; break
        if pick:
            _RESOLVED_SITE_URL = pick
            if pick != configured:
                logger.info(f"GSC siteUrl auto-gedetecteerd: {pick} (config was {configured})")
            return pick
        logger.warning(f"Geen GSC-property gevonden voor {bare}. Beschikbaar: {candidates}")
    except Exception as e:
        logger.error(f"GSC sites().list() mislukt: {e}")

    _RESOLVED_SITE_URL = configured
    return configured


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


def query_window(
    dimensions: list[str],
    start: str,
    end: str,
    row_limit: int = 200,
    dimension_filters: list[dict] | None = None,
) -> list[dict]:
    """
    Generieke GSC-query over een expliciet datumvenster (start/end als ISO-strings).
    Gebruikt door het wekelijkse analytics-rapport om 'deze week vs vorige week' te
    vergelijken zonder eigen opslag. Geeft rijen terug met de gevraagde dimensiekeys
    plus clicks/impressions/ctr/position. Faalt zacht (lege lijst).
    """
    service = _get_service()
    if not service:
        return []

    body: dict = {
        "startDate": start,
        "endDate": end,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    if dimension_filters:
        body["dimensionFilterGroups"] = [{"filters": dimension_filters}]

    try:
        response = (
            service.searchanalytics()
            .query(siteUrl=settings.gsc_site_url, body=body)
            .execute()
        )
    except Exception as e:
        logger.error(f"GSC window-query mislukt ({dimensions} {start}..{end}): {e}")
        return []

    rows = []
    for row in response.get("rows", []):
        rec = {"keys": row["keys"]}
        rec.update(
            clicks=row.get("clicks", 0),
            impressions=row.get("impressions", 0),
            ctr=row.get("ctr", 0.0),
            position=row.get("position", 0.0),
        )
        rows.append(rec)
    return rows
