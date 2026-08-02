from __future__ import annotations
import logging
import time
from typing import Optional
import httpx
from supabase import create_client, Client
from backend.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


# Supabase houdt verbindingen open om ze te hergebruiken. Sluit de andere kant
# er eentje terwijl wij hem net pakken, dan mislukt dat verzoek met "Server
# disconnected" — zonder dat er iets mis is met de gegevens. Dat gebeurt af en
# toe, en trof dus willekeurige acties: één keer het aanmaken van een item, een
# andere keer een lijst ophalen. Opnieuw proberen op een verse verbinding lost
# het op; het is dezelfde fout die een browser zelf ook stil wegwerkt.
_HERSTELBAAR = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)


def _is_herstelbaar(exc: BaseException) -> bool:
    huidige: BaseException | None = exc
    while huidige is not None:
        if isinstance(huidige, _HERSTELBAAR):
            return True
        huidige = huidige.__cause__ or huidige.__context__
    return False


def execute_with_retry(query, pogingen: int = 3, dubbel_is_ok: bool = False):
    """
    Voer een Supabase-query uit en probeer opnieuw als de verbinding wegviel.

    `dubbel_is_ok` is voor inserts: het id wordt vooraf door ons bepaald, dus
    als de eerste poging tóch was aangekomen loopt de herhaling op een dubbele
    sleutel. Dat betekent dat de rij er al staat — geen fout dus.
    """
    laatste: BaseException | None = None
    for poging in range(pogingen):
        try:
            return query.execute()
        except Exception as e:  # noqa: BLE001 - alleen verbindingsfouten herhalen
            if dubbel_is_ok and "23505" in str(e):
                logger.warning("Rij stond er al na een herhaalde poging — behandeld als gelukt")
                return None
            if not _is_herstelbaar(e) or poging == pogingen - 1:
                raise
            laatste = e
            logger.warning("Databaseverbinding viel weg (%s) — poging %d opnieuw", type(e).__name__, poging + 2)
            time.sleep(0.25 * (poging + 1))
    raise laatste  # type: ignore[misc]
