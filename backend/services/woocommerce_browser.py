"""WooCommerce via de browser van de klant, voor winkels die onze server niet binnenlaten.

WAAROM (10-10-2026, De Juiste Toon). dejuistetoon.eu draait op SiteGround, en
SiteGround's anti-bot geeft het IP van onze server (Railway) een captcha (HTTP
202, kopregel sg-captcha) in plaats van de winkel; gemeten via Daniels eigen
koppelpoging. De klant zelf, in zijn eigen browser op zijn eigen internet, komt
er gewoon in. En WordPress staat verzoeken vanaf omnivaleur.com toe (CORS:
access-control-allow-origin met Authorization erbij, gemeten op zijn winkel).
Een vast IP voor onze server kost een duurder Railway-plan; dat wilde Daniel niet.

HOE. Het dashboard in de browser van de klant is een doorgeefluik: het vraagt
hier steeds of er iets voor zijn winkel klaarligt, voert dat verzoek zelf uit
(fetch met de sleutel van de koppeling) en stuurt het antwoord terug. Aan de
serverkant is dat een httpx-transport (BrowserTransport): WooClient en alles
erboven (scan, import, voorraad, prijs, publiceren, bestellingen) werkt
ongewijzigd, alleen loopt het verzoek via de browser in plaats van rechtstreeks.

WAT ER GEBEURT ALS HET DASHBOARD DICHT IS
  - Verkopen in de winkel: die meldt de WINKEL zelf via een webhook (de winkel
    stuurt naar ons, en dat houdt SiteGround niet tegen). Zie
    api/platforms.woocommerce_webhook en zorg_voor_webhook hieronder.
  - Elders verkocht, product in de winkel op uitverkocht: dat gaat in een
    wachtrij op de koppeling (WACHTRIJ) en gebeurt zodra er weer een dashboard
    open is. Nooit stil laten vallen: dan wordt een stuk twee keer verkocht.
  - Bestellingenronde en automatische import slaan de winkel over zolang er
    geen browser is, in plaats van een storing te melden.

Alles in dit bestand staat in het geheugen van het serverproces. Railway draait
één proces (railway.json: uvicorn zonder --workers); bij een herstart gaat een
lopend verzoek verloren en probeert de aanroeper het zoals bij elke storing.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

ONLINE_S = 45           # zo lang na de laatste vraag van de browser telt hij als open
WACHT_S = 25            # hoe lang één vraag van de browser hooguit openstaat
MAX_PER_KEER = 4        # zoveel verzoeken krijgt de browser tegelijk
EXTRA_WACHT_S = 20      # bovenop de leestijd van het verzoek zelf
WACHTRIJ = "wacht_op_browser"
ONDERHOUD_S = 15 * 60   # webhook nakijken hooguit zo vaak per klant

GEEN_BROWSER_MELDING = ("Your shop only lets Omnivaleur in through your own browser. Open "
                        "Omnivaleur in your browser and keep it open; this happens as soon as it is.")

# Kopregels die de browser zelf mag meesturen. User-Agent en Cookie mag een
# browser niet zetten, en cookies willen we ook niet: alleen de sleutel telt.
_MEE_KOPREGELS = ("authorization", "content-type", "accept")


@dataclass
class _Opdracht:
    id: str
    verzoek: dict
    toekomst: asyncio.Future
    uitgedeeld: bool = False


@dataclass
class _Klant:
    opdrachten: dict = field(default_factory=dict)
    signaal: asyncio.Event = field(default_factory=asyncio.Event)
    luistert: int = 0
    laatst: float = 0.0
    onderhoud: float = 0.0
    # Er staat iets in de wachtrij dat nog niet is geprobeerd. Los van "de
    # browser kwam terug": die overgang kan samenvallen met een onderhoudsronde
    # die nog loopt, en dan bleef de wachtrij liggen (gezien op GitHub tegen een
    # echte WooCommerce, 10-10-2026).
    wachtrij: bool = False


_klanten: dict[str, _Klant] = {}


def _klant(user_id: str) -> _Klant:
    k = _klanten.get(user_id)
    if k is None:
        k = _klanten[user_id] = _Klant()
    return k


def online(user_id: str) -> bool:
    """Is er nu een dashboard van deze klant dat verzoeken doorgeeft?"""
    k = _klanten.get(user_id)
    return bool(k) and (k.luistert > 0 or time.time() - k.laatst < ONLINE_S)


async def wacht_op_browser(user_id: str, seconden: float = 8.0) -> bool:
    """Net na het klikken kan de eerste vraag van het dashboard nog onderweg zijn."""
    eind = time.monotonic() + seconden
    while not online(user_id):
        if time.monotonic() >= eind:
            return False
        await asyncio.sleep(0.25)
    return True


def via_browser(rij: dict | None) -> bool:
    return bool(((rij or {}).get("extra_data") or {}).get("via_browser"))


def bereikbaar(rij: dict | None) -> bool:
    """Kan de server deze winkel nu bereiken (rechtstreeks of via een browser)?"""
    return not via_browser(rij) or online(str((rij or {}).get("user_id") or ""))


async def haal_opdrachten(user_id: str, wacht_s: float | None = None) -> list[dict]:
    """Wat de browser nu moet doen. Wacht tot er iets is, hooguit `wacht_s`."""
    wacht_s = WACHT_S if wacht_s is None else wacht_s
    k = _klant(user_id)
    was_weg = not online(user_id)
    k.luistert += 1
    try:
        if was_weg or k.wachtrij or time.time() - k.onderhoud > ONDERHOUD_S:
            _start_onderhoud(user_id)
        eind = time.monotonic() + wacht_s
        while True:
            open_ = [o for o in k.opdrachten.values() if not o.uitgedeeld and not o.toekomst.done()]
            if open_:
                uit = []
                for o in open_[:MAX_PER_KEER]:
                    o.uitgedeeld = True
                    uit.append({"id": o.id, **o.verzoek})
                return uit
            rest = eind - time.monotonic()
            if rest <= 0:
                return []
            k.signaal.clear()
            try:
                await asyncio.wait_for(k.signaal.wait(), timeout=rest)
            except asyncio.TimeoutError:
                return []
    finally:
        k.luistert -= 1
        k.laatst = time.time()


def lever_antwoord(user_id: str, opdracht_id: str, antwoord: dict) -> bool:
    o = _klant(user_id).opdrachten.get(opdracht_id)
    if not o or o.toekomst.done():
        return False
    o.toekomst.set_result(antwoord or {})
    return True


class BrowserTransport(httpx.AsyncBaseTransport):
    """Een httpx-transport dat het verzoek door de browser van de klant laat doen."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        from backend.platforms.woocommerce import WooFout
        if not online(self.user_id):
            raise WooFout(GEEN_BROWSER_MELDING, "geen_browser")
        inhoud = await request.aread()
        verzoek = {
            "methode": request.method,
            "url": str(request.url),
            "kopregels": {k: v for k, v in request.headers.items() if k.lower() in _MEE_KOPREGELS},
            "inhoud": inhoud.decode("utf-8") if inhoud else None,
        }
        k = _klant(self.user_id)
        o = _Opdracht(secrets.token_hex(8), verzoek, asyncio.get_running_loop().create_future())
        k.opdrachten[o.id] = o
        k.signaal.set()
        tijd = (request.extensions.get("timeout") or {}).get("read") or 60.0
        try:
            # Eerst: haalt een browser het op? Een tabblad dat net dicht ging telt
            # nog even als open (zijn laatste vraag loopt nog), maar haalt niets
            # meer op. Dan is het "geen browser", zodat een afmelding in de
            # wachtrij gaat in plaats van verloren te gaan.
            eind = time.monotonic() + WACHT_S + 5
            while not o.uitgedeeld and not o.toekomst.done():
                if time.monotonic() >= eind:
                    raise WooFout(GEEN_BROWSER_MELDING, "geen_browser")
                await asyncio.sleep(0.2)
            try:
                antwoord = await asyncio.wait_for(asyncio.shield(o.toekomst), timeout=tijd + EXTRA_WACHT_S)
            except asyncio.TimeoutError:
                raise httpx.ReadTimeout("the browser did not answer in time", request=request) from None
        finally:
            k.opdrachten.pop(o.id, None)
        if antwoord.get("fout"):
            # Nooit ConnectError: of het verzoek de winkel bereikte weten we niet,
            # en WooClient herhaalt een POST alleen als het zeker niet aankwam.
            raise httpx.ReadError(f"browser: {str(antwoord['fout'])[:200]}", request=request)
        kop = {str(a).lower(): str(b) for a, b in (antwoord.get("kopregels") or {}).items()}
        return httpx.Response(status_code=int(antwoord.get("status") or 0) or 599,
                              headers=kop, content=(antwoord.get("tekst") or "").encode("utf-8"),
                              request=request)


# ── Webhook: de winkel meldt zelf een bestelling ─────────────────────────

WEBHOOK_TOPICS = ("order.created", "order.updated")
WEBHOOK_NAAM = "Omnivaleur sales"
WEBHOOK_BASIS = "https://omnivaleur.com/api/platforms/woocommerce/webhook/"


def webhook_url(token: str) -> str:
    return WEBHOOK_BASIS + token


def handtekening_klopt(geheim: str, inhoud: bytes, handtekening: str | None) -> bool:
    """WooCommerce tekent met base64(HMAC-SHA256(inhoud, geheim))
    (WC_Webhook::generate_signature)."""
    if not (geheim and handtekening):
        return False
    goed = base64.b64encode(hmac.new(geheim.encode(), inhoud, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(goed, handtekening.strip())


async def _lees_rij(db, user_id: str) -> dict | None:
    from backend.database import naast_de_lus
    from backend.platforms.woocommerce import PLATFORM
    rij = ((await naast_de_lus(lambda: db.table("platform_credentials").select("*")
            .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
    return rij[0] if rij else None


async def _schrijf_extra(db, user_id: str, wijzig) -> dict:
    """extra_data opnieuw lezen vlak voor het schrijven: andere routines schrijven ook."""
    from backend.database import naast_de_lus
    from backend.platforms.woocommerce import PLATFORM
    rij = await _lees_rij(db, user_id)
    extra = dict((rij or {}).get("extra_data") or {})
    nieuw = wijzig(extra)
    await naast_de_lus(lambda: db.table("platform_credentials").update({"extra_data": nieuw})
                       .eq("user_id", user_id).eq("platform", PLATFORM).execute())
    return nieuw


async def zorg_voor_webhook(db, user_id: str) -> str:
    """Zorg dat de winkel bestellingen aan ons meldt. Geeft wat er gebeurde.

    WooCommerce zet een webhook stil op 'disabled' na meer dan vijf mislukte
    afleveringen achter elkaar; daarom kijken we elke keer dat er een browser
    is ook of hij nog aan staat, en zetten hem anders weer aan."""
    from backend.platforms.woocommerce import client_uit

    def _sleutels(extra: dict) -> dict:
        extra.setdefault("webhook_token", secrets.token_hex(16))
        extra.setdefault("webhook_geheim", secrets.token_hex(24))
        return extra

    rij = await _lees_rij(db, user_id)
    extra = (rij or {}).get("extra_data") or {}
    if not extra.get("webhook_token") or not extra.get("webhook_geheim"):
        extra = await _schrijf_extra(db, user_id, _sleutels)
        rij = {**(rij or {}), "extra_data": extra}
    client = client_uit(rij)
    if not client:
        return "geen koppeling"
    url = webhook_url(extra["webhook_token"])
    _, bestaand, _ = await client.verzoek("GET", "wc/v3/webhooks", {"per_page": 100})
    eigen = {w.get("topic"): w for w in (bestaand or []) if isinstance(w, dict)
             and w.get("delivery_url") == url}
    gedaan = []
    for topic in WEBHOOK_TOPICS:
        w = eigen.get(topic)
        if w is None:
            await client.verzoek("POST", "wc/v3/webhooks", body={
                "name": WEBHOOK_NAAM, "topic": topic, "delivery_url": url,
                "secret": extra["webhook_geheim"], "status": "active"})
            gedaan.append(f"{topic} aangemaakt")
        elif w.get("status") != "active":
            await client.verzoek("PUT", f"wc/v3/webhooks/{w['id']}", body={"status": "active"})
            gedaan.append(f"{topic} weer aangezet (stond op {w.get('status')})")
    if gedaan:
        logger.info("woocommerce-browser: webhook %s: %s", user_id[:8], ", ".join(gedaan))
    return ", ".join(gedaan) or "in orde"


# ── Wachtrij: wat moet gebeuren zodra er weer een browser is ─────────────

async def onthoud_uitverkocht(db, user_id: str, product_id: str) -> None:
    """Elders verkocht terwijl er geen browser was: later op uitverkocht zetten."""
    def _erbij(extra: dict) -> dict:
        lijst = [p for p in (extra.get(WACHTRIJ) or []) if p != str(product_id)]
        extra[WACHTRIJ] = lijst + [str(product_id)]
        return extra
    await _schrijf_extra(db, user_id, _erbij)
    _klant(user_id).wachtrij = True
    logger.info("woocommerce-browser: %s product %s wacht op een browser om uitverkocht te gaan",
                user_id[:8], product_id)


async def werk_wachtrij_af(db, user_id: str) -> int:
    """De uitgestelde 'op uitverkocht' uitvoeren. Geeft hoeveel er lukten."""
    from backend.platforms.woocommerce import client_uit, zet_uitverkocht
    rij = await _lees_rij(db, user_id)
    lijst = list(((rij or {}).get("extra_data") or {}).get(WACHTRIJ) or [])
    client = client_uit(rij) if rij else None
    if not client:
        return 0
    gelukt = []
    for pid in lijst:
        try:
            # Rechtstreeks, niet via delete_listing: die zou een mislukking weer
            # in de wachtrij zetten en hier als gelukt tellen.
            await zet_uitverkocht(client, pid)
            gelukt.append(pid)
        except Exception as e:  # noqa: BLE001 — volgende keer opnieuw
            logger.warning("woocommerce-browser: uitgesteld uitverkocht %s/%s mislukt: %s",
                           user_id[:8], pid, e)
            if not online(user_id):
                break
    if len(gelukt) < len(lijst):
        _klant(user_id).wachtrij = True     # volgende ronde van de browser opnieuw
    if gelukt:
        await _schrijf_extra(db, user_id, lambda extra: {
            **extra, WACHTRIJ: [p for p in (extra.get(WACHTRIJ) or []) if p not in gelukt]})
        logger.info("woocommerce-browser: %s %d uitgestelde product(en) op uitverkocht gezet",
                    user_id[:8], len(gelukt))
    return len(gelukt)


_onderhoud_bezig: set[str] = set()


def _start_onderhoud(user_id: str) -> None:
    """De browser is er (weer): wachtrij afwerken en webhook nakijken, op de achtergrond."""
    k = _klant(user_id)
    if user_id in _onderhoud_bezig:
        k.wachtrij = True       # deze aanleiding niet kwijtraken: volgende ronde opnieuw
        return
    _onderhoud_bezig.add(user_id)

    async def _doe():
        from backend.database import get_db
        try:
            await asyncio.sleep(1)      # de browser moet eerst echt luisteren
            db = get_db()
            k.wachtrij = False
            rij = await _lees_rij(db, user_id)
            if not via_browser(rij):
                return
            if (rij.get("extra_data") or {}).get(WACHTRIJ):
                await werk_wachtrij_af(db, user_id)
            if time.time() - k.onderhoud > ONDERHOUD_S:
                await zorg_voor_webhook(db, user_id)
                k.onderhoud = time.time()
        except Exception as e:  # noqa: BLE001 — volgende keer opnieuw
            logger.warning("woocommerce-browser: onderhoud voor %s mislukt: %s", user_id[:8], e)
        finally:
            _onderhoud_bezig.discard(user_id)

    houd_vast(asyncio.get_running_loop().create_task(_doe()))


_taken: set = set()


def houd_vast(taak: asyncio.Task) -> None:
    """Een achtergrondtaak waar niemand op wacht moet ergens bewaard worden,
    anders kan Python hem halverwege opruimen (asyncio.create_task, documentatie)."""
    _taken.add(taak)
    taak.add_done_callback(_taken.discard)
