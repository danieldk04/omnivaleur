"""
Zoekvolume-check via de Google Ads API (Keyword Planner historical metrics) —
voorkomt dat de content-pijplijn artikelen schrijft voor keywords die Claude
plausibel liet klinken maar die niemand daadwerkelijk zoekt.

Vereist: een Google Ads developer token (aangevraagd bij Google, kan een paar
dagen goedkeuring kosten) + OAuth client id/secret/refresh token gekoppeld aan
een Google Ads-account. Faalt zacht (retourneert None per keyword) als dit niet
is geconfigureerd — dan slaat de keyword-planner de volume-filter simpelweg over
in plaats van de hele pijplijn te blokkeren.
"""
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

# Onder dit maandelijkse zoekvolume beschouwen we een keyword als "geen publiek"
# en slaan we het over — voorkomt artikelen voor keywords met ~0 zoekopdrachten/maand.
MIN_MONTHLY_SEARCHES = 10


def _is_configured() -> bool:
    return bool(
        settings.google_ads_developer_token
        and settings.google_ads_client_id
        and settings.google_ads_client_secret
        and settings.google_ads_refresh_token
        and settings.google_ads_login_customer_id
    )


def get_search_volumes(keywords: list[str], region: str = "NL") -> dict[str, int | None]:
    """
    Retourneert {keyword: gemiddeld maandelijks zoekvolume} voor de gegeven keywords.
    Waarde is None per keyword als de Ads-API niet geconfigureerd is of de call faalt —
    de aanroeper moet None interpreteren als "onbekend, niet als 0" en de volume-filter
    dan overslaan i.p.v. het keyword af te wijzen.
    """
    if not keywords:
        return {}
    if not _is_configured():
        logger.info("Google Ads API niet geconfigureerd — zoekvolume-check overgeslagen")
        return {k: None for k in keywords}

    try:
        from google.ads.googleads.client import GoogleAdsClient

        client = GoogleAdsClient.load_from_dict(
            {
                "developer_token": settings.google_ads_developer_token,
                "client_id": settings.google_ads_client_id,
                "client_secret": settings.google_ads_client_secret,
                "refresh_token": settings.google_ads_refresh_token,
                "login_customer_id": settings.google_ads_login_customer_id,
                "use_proto_plus": True,
            }
        )
        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

        geo_target_map = {"NL": "2528", "BE": "2056"}
        geo_target_constant = geo_target_map.get(region, geo_target_map["NL"])

        request = client.get_type("GenerateKeywordIdeaRequest")
        request.customer_id = settings.google_ads_login_customer_id
        request.language = "languageConstants/1010"  # Dutch
        request.geo_target_constants.append(f"geoTargetConstants/{geo_target_constant}")
        request.keyword_seed.keywords.extend(keywords)
        request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

        volumes: dict[str, int | None] = {k: None for k in keywords}
        for idea in response:
            text = idea.text.lower()
            for keyword in keywords:
                if keyword.lower() == text:
                    metrics = idea.keyword_idea_metrics
                    volumes[keyword] = metrics.avg_monthly_searches or 0
        return volumes
    except Exception as e:
        logger.error(f"Google Ads zoekvolume-check mislukt: {e}")
        return {k: None for k in keywords}


def meets_volume_threshold(keyword: str, region: str = "NL") -> bool:
    """True als het keyword genoeg volume heeft, OF als volume onbekend is (fail-open —
    we blokkeren nooit content-generatie puur omdat de Ads-API niet beschikbaar is)."""
    volumes = get_search_volumes([keyword], region=region)
    volume = volumes.get(keyword)
    if volume is None:
        return True
    return volume >= MIN_MONTHLY_SEARCHES
