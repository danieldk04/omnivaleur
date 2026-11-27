"""Verbinding met het Revaleur-Supabaseproject (niet dat van Omnivaleur)."""
from supabase import Client, create_client

from .config import settings

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        if not (settings.supabase_url and settings.supabase_service_key):
            raise RuntimeError("REVALEUR_SUPABASE_URL / REVALEUR_SUPABASE_SERVICE_KEY ontbreken")
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client
