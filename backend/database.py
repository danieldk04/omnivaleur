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
            # Alleen ná een herhaling, en alleen op de primaire sleutel: dat id
            # is door ons bedacht, dus als dat al bestaat is het onze eigen
            # eerste poging die tóch was aangekomen. Een dubbele SKU is iets
            # heel anders — dat is een bestaand item van de verkoper en moet
            # gewoon gemeld worden.
            if dubbel_is_ok and poging > 0 and "23505" in str(e) and "_pkey" in str(e):
                logger.warning("Rij stond er al na een herhaalde poging — behandeld als gelukt")
                return None
            if not _is_herstelbaar(e) or poging == pogingen - 1:
                raise
            laatste = e
            logger.warning("Databaseverbinding viel weg (%s) — poging %d opnieuw", type(e).__name__, poging + 2)
            time.sleep(0.25 * (poging + 1))
    raise laatste  # type: ignore[misc]


def fetch_all(build_query, order_by: str = "id", page_size: int = 500) -> list[dict]:
    """
    Haal álle rijen op die bij een query horen, pagina voor pagina.

    Een gewone select geeft er hooguit een paar honderd terug en zegt er niets
    over; alles daarboven verdween stilzwijgend. In het dashboard betekende dat
    dat items die wél online stonden onder "To list" belandden. `build_query`
    maakt telkens een verse query (Supabase-builders zijn niet herbruikbaar).
    """
    Er wordt geteld met het aantal rijen dat we écht terugkregen, niet met de
    grootte die we vroegen: de server mag een pagina korter maken dan gevraagd,
    en dan zou "korter dus klaar" halverwege stoppen.
    """
    rijen: list[dict] = []
    offset = 0
    while True:
        pagina = (build_query().order(order_by)
                  .range(offset, offset + page_size - 1).execute().data or [])
        if not pagina:
            break
        rijen.extend(pagina)
        offset += len(pagina)
    return rijen
