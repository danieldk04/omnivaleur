from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=str(_ENV_FILE), env_file_encoding='utf-8')

    supabase_url: str = ""
    supabase_key: str = ""

    marktplaats_client_id: str = ""
    marktplaats_client_secret: str = ""
    marktplaats_redirect_uri: str = "http://localhost:8000/api/platforms/marktplaats/callback"

    shopify_store: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_scopes: str = "read_products,write_products"
    shopify_redirect_uri: str = "https://crosslisteu.com/shopify-callback.html"

    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    ebay_redirect_uri: str = "Daniel_de_Konin-Danielde-crossl-bwahwc"
    ebay_marketplace_id: str = "EBAY_NL"
    ebay_sandbox: bool = False
    ebay_default_category_id: str = ""
    ebay_verification_token: str = ""
    ebay_webhook_url: str = "https://crosslisteu.com/api/webhooks/ebay"

    anthropic_api_key: str = ""
    google_api_key: str = ""  # Gemini image-gen voor content_pages featured images

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    app_url: str = "https://app.crosslisteu.com"

    secret_key: str = "change-me"
    polling_interval: int = 300
    owner_email: str = "dkresellacademy@gmail.com"

    # Google Search Console — service account JSON (as a raw JSON string, not a file path)
    # for the content pipeline's keyword prioritization + internal-linking signal.
    # OAuth (not a service account — org policy blocks service-account key creation
    # on this Google Cloud project). Reuses the same OAuth client as Google Ads;
    # only the refresh token differs (separate consent, separate scope).
    gsc_client_id: str = ""
    gsc_client_secret: str = ""
    gsc_refresh_token: str = ""
    gsc_site_url: str = "https://crosslisteu.com"

    # Google Analytics 4 — wekelijks marketingrapport (verkeer + kanaalattributie).
    # Hergebruikt de GSC OAuth-client (gsc_client_id/secret); alleen een apart refresh
    # token met de analytics.readonly-scope + het numerieke property-ID zijn nodig.
    # Leeg = rapport draait door op alleen Search Console + signups.
    ga4_property_id: str = ""
    ga4_refresh_token: str = ""
    # Token dat het /analytics dashboard beschermt (?token=...). Leeg = dashboard uit.
    analytics_dashboard_token: str = ""

    # Apify — wekelijkse scrape van de eigen social-profielen (TikTok/Instagram/
    # YouTube/Pinterest) voor per-post prestaties in het marketingrapport.
    # Leeg = social-sectie blijft leeg / 'niet gekoppeld'. De handles zijn de
    # publieke gebruikersnamen; comma-gescheiden override kan via env.
    apify_token: str = ""
    social_tiktok: str = "crosslisteu"
    social_instagram: str = "crosslisteu"
    social_youtube: str = "@ListHub"
    social_pinterest: str = "ListHub"
    social_threads: str = "crosslisteu"

    # Google Ads API — search-volume check before a keyword enters the content queue.
    # Optional: pipeline runs without volume filtering if these are blank.
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    google_ads_login_customer_id: str = ""

    # Best-effort post-publish notification email (non-blocking — publish never waits on this).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""


settings = Settings()
