from __future__ import annotations
import logging
import time
from typing import Optional
import httpx
from supabase import create_client, Client
from backend.config import settings

logger = logging.getLogger(__name__)

_client: Optional[Client] = None
_admin_client: Optional[Client] = None
_auth_client: Optional[Client] = None


def get_db() -> Client:
    """De gewone verbinding: gegevens lezen en schrijven."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def get_admin_db() -> Client:
    """
    Een APARTE verbinding, uitsluitend voor `auth.admin.*`.

    Waarom apart: een Supabase-client onthoudt de laatste sessie. Zodra er ergens
    `sign_in_with_password` of `set_session` op een client gebeurt, stuurt diezelfde
    client daarna het tóken van die gebruiker mee in plaats van de servicesleutel —
    en dan antwoordt Supabase op elke beheerdersactie met "User not allowed".

    Dat is precies wat er gebeurde. Alles liep over één gedeelde verbinding, dus
    één inlog verderop maakte het opzoeken van e-mailadressen kapot. Gevolg:
    27 abonnementen, 22 verlopen proefperiodes, nul verstuurde herinneringen, en
    "e-mailadres wijzigen" dat nooit gewerkt heeft (die logt zichzélf in vlak
    voor de beheerdersactie).

    Op deze verbinding wordt daarom nooit ingelogd. Niet hergebruiken voor iets
    anders.
    """
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(settings.supabase_url, settings.supabase_key)
    return _admin_client


def get_auth_db() -> Client:
    """
    Een aparte verbinding voor alles wat mét een gebruikerssessie werkt:
    registreren, inloggen, wachtwoord zetten. Die mág vervuild raken — daar is hij
    voor. Zo blijven de gegevens- en beheerdersverbinding schoon.
    """
    global _auth_client
    if _auth_client is None:
        _auth_client = create_client(settings.supabase_url, settings.supabase_key)
    return _auth_client


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


# Hoeveel id's er hooguit in één `.in_(...)`-filter mogen.
#
# WAAROM DIT BESTAAT — de duurste fout die dit project heeft gehad.
# PostgREST zet een `.in_("item_id", [...])` als tekst in de URL. Bij een
# account met veel items wordt die URL zó lang dat httpx hem weigert nog vóór
# hij verstuurd wordt: `httpx.InvalidURL: URL component 'query' too long`.
# Gemeten (27-08-2026) met echte item-id's: tot 639 id's gaat goed, vanaf 640
# breekt het. Dat is geen nette foutmelding maar een uitzondering midden in de
# verwerking.
#
# Gevolg bij Egbert Brouwer (2.135 items): élke Marktplaats-scan werd wel
# opgehaald door de extensie én als "klaar" weggeschreven, maar het opslaan
# van de gevonden advertenties knalde hierop stuk. Drie scans op rij leverden
# 2.000 nieuwe advertenties op die nooit ergens landden — het scherm meldde
# "niets nieuws". Ook het boeken van verkopen (polling) lag hierdoor stil.
#
# 200 is ruim onder de grens en wordt elders in de code al gebruikt.
IN_BROK = 200


def fetch_all_in(build_query, kolom: str, waarden, brok: int = IN_BROK,
                 order_by: str = "id", page_size: int = 500) -> list[dict]:
    """Zoals `fetch_all`, maar met een `.in_(kolom, waarden)`-filter dat te
    groot is voor één URL (zie IN_BROK).

    `build_query` krijgt geen argumenten en levert een VERSE query zonder het
    in-filter; dit voegt het per brok zelf toe.
    """
    waarden = list(dict.fromkeys(w for w in (waarden or []) if w is not None))
    if not waarden:
        return []
    rijen: list[dict] = []
    for i in range(0, len(waarden), brok):
        stuk = waarden[i:i + brok]
        rijen.extend(fetch_all(lambda s=stuk: build_query().in_(kolom, s),
                               order_by=order_by, page_size=page_size))
    return rijen


def update_in(build_query, kolom: str, waarden, patch: dict, brok: int = IN_BROK) -> int:
    """Eén update over veel rijen, opgeknipt zodat de URL nooit te lang wordt."""
    waarden = list(dict.fromkeys(w for w in (waarden or []) if w is not None))
    for i in range(0, len(waarden), brok):
        build_query().update(patch).in_(kolom, waarden[i:i + brok]).execute()
    return len(waarden)


async def naast_de_lus(aanroep):
    """Draai één synchrone database-aanroep in een aparte werkdraad.

    De Supabase-client is synchroon. In een `async def` liep elke `.execute()`
    dus rechtstreeks op de lus die de hele server bedient: zolang die aanroep
    duurde, stond álles stil — voor iedere klant tegelijk. Bij een verkoper met
    duizenden advertenties zijn dat seconden per verzoek, en precies daar
    kwamen de 500-fouten vandaan die een import lieten vastlopen.

    Gebruik: `rij = (await naast_de_lus(lambda: db.table("x").select("*").execute())).data`
    """
    import asyncio
    return await asyncio.to_thread(aanroep)
