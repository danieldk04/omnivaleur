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


settings = Settings()
