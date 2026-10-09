"""WooCommerce: de winkel van de verkoper lezen en bijwerken via de REST API.

WAAROM (09-10-2026, Mikkis en eerder Borstelbeer, Vianen Telecom, De Juiste Toon)
WooCommerce is bij onze leads drie keer zo gewoon als Shopify (gemeten over 792
Marktplaats-verkopers: 154 tegen 48). Wie zijn voorraad daar heeft staan wil hem
vanuit de winkel op Marktplaats en de rest krijgen, en een verkoop in de winkel
moet het artikel elders weghalen.

WAT ANDERS IS DAN SHOPIFY, EN WAAROM DIT BESTAND ZO VOORZICHTIG IS
Elke WooCommerce-winkel draait op eigen hosting. GEMETEN op 100 WooCommerce-
webshops uit de leadlijst (09-10-2026): 76 gaven netjes WooCommerce's eigen
401-antwoord (bereikbaar, sleutel nodig), 21 hadden een WordPress-API zonder
WooCommerce-routes (uitgezet of verborgen door een plugin), 3 gaven geen
antwoord of een PHP-fout. Mikkis (2.504 producten) verbrak de verbinding toen
we snel achter elkaar bladerden. Daarom:
  * het API-adres wordt ontdekt via WordPress' eigen Link-kop, niet geraden
    (een winkel zonder mooie permalinks heeft /?rest_route= in plaats van /wp-json);
  * drie manieren van inloggen, in deze volgorde: de sleutel in de kopregel
    (https), de sleutel in het adres (https, als de hosting de kopregel weggooit),
    OAuth 1.0a (alleen http, zo eist WooCommerce het);
  * bladeren met een pauze en herhaalpogingen bij een verbroken verbinding,
    429 of 5xx;
  * een geblokkeerd verzoek (HTML van een firewall in plaats van JSON) wordt
    als zodanig gemeld, met wat de winkelier eraan kan doen.

NOOIT WISSEN. Een verkoop elders zet het WooCommerce-product op uitverkocht in
plaats van het te verwijderen. De winkel houdt zo zijn productpagina, foto's en
vindbaarheid, en een vergissing is met één klik terug te draaien. Wissen niet.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import json
import logging
import re
import secrets
import time
from typing import Optional
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

PLATFORM = "woocommerce"
PER_PAGINA = 100            # het maximum dat WooCommerce per keer toestaat
MAX_PAGINAS = 200           # 20.000 producten: ruim, maar nooit eindeloos
PAUZE_S = 0.6               # tussen twee pagina's; Mikkis verbrak de verbinding zonder
POGINGEN = 4
WACHT_S = (2, 5, 12)        # tussen de herhaalpogingen

UA = "Omnivaleur/1.0 (+https://omnivaleur.com)"


class WooFout(RuntimeError):
    """Een fout die de winkelier kan lezen. `soort` zegt de code welke het is."""

    def __init__(self, melding: str, soort: str = "onbekend", status: int | None = None):
        super().__init__(melding)
        self.soort = soort
        self.status = status


# ── Winkeladres ──────────────────────────────────────────────────────────

def normaliseer_adres(invoer: str) -> str:
    """Wat de verkoper intypt, als https://host[/pad]. Leeg als het geen adres is.

    Verkopers plakken van alles: 'mikkis.nl', 'www.mikkis.nl/shop/', de hele
    beheer-URL. Een pad blijft staan behalve wp-admin en alles daarachter, want
    WordPress kan in een submap staan (example.nl/winkel)."""
    s = (invoer or "").strip()
    if not s:
        return ""
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s
    deel = urlsplit(s)
    host = (deel.hostname or "").lower()
    if not host or "." not in host or " " in host:
        return ""
    pad = re.split(r"/(wp-admin|wp-login\.php|wp-json|product|shop|winkel)(/|$)", deel.path or "")[0]
    pad = pad.rstrip("/")
    poort = f":{deel.port}" if deel.port else ""
    return urlunsplit(((deel.scheme or "https").lower(), host + poort, pad, "", ""))


def _api_url(api_root: str, route: str, params: dict | None = None) -> str:
    """Volledig adres van een route, voor beide vormen van de API-wortel."""
    route = route.lstrip("/")
    params = {k: v for k, v in (params or {}).items() if v is not None}
    if "rest_route=" in api_root:
        deel = urlsplit(api_root)
        q = dict(parse_qsl(deel.query, keep_blank_values=True))
        q["rest_route"] = "/" + route
        q.update({k: str(v) for k, v in params.items()})
        return urlunsplit((deel.scheme, deel.netloc, deel.path or "/", urlencode(q, safe="/,"), ""))
    basis = api_root if api_root.endswith("/") else api_root + "/"
    return basis + route + (("?" + urlencode({k: str(v) for k, v in params.items()}, safe=",")) if params else "")


def site_van_api(api_root: str) -> str:
    """De WordPress-site bij een API-wortel."""
    if "rest_route=" in api_root:
        d = urlsplit(api_root)
        return urlunsplit((d.scheme, d.netloc, (d.path or "/").rstrip("/"), "", ""))
    return re.sub(r"/wp-json/?$", "", api_root.rstrip("/") + "/").rstrip("/")


def _link_api_root(link_kop: str | None) -> str | None:
    for deel in (link_kop or "").split(","):
        if 'rel="https://api.w.org/"' in deel:
            m = re.search(r"<([^>]+)>", deel)
            if m:
                return m.group(1)
    return None


async def ontdek_api(adres: str, client=None) -> str:
    """De API-wortel van deze WordPress-site, of WooFout als het geen WordPress is.

    WordPress zet het adres in een Link-kop op elke pagina. Zo werkt het ook bij
    een site in een submap en bij een site zonder mooie permalinks."""
    import httpx

    eigen = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0),
                                         follow_redirects=True, headers={"User-Agent": UA})
    try:
        kandidaten = []
        for poging in range(2):
            try:
                r = await client.head(adres + "/")
                if r.status_code >= 400 or not _link_api_root(r.headers.get("link")):
                    r = await client.get(adres + "/")
                gevonden = _link_api_root(r.headers.get("link"))
                if gevonden:
                    return gevonden
                kandidaten.append(str(r.url))
                break
            except (httpx.TransportError,) as e:
                if poging:
                    raise WooFout(f"Could not reach {adres}. Check the address and try again.",
                                  "onbereikbaar") from e
                await asyncio.sleep(2)
        # Geen Link-kop (sommige caches halen hem weg): de gewone plek proberen.
        for root in (adres + "/wp-json/", adres + "/?rest_route=/"):
            try:
                r = await client.get(root)
                if r.status_code == 200 and "namespaces" in (r.text or "")[:5000]:
                    return root
            except httpx.TransportError:
                continue
        raise WooFout(f"{adres} doesn't look like a WordPress site. Enter the address of your "
                      f"WooCommerce shop, for example yourshop.nl.", "geen_wordpress")
    finally:
        if eigen:
            await client.aclose()


# ── Inloggen ─────────────────────────────────────────────────────────────

def _pct(s: str) -> str:
    return quote(str(s), safe="~-._")


def oauth1_params(methode: str, url: str, ck: str, cs: str,
                  nonce: str | None = None, tijd: int | None = None) -> dict:
    """De OAuth 1.0a-velden die WooCommerce over http eist (one-legged, HMAC-SHA256).

    WooCommerce (class-wc-rest-authentication.php) bouwt de handtekening over de
    url zonder query, plus alle query- en oauth-velden, gesorteerd; de sleutel is
    het geheim met een '&' erachter."""
    deel = urlsplit(url)
    basis = urlunsplit((deel.scheme, deel.netloc, deel.path, "", ""))
    velden = dict(parse_qsl(deel.query, keep_blank_values=True))
    oauth = {
        "oauth_consumer_key": ck,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(tijd or int(time.time())),
    }
    alles = {**velden, **oauth}
    paren = "%26".join(f"{_pct(_pct(k))}%3D{_pct(_pct(v))}" for k, v in sorted(alles.items()))
    tekst = f"{methode.upper()}&{_pct(basis)}&{paren}"
    sig = hmac.new((cs + "&").encode(), tekst.encode(), hashlib.sha256).digest()
    oauth["oauth_signature"] = base64.b64encode(sig).decode()
    return oauth


def _met_auth(methode: str, url: str, ck: str, cs: str, modus: str) -> tuple[str, dict]:
    """Adres en kopregels voor deze inlogmodus."""
    if modus == "basic":
        tok = base64.b64encode(f"{ck}:{cs}".encode()).decode()
        return url, {"Authorization": f"Basic {tok}"}
    if modus == "query":
        sep = "&" if "?" in url else "?"
        return url + sep + urlencode({"consumer_key": ck, "consumer_secret": cs}), {}
    if modus == "oauth1":
        extra = oauth1_params(methode, url, ck, cs)
        sep = "&" if "?" in url else "?"
        return url + sep + urlencode(extra), {}
    raise ValueError(f"onbekende inlogmodus {modus}")


def modi_voor(api_root: str) -> tuple[str, ...]:
    return ("basic", "query") if api_root.lower().startswith("https://") else ("oauth1",)


def _lees_fout(r) -> WooFout:
    """Een weigering, vertaald naar wat de winkelier kan doen."""
    ct = (r.headers.get("content-type") or "").lower()
    code = ""
    if "json" in ct:
        try:
            code = str((r.json() or {}).get("code") or "")
        except ValueError:
            code = ""
    if r.status_code in (401, 403) and (code.startswith("woocommerce_rest") or code.startswith("rest_")):
        return WooFout("WooCommerce did not accept the key. Connect again, and choose "
                       "Read/Write when WooCommerce asks.", "sleutel", r.status_code)
    if r.status_code == 404 and code == "rest_no_route":
        return WooFout("Your site answers, but the WooCommerce API is switched off or hidden. "
                       "Check that WooCommerce is active and that no security plugin blocks "
                       "the REST API (/wp-json/wc/v3).", "geen_woo_api", 404)
    if r.status_code in (401, 403, 406, 429, 503) and "json" not in ct:
        server = (r.headers.get("server") or "").lower()
        door = "Cloudflare" if "cloudflare" in server or r.headers.get("cf-ray") else "a firewall or security plugin"
        return WooFout(f"Your shop's {door} blocked our request (HTTP {r.status_code}). Allow "
                       f"requests to /wp-json/wc/v3 from Omnivaleur, or ask your host to.",
                       "geblokkeerd", r.status_code)
    return WooFout(f"Your shop answered HTTP {r.status_code}. Try again in a moment.",
                   "serverfout", r.status_code)


# ── De client ────────────────────────────────────────────────────────────

class WooClient:
    """Eén winkel. `modus` komt uit de koppeling (zie controleer_sleutels)."""

    def __init__(self, api_root: str, ck: str, cs: str, modus: str = "basic"):
        self.api_root = api_root
        self.ck, self.cs, self.modus = ck, cs, modus
        self.modus_gewijzigd = False

    async def verzoek(self, methode: str, route: str, params: dict | None = None,
                      body: dict | None = None, timeout: float = 60.0, client=None):
        """Eén verzoek met herhaalpogingen. Geeft (status, json, kopregels)."""
        import httpx

        eigen = client is None
        client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15.0),
                                             follow_redirects=False, headers={"User-Agent": UA})
        laatste: Exception | None = None
        try:
            for poging in range(POGINGEN):
                url, kop = _met_auth(methode, _api_url(self.api_root, route, params),
                                     self.ck, self.cs, self.modus)
                if body is not None:
                    kop = {**kop, "Content-Type": "application/json"}
                try:
                    r = await client.request(methode, url, headers=kop,
                                             content=json.dumps(body) if body is not None else None)
                except (httpx.TransportError, httpx.TimeoutException) as e:
                    laatste = e
                    if poging < POGINGEN - 1:
                        await asyncio.sleep(WACHT_S[min(poging, len(WACHT_S) - 1)])
                        continue
                    raise WooFout("Your shop did not answer (the connection dropped). We try "
                                  "again later.", "onbereikbaar") from e
                # Een PHP-crash (500 met een HTML-pagina) is vaak tijdelijk; een 500
                # met WooCommerce-JSON is een echte weigering en heeft geen herkansing.
                tijdelijk = r.status_code in (429, 502, 503, 504) or (
                    r.status_code == 500 and "json" not in (r.headers.get("content-type") or "").lower())
                if tijdelijk and poging < POGINGEN - 1:
                    wacht = WACHT_S[min(poging, len(WACHT_S) - 1)]
                    try:
                        wacht = max(wacht, min(int(r.headers.get("retry-after") or 0), 60))
                    except ValueError:
                        pass
                    await asyncio.sleep(wacht)
                    continue
                if r.status_code in (301, 302, 307, 308):
                    # Een doorverwijzing (http→https, www) kost bij een POST de
                    # inhoud en bij Basic de kopregel; daarom nooit vanzelf volgen.
                    raise WooFout(f"Your shop redirects to {r.headers.get('location')}. "
                                  f"Connect again with that address.", "verhuisd", r.status_code)
                if r.status_code >= 400:
                    fout = _lees_fout(r)
                    # Geweigerd met de sleutel in de kopregel: probeer hem in het
                    # adres. GEMETEN op de lokale testwinkel (09-10-2026): 4 van 16
                    # verzoeken kwamen zonder kopregel aan bij PHP, het adres ging 20
                    # van 20 goed. Een hosting met meerdere servers kan net zo
                    # wisselend zijn; één vaste keuze bij het koppelen is dan niet
                    # genoeg. De nieuwe modus blijft hangen en wordt opgeslagen
                    # door wie modus_gewijzigd ziet staan.
                    if fout.soort == "sleutel" and self.modus == "basic":
                        self.modus = "query"
                        self.modus_gewijzigd = True
                        continue
                    raise fout
                try:
                    data = r.json()
                except ValueError as e:
                    raise WooFout("Your shop answered with a web page instead of data. A cache or "
                                  "security plugin is probably in the way.", "geen_json",
                                  r.status_code) from e
                return r.status_code, data, r.headers
            raise WooFout("Your shop kept refusing. Try again later.", "serverfout") from laatste
        finally:
            if eigen:
                await client.aclose()

    async def alle_paginas(self, route: str, params: dict | None = None) -> list[dict]:
        """Alle pagina's van een lijst, rustig achter elkaar."""
        import httpx

        uit: list[dict] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0),
                                     follow_redirects=False, headers={"User-Agent": UA}) as c:
            for pagina in range(1, MAX_PAGINAS + 1):
                _, data, kop = await self.verzoek("GET", route, {**(params or {}),
                                                  "per_page": PER_PAGINA, "page": pagina}, client=c)
                if not isinstance(data, list):
                    break
                uit += data
                try:
                    totaal = int(kop.get("x-wp-totalpages") or 0)
                except ValueError:
                    totaal = 0
                if len(data) < PER_PAGINA or (totaal and pagina >= totaal):
                    return uit
                await asyncio.sleep(PAUZE_S)
        logger.warning("woocommerce %s: gestopt na %d pagina's", self.api_root, MAX_PAGINAS)
        return uit

    # ── Producten ──
    async def producten(self, gewijzigd_na: str | None = None) -> list[dict]:
        params = {"status": "publish", "orderby": "id", "order": "asc"}
        if gewijzigd_na:
            params.update({"modified_after": gewijzigd_na, "dates_are_gmt": "true"})
        return await self.alle_paginas("wc/v3/products", params)

    async def product(self, pid: str) -> dict | None:
        try:
            _, data, _ = await self.verzoek("GET", f"wc/v3/products/{pid}")
        except WooFout as e:
            if e.status == 404:
                return None
            raise
        return data

    async def variaties(self, pid: str) -> list[dict]:
        return await self.alle_paginas(f"wc/v3/products/{pid}/variations")

    async def zoek_op_sku(self, sku: str) -> dict | None:
        _, data, _ = await self.verzoek("GET", "wc/v3/products", {"sku": sku, "status": "any"})
        return data[0] if isinstance(data, list) and len(data) == 1 else None

    async def tel(self, status: str) -> int:
        try:
            _, _, kop = await self.verzoek("GET", "wc/v3/products", {"status": status, "per_page": 1})
            return int(kop.get("x-wp-total") or 0)
        except (WooFout, ValueError):
            return 0

    async def werk_bij(self, pid: str, velden: dict, variatie: str | None = None) -> dict:
        route = f"wc/v3/products/{pid}" + (f"/variations/{variatie}" if variatie else "")
        _, data, _ = await self.verzoek("PUT", route, body=velden)
        return data

    async def bestellingen(self, gewijzigd_na: str) -> list[dict]:
        """Betaalde bestellingen die sinds `gewijzigd_na` (UTC, zonder zone) veranderden.

        OUDE WINKELS (gemeten 09-10-2026: 5 van de 44 leadwinkels met een zichtbare
        versie draaien ouder dan 9, eentje 3.5). modified_after en dates_are_gmt
        bestaan pas sinds WooCommerce 5.8, en een lijst statussen in één veld ook
        niet overal; een oude winkel negeert wat hij niet kent en geeft dan ÁLLE
        bestellingen ooit. Daarom: nieuwste eerst, zelf op tijd en status filteren,
        en stoppen zodra een hele pagina van vóór het merkteken is."""
        sinds = gewijzigd_na.replace("Z", "")
        uit: list[dict] = []

        def _tijd(o: dict) -> str:
            return max(str(o.get("date_modified_gmt") or ""), str(o.get("date_created_gmt") or ""))

        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0),
                                     follow_redirects=False, headers={"User-Agent": UA}) as c:
            for pagina in range(1, MAX_PAGINAS + 1):
                _, data, _ = await self.verzoek("GET", "wc/v3/orders", {
                    "modified_after": gewijzigd_na, "dates_are_gmt": "true",
                    "orderby": "date", "order": "desc",
                    "per_page": PER_PAGINA, "page": pagina}, client=c)
                if not isinstance(data, list):
                    break
                recent = [o for o in data if _tijd(o) >= sinds]
                uit += [o for o in recent if o.get("status") in BETAALDE_STATUSSEN]
                if len(data) < PER_PAGINA or not recent:
                    break
                await asyncio.sleep(PAUZE_S)
        return uit


# Een bestelling in deze stand heeft de voorraad al verlaagd: het stuk is weg.
# 'on-hold' is de bankoverschrijving die nog binnen moet komen. WooCommerce houdt
# het product dan al vast; elders laten staan betekent dat het twee keer verkocht
# kan worden, en dat is erger dan een advertentie die terug moet.
BETAALDE_STATUSSEN = ("processing", "completed", "on-hold")


async def controleer_sleutels(adres_of_api: str, ck: str, cs: str) -> dict:
    """Werkt deze sleutel, en op welke manier? Geeft api_root, site, modus, schrijven.

    Probeert de inlogmodi op volgorde: een 401 met correcte sleutel is bij veel
    hosts een weggegooide kopregel, en dan werkt de sleutel in het adres wel."""
    ck, cs = (ck or "").strip(), (cs or "").strip()
    if not (ck.startswith("ck_") and cs.startswith("cs_")):
        raise WooFout("A WooCommerce key starts with ck_ and the secret with cs_. Copy both "
                      "from WooCommerce → Settings → Advanced → REST API.", "sleutelvorm")
    if "/wp-json" in adres_of_api or "rest_route=" in adres_of_api:
        api_root = adres_of_api
    else:
        adres = normaliseer_adres(adres_of_api)
        if not adres:
            raise WooFout("Enter your shop's address, for example yourshop.nl.", "adres")
        api_root = await ontdek_api(adres)
    laatste: WooFout | None = None
    for modus in modi_voor(api_root):
        client = WooClient(api_root, ck, cs, modus)
        try:
            _, data, kop = await client.verzoek(
                "GET", "wc/v3/products", {"per_page": 1, "status": "any"}, timeout=30.0)
            totaal = int(kop.get("x-wp-total") or 0) if kop.get("x-wp-total") else None
            return {"api_root": api_root, "site": site_van_api(api_root), "modus": client.modus,
                    "producten": totaal}
        except WooFout as e:
            laatste = e
            if e.soort != "sleutel":
                break
    raise laatste or WooFout("WooCommerce did not accept the key.", "sleutel")


# ── Koppelen met één klik (/wc-auth/v1/authorize) ───────────────────────

def _geheim() -> bytes:
    from backend.config import settings
    sleutel = settings.supabase_service_key or settings.supabase_key or ""
    return hashlib.sha256(("woo-koppel:" + sleutel).encode()).digest()


def maak_staat(user_id: str, api_root: str, nu: int | None = None) -> str:
    """Wat we als user_id aan WooCommerce meegeven: wie, welke winkel, wanneer, getekend.

    WooCommerce stuurt dit ongewijzigd terug naar onze callback. Die callback is
    openbaar (de WINKEL roept hem aan, niet de verkoper), dus zonder handtekening
    zou iedereen sleutels aan andermans account kunnen hangen."""
    inhoud = json.dumps({"u": user_id, "a": api_root, "t": nu or int(time.time())},
                        separators=(",", ":")).encode()
    deel = base64.urlsafe_b64encode(inhoud).decode().rstrip("=")
    sig = hmac.new(_geheim(), deel.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{deel}.{sig}"


STAAT_GELDIG_S = 3600


def lees_staat(staat: str, nu: int | None = None) -> dict | None:
    try:
        deel, sig = (staat or "").rsplit(".", 1)
    except ValueError:
        return None
    goed = hmac.new(_geheim(), deel.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(goed, sig):
        return None
    try:
        inhoud = json.loads(base64.urlsafe_b64decode(deel + "=" * (-len(deel) % 4)))
    except (ValueError, TypeError):
        return None
    if (nu or int(time.time())) - int(inhoud.get("t") or 0) > STAAT_GELDIG_S:
        return None
    return inhoud


def koppel_url(api_root: str, staat: str, return_url: str, callback_url: str) -> str:
    """Het adres van WooCommerce's eigen toestemmingsscherm in de winkel."""
    site = site_van_api(api_root)
    params = {"app_name": "Omnivaleur", "scope": "read_write", "user_id": staat,
              "return_url": return_url, "callback_url": callback_url}
    if "rest_route=" in api_root:
        # Zonder mooie permalinks bestaat /wc-auth/v1/ niet; WooCommerce kent
        # dan dezelfde route als queryvelden.
        return f"{site}/?" + urlencode({"wc-auth-version": "1", "wc-auth-route": "authorize", **params})
    return f"{site}/wc-auth/v1/authorize?" + urlencode(params)


# ── Wat de rest van Omnivaleur van een koppeling nodig heeft ─────────────

def client_uit(credentials: dict) -> WooClient | None:
    """De client voor een rij uit platform_credentials, of None zonder koppeling."""
    extra = (credentials or {}).get("extra_data") or {}
    ck, cs = credentials.get("access_token"), credentials.get("refresh_token")
    api_root = extra.get("api_root")
    if not (ck and cs and api_root):
        return None
    return WooClient(api_root, ck, cs, extra.get("modus") or modi_voor(api_root)[0])


def platte_tekst(html_tekst: str | None) -> str:
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", html_tekst or "", flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(r.strip() for r in s.splitlines())).strip()


def _foto_urls(item: dict) -> list[str]:
    """Alleen openbare adressen: WooCommerce haalt elke foto zelf op."""
    return [u for u in (item.get("photo_urls") or []) if isinstance(u, str)
            and u.startswith("https://")][:10]


def productvelden(item: dict) -> dict:
    prijs = item.get("price_woocommerce") or item.get("price")
    tekst = (item.get("description") or "").replace("\r\n", "\n")
    velden = {
        "name": item.get("title") or "",
        "type": "simple",
        "status": "publish",
        "regular_price": f"{float(prijs):.2f}" if prijs not in (None, "") else "",
        "description": tekst.replace("\n", "<br>\n"),
        # Eén tweedehands stuk: voorraad 1, zodat de winkel zelf uitverkoopt en
        # nooit een tweede bestelling aanneemt.
        "manage_stock": True,
        "stock_quantity": 1,
        "backorders": "no",
        "images": [{"src": u} for u in _foto_urls(item)],
    }
    if item.get("sku"):
        velden["sku"] = str(item["sku"])[:100]
    return velden


class WooCommercePlatform(PlatformBase):
    platform_name = PLATFORM

    @staticmethod
    def _eis(credentials: dict) -> WooClient:
        c = client_uit(credentials)
        if not c:
            raise RuntimeError("No WooCommerce shop is connected to this account. Open "
                               "Platforms → WooCommerce → Connect first.")
        return c

    async def create_listing(self, item: dict, credentials: dict, on_created=None) -> dict:
        c = self._eis(credentials)
        # Bestaat het al (een eerdere poging die werd afgekapt terwijl de winkel
        # nog foto's ophaalde)? Dan dat product gebruiken, geen tweede maken.
        bestaand = await c.zoek_op_sku(str(item["sku"])) if item.get("sku") else None
        if bestaand:
            product = bestaand
        else:
            # Foto's ophalen gebeurt binnen hetzelfde verzoek in de winkel; tien
            # grote foto's kosten een trage host ruim een minuut.
            _, product, _ = await c.verzoek("POST", "wc/v3/products", body=productvelden(item),
                                            timeout=180.0)
        uit = {"platform_listing_id": str(product["id"]),
               "platform_listing_url": product.get("permalink")}
        if on_created:
            try:
                await on_created(uit)
            except Exception:  # noqa: BLE001
                logger.exception("woocommerce: vastleggen van het nieuwe product mislukte")
        return uit

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        """Elders verkocht: op uitverkocht zetten, nooit wissen (zie bovenaan)."""
        c = self._eis(credentials)
        if not platform_listing_id:
            raise RuntimeError("This WooCommerce listing has no product number. Link it again "
                               "with its product URL.")
        product = await c.product(platform_listing_id)
        if product is None or product.get("status") == "trash":
            return True     # al weg: "zorg dat het er niet staat" is gelukt
        if product.get("type") == "variable":
            for v in await c.variaties(platform_listing_id):
                if v.get("stock_status") != "outofstock":
                    await c.werk_bij(platform_listing_id, _uitverkocht(v), variatie=str(v["id"]))
            return True
        if product.get("stock_status") != "outofstock" or (product.get("stock_quantity") or 0) > 0:
            await c.werk_bij(platform_listing_id, _uitverkocht(product))
        return True

    async def update_listing_price(self, platform_listing_id: str, price: float, credentials: dict) -> bool:
        c = self._eis(credentials)
        product = await c.product(platform_listing_id)
        if product is None:
            raise RuntimeError(f"WooCommerce product {platform_listing_id} no longer exists")
        if product.get("type") == "variable":
            # Elke maat kan een eigen prijs hebben; één bedrag over alle maten
            # heen zetten zou die stil gelijktrekken.
            raise RuntimeError("This product has variants (sizes) in WooCommerce. Change its "
                               "prices in WooCommerce itself.")
        # De actieprijs leegmaken: anders blijft de oude actieprijs gelden en ziet
        # de koper de nieuwe prijs nooit.
        await c.werk_bij(platform_listing_id, {"regular_price": f"{float(price):.2f}", "sale_price": ""})
        return True

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        c = client_uit(credentials)
        if not c:
            return "error"
        try:
            p = await c.product(platform_listing_id)
        except WooFout:
            return "error"
        if p is None or p.get("status") == "trash":
            return "not_found"
        return "sold" if p.get("stock_status") == "outofstock" else "active"

    async def refresh_credentials(self, credentials: dict) -> dict:
        return credentials      # WooCommerce-sleutels verlopen niet


def _uitverkocht(p: dict) -> dict:
    if p.get("manage_stock") is True:
        return {"stock_quantity": 0}
    return {"stock_status": "outofstock"}


def eerste_regel(e: Exception) -> str:
    return str(e).split("\n")[0][:300]


__all__ = ["WooClient", "WooFout", "WooCommercePlatform", "controleer_sleutels", "ontdek_api",
           "normaliseer_adres", "maak_staat", "lees_staat", "koppel_url", "client_uit",
           "platte_tekst", "BETAALDE_STATUSSEN", "PLATFORM"]
