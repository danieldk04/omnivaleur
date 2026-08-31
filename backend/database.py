from __future__ import annotations
import logging
import ssl
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
    Een gedeelde verbinding voor auth-aanroepen die GEEN sessie achterlaten.

    In de praktijk is dat er nog maar één: `auth.get_user(token)`, waar het
    bewijs expliciet wordt meegegeven. Die staat op elk binnenkomend verzoek, dus
    daar telkens een nieuwe verbinding voor opzetten zou zonde zijn.

    ALLES wat inlogt, ververst of een wachtwoord zet hoort hier NIET. Zie
    `verse_auth_client()` hieronder voor waarom dat een gebruiker zijn account
    kostte.
    """
    global _auth_client
    if _auth_client is None:
        _auth_client = create_client(settings.supabase_url, settings.supabase_key)
    return _auth_client


def verse_auth_client() -> Client:
    """
    Een GLOEDNIEUWE verbinding, voor precies één gebruiker, voor precies één
    verzoek. Nooit hergebruiken en nooit ergens bewaren.

    DE DUURSTE FOUT IN DIT BESTAND — hier is een klant zijn account door
    kwijtgeraakt.

    Een Supabase-client onthoudt de laatste sessie. `sign_in_with_password`,
    `refresh_session` en `set_session` schrijven die sessie in de client; en
    `auth.update_user({"password": ...})` kijkt NIET naar wie hem aanroept maar
    naar díé opgeslagen sessie (zie `update_user` in supabase_auth: het pakt
    `self.get_session()`).

    Alles liep over één gedeelde verbinding. Elke inlog en elke tokenvernieuwing
    van welke klant dan ook — en dat zijn er tientallen per minuut, want elke
    extensie ververst zelf — overschreef die sessie. Klikte er op dat moment
    iemand anders zijn "wachtwoord vergeten"-link af, dan zette Supabase dat
    nieuwe wachtwoord op de account van de laatste inlogger. Die kon daarna niet
    meer inloggen, met "Invalid email or password", zonder ooit iets gevraagd of
    veranderd te hebben. Aantoonbaar gebeurd bij info@papas-plectrums.nl op
    28-08-2026 om 07:51:07 UTC, tien seconden na zijn eigen geslaagde inlog: zijn
    account werd bijgewerkt terwijl hij zelf nooit een herstelmail had
    aangevraagd (`recovery_sent_at` leeg). Een wachtwoordwijziging trekt
    bovendien alle lopende sessies in — vandaar dat hij er eerst uit vloog en er
    daarna helemaal niet meer in kwam.

    Een verse verbinding heeft een lege sessie en wordt na het verzoek
    weggegooid. Dan kan geen enkele gebruiker de sessie van een ander raken.
    """
    return create_client(settings.supabase_url, settings.supabase_key)


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
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    # Valt de verbinding weg tijdens de beveiligde handdruk, dan komt er geen
    # httpx-fout maar een kale ssl.SSLEOFError: "EOF occurred in violation of
    # protocol". Die stond hier niet bij, dus werd zo'n hik NIET herhaald en
    # kwam hij als harde storing bij de verkoper op het scherm. Jaap Kroon zag
    # hem op 28-08-2026 letterlijk zo staan bij het verversen van een
    # advertentie.
    ssl.SSLError,
)

# Sommige lagen geven de oorzaak niet door als uitzondering maar alleen als
# tekst. Dan is de tekst het enige wat we hebben.
_HERSTELBARE_TEKST = (
    "eof occurred in violation of protocol",
    "server disconnected",
    "connection reset by peer",
    "connection aborted",
)


def _is_een_gateway_pagina(tekst: str) -> bool:
    """Een HTML-pagina waar JSON hoort te staan is nooit een echte databasefout.

    Supabase staat achter Cloudflare. Hapert die ertussen, dan komt er een
    HTML-foutpagina terug en maakt de client daar "JSON could not be generated,
    code 400" van — een fout die eruitziet als een kapotte query, maar het niet
    is. Op 30-08-2026 waren dat er negen in een half uur, op het ophalen van de
    advertentielijst en op de wachtrij van de extensie. PostgREST antwoordt altijd
    met JSON, dus HTML betekent per definitie: het verzoek is de database nooit
    binnengekomen. Opnieuw proberen mag.
    """
    return "json could not be generated" in tekst and ("<html" in tekst or "cloudflare" in tekst)


# ─────────────────────────────────────────────────────────────────────────────
# HET PROJECT OP SLOT — ALARM, NIET AFWACHTEN
#
# WAAROM DIT ER IS (31-08-2026). Supabase zette het hele project op slot wegens
# overschreden verkeer: elk verzoek kreeg een 402 met "Service for this project
# is restricted". Inloggen gaf 503, de blog 500, de mailagent viel stil. Wij
# hoorden dat niet van onze eigen server maar van een klant, die 's ochtends
# mailde dat inloggen niet lukte. Dat is de verkeerde volgorde.
#
# Dit is bewust géén herstelbare fout: opnieuw proberen helpt niet en maakt het
# alleen maar erger. Het is een toestand die iemand moet oplossen, en dus een
# alarm. Hooguit één keer per QUOTA_STILTE_UREN, anders wordt het bij duizenden
# verzoeken per uur zelf een storing.
QUOTA_STILTE_UREN = 4
_QUOTA_GEMELD_OP = 0.0
_QUOTA_SLOT = threading.Lock()


def _is_quotastoring(exc: BaseException) -> str:
    """De tekst van de blokkade, of "" als dit iets anders is."""
    huidige: BaseException | None = exc
    while huidige is not None:
        tekst = str(huidige)
        laag = tekst.lower()
        if "restricted due to the following violations" in laag or (
                "402" in laag and "quota" in laag):
            return tekst[:400]
        huidige = huidige.__cause__ or huidige.__context__
    return ""


def meld_quotastoring(exc: BaseException) -> None:
    """Eén mail naar Daniel zodra het project op slot staat. Faalt dit, dan zwijgt het."""
    global _QUOTA_GEMELD_OP
    reden = _is_quotastoring(exc)
    if not reden:
        return
    with _QUOTA_SLOT:
        if time.time() - _QUOTA_GEMELD_OP < QUOTA_STILTE_UREN * 3600:
            return
        _QUOTA_GEMELD_OP = time.time()
    logger.error("SUPABASE HEEFT HET PROJECT OP SLOT GEZET: %s", reden)
    try:
        from backend.services.email import send_email
        send_email(
            "Omnivaleur ligt eruit — Supabase heeft het project op slot gezet",
            "Supabase weigert elk verzoek omdat het gratis plan op is. Voor je "
            "klanten betekent dit dat inloggen, publiceren en het dashboard geen "
            "van alle werken.\n\n"
            f"Wat Supabase teruggeeft:\n  {reden}\n\n"
            "Wat je kunt doen:\n"
            "  1. Wachten tot je factuurperiode omslaat — dan gaat de blokkade er "
            "vanzelf af en kost het niets.\n"
            "  2. In Supabase het plan opwaarderen; dan is het meteen opgelost.\n\n"
            "Kijk daarna op supabase.com/dashboard bij Usage welke meter vol liep.\n\n"
            f"Je krijgt hooguit elke {QUOTA_STILTE_UREN} uur een herinnering.\n")
    except Exception:  # noqa: BLE001 — een mislukt alarm mag nooit iets blokkeren
        logger.exception("Kon de quotastoring niet mailen")


def _is_herstelbaar(exc: BaseException) -> bool:
    # Een project dat op slot staat is niet "even weg": herhalen helpt niet en
    # verbruikt alleen nog meer van precies datgene wat op is.
    if _is_quotastoring(exc):
        meld_quotastoring(exc)
        return False
    huidige: BaseException | None = exc
    while huidige is not None:
        if isinstance(huidige, _HERSTELBAAR):
            return True
        tekst = str(huidige).lower()
        if any(fragment in tekst for fragment in _HERSTELBARE_TEKST) or _is_een_gateway_pagina(tekst):
            return True
        huidige = huidige.__cause__ or huidige.__context__
    return False


# ─────────────────────────────────────────────────────────────────────────────
# ELKE LEESACTIE OVERLEEFT EEN WEGGEVALLEN VERBINDING — OOK ZONDER WRAPPER
#
# WAAROM DIT ER IS (30-08-2026). `execute_with_retry` bestond al, maar verreweg
# de meeste plekken in de code roepen gewoon `.execute()` aan: zo'n tweehonderd
# stuks. Viel de verbinding daar weg, dan vloog de fout ongevangen omhoog en
# kreeg de gebruiker "HTTP 500: Internal Server Error" — precies het scherm
# waar Amanda een foto van stuurde. Binnen een kwartier na het inschakelen van
# de foutcodes stonden er twee van deze fouten in de lijst, allebei op
# /api/jobs/relist-status, allebei een verbroken verbinding met Supabase.
#
# Tweehonderd plekken één voor één omzetten is vragen om fouten. Daarom hangt de
# herhaling hier, op de bouwer die Supabase teruggeeft bij een SELECT.
#
# ALLEEN LEZEN. Schrijfacties (insert, update, upsert, delete) geven een ANDERE
# bouwer terug en blijven dus onaangeraakt. Dat is opzet: een leesactie opnieuw
# doen is gratis, maar een insert blind herhalen na een weggevallen antwoord
# maakt een tweede rij — en dus een tweede advertentie. Die les staat al in
# `dubbel_is_ok` hieronder.
_ORIGINEEL_SELECT_EXECUTE = None
try:
    from postgrest import SyncSelectRequestBuilder as _SelectBouwer

    _ORIGINEEL_SELECT_EXECUTE = _SelectBouwer.execute

    def _lezen_met_herkansing(self, *a, **kw):
        laatste: BaseException | None = None
        for poging in range(3):
            try:
                return _ORIGINEEL_SELECT_EXECUTE(self, *a, **kw)
            except Exception as e:  # noqa: BLE001
                if not _is_herstelbaar(e) or poging == 2:
                    raise
                laatste = e
                logger.warning("Leesactie viel weg (%s) — poging %d opnieuw",
                               type(e).__name__, poging + 2)
                time.sleep(0.25 * (poging + 1))
        raise laatste  # type: ignore[misc]

    _SelectBouwer.execute = _lezen_met_herkansing
except Exception:  # noqa: BLE001 — nooit de start van de server blokkeren
    logger.exception("Kon de herhaling op leesacties niet installeren")


def _eenmaal_uitvoeren(query):
    """Eén poging, zonder de herhaling hierboven — anders herhaalt
    `execute_with_retry` een leesactie negen keer in plaats van drie."""
    if _ORIGINEEL_SELECT_EXECUTE is not None and isinstance(query, _SelectBouwer):
        return _ORIGINEEL_SELECT_EXECUTE(query)
    return query.execute()


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
            return _eenmaal_uitvoeren(query)
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


class AuthTijdelijkOnbereikbaar(Exception):
    """Supabase kon niet beantwoord worden — dat is GEEN afgekeurd wachtwoord."""


def auth_met_herkansing(aanroep, pogingen: int = 3):
    """
    Voer één auth-aanroep uit en probeer opnieuw als de verbinding wegviel.

    WAAROM DIT BESTAAT — dit heeft klanten hun toegang gekost.
    Supabase verbreekt af en toe een hergebruikte verbinding (zie _HERSTELBAAR
    hierboven; voor gegevens werd dat allang opgevangen door execute_with_retry).
    Bij auth gebeurde dat niet, en erger: elke fout werd daar vertaald naar "je
    sessie is verlopen" of "Invalid email or password". Eén weggevallen
    verbinding zag er voor de verkoper dus uit als een verkeerd wachtwoord.

    Gevolg bij Egbert Brouwer (info@papas-plectrums.nl, 28-08-2026): hij vloog er
    een paar keer uit vlak na het inloggen — het dashboard leest die 401 als
    "opnieuw inloggen" en gooit je eruit — en kreeg daarna op het inlogscherm
    "Invalid email or password" te zien terwijl zijn wachtwoord gewoon goed was.

    Lukt het na de herkansingen nog steeds niet, dan volgt
    AuthTijdelijkOnbereikbaar. Dat moet naar buiten als "even niet bereikbaar",
    nooit als een afgewezen inlog: op een afgewezen inlog gooit het dashboard je
    eruit en wist de extensie haar inlogbewijs.
    """
    laatste: BaseException | None = None
    for poging in range(pogingen):
        try:
            return aanroep()
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status", None)
            # Alleen opnieuw proberen bij een weggevallen verbinding of een 5xx
            # van Supabase zelf. Alles daarbuiten — verkeerd wachtwoord, verlopen
            # bewijs, te veel pogingen — is een écht antwoord en moet ongemoeid
            # door naar de aanroeper.
            tijdelijk = _is_herstelbaar(e) or (isinstance(status, int) and status >= 500)
            if not tijdelijk or poging == pogingen - 1:
                if not tijdelijk:
                    raise
            laatste = e
            logger.warning("Auth-aanroep viel weg (%s) — poging %d opnieuw",
                           type(e).__name__, poging + 2)
            time.sleep(0.25 * (poging + 1))
    raise AuthTijdelijkOnbereikbaar(str(laatste)) from laatste


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
        # execute_with_retry: Supabase verbreekt af en toe een hergebruikte
        # verbinding (RemoteProtocolError). Bij een lezing die over tien pagina's
        # loopt is de kans daarop tien keer zo groot, en zonder herkansing valt
        # de hele aanroep om op iets wat een browser zelf stil zou wegwerken.
        pagina = (execute_with_retry(build_query().order(order_by)
                  .range(offset, offset + page_size - 1)).data or [])
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


async def naast_de_lus(aanroep, herkans: bool = False):
    """Draai één synchrone database-aanroep in een aparte werkdraad.

    De Supabase-client is synchroon. In een `async def` liep elke `.execute()`
    dus rechtstreeks op de lus die de hele server bedient: zolang die aanroep
    duurde, stond álles stil — voor iedere klant tegelijk. Bij een verkoper met
    duizenden advertenties zijn dat seconden per verzoek, en precies daar
    kwamen de 500-fouten vandaan die een import lieten vastlopen.

    Gebruik: `rij = (await naast_de_lus(lambda: db.table("x").select("*").execute())).data`

    HERKANSING — alleen als de aanroeper hem aanzet, en dat is met opzet.
    Tot 28-08-2026 herhaalde alleen execute_with_retry een weggevallen
    verbinding; alles wat via deze weg loopt deed dat niet, en één hik
    halverwege een verversing was meteen een harde fout.

    Maar blind herhalen mag hier NIET standaard. Valt de verbinding weg terwijl
    het ANTWOORD onderweg is, dan is de rij misschien allang aangemaakt en maakt
    een tweede poging er nog een. Bij een opdracht in de wachtrij betekent dat
    een tweede advertentie. Daarom staat `herkans` standaard uit: zet hem alleen
    aan voor aanroepen die je twee keer mag doen (lezen, of een update die
    hetzelfde resultaat geeft). Voor een insert hoort execute_with_retry met een
    zelfbedacht id en `dubbel_is_ok=True` — zie crosslist._exec.
    """
    import asyncio

    if not herkans:
        return await asyncio.to_thread(aanroep)

    laatste: BaseException | None = None
    for poging in range(3):
        try:
            return await asyncio.to_thread(aanroep)
        except Exception as e:  # noqa: BLE001 - alleen verbindingsfouten herhalen
            if not _is_herstelbaar(e) or poging == 2:
                raise
            laatste = e
            logger.warning(
                "Verbinding viel weg (%s) — poging %d opnieuw", type(e).__name__, poging + 2)
            await asyncio.sleep(0.25 * (poging + 1))
    raise laatste  # type: ignore[misc]
