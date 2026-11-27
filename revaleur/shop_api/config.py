"""Instellingen van de Revaleur-webshop. Eigen variabelen (alle met REVALEUR_ ervoor), niets gedeeld met Omnivaleur."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REVALEUR_", env_file=".env", extra="ignore")

    supabase_url: str = ""            # het EIGEN Revaleur-Supabaseproject
    supabase_service_key: str = ""
    stripe_secret_key: str = ""       # eigen Stripe-account
    stripe_webhook_secret: str = ""
    resend_api_key: str = ""          # eigen Resend-domein revaleur.com
    mail_van: str = "Daniel van Revaleur <info@revaleur.com>"
    mail_antwoord: str = "info@revaleur.com"
    site_url: str = "https://revaleur.com"
    api_url: str = "https://api.revaleur.com"
    extra_origins: str = ""           # komma-gescheiden, bv. de testdomeinen op Cloudflare Pages
    deploy_hook: str = ""             # Cloudflare Pages deploy hook: site opnieuw bouwen na verkoop
    # De ENIGE verbinding met Omnivaleur (zie docs/koppeling.md)
    omnivaleur_url: str = "https://omnivaleur.com"
    koppeling_geheim: str = ""        # gedeeld geheim voor ondertekende berichten, beide kanten


settings = Settings()
