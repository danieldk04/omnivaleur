"""
Platform auth endpoints — login endpoints for all platforms.
"""
import asyncio
import logging
import re
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from backend.database import get_db, naast_de_lus, eerste_rij
from backend.platforms.marktplaats import MarktplaatsPlatform, TweedehandsPlatform
from backend.platforms.ebay import EbayPlatform
from backend.platforms.shopify import ShopifyPlatform, is_valid_shop_domain, verify_install_hmac
from backend.models import AIListingRequest
from backend.services.ai_listing import generate_listing_from_photos
from backend.api.deps import get_current_user

logger = logging.getLogger(__name__)

# Hoeveel eBay-advertenties we na het opnieuw koppelen in één keer terugzetten.
_HERPLAATS_GRENS = 50

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.post("/marktplaats/bootstrap")
async def marktplaats_bootstrap(body: dict, user_id: str = Depends(get_current_user)):
    """Bootstrap Marktplaats session via Playwright. Body: {email, password}"""
    try:
        session = await MarktplaatsPlatform().bootstrap_session(body["email"], body["password"])
        _save_credentials(user_id, "marktplaats", {
            "access_token": "session",
            "extra_data": {
                "cookies": session["cookies"],
                "user_agent": session["user_agent"],
                "email": body["email"],
                "password": body["password"],
            },
        })
        return {
            "status": "connected",
            "platform": "marktplaats",
            "cookies_captured": len(session["cookies"]),
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/2dehands/bootstrap")
async def tweedehands_bootstrap(body: dict, user_id: str = Depends(get_current_user)):
    """Bootstrap 2dehands session via Playwright. Body: {email, password}"""
    try:
        session = await TweedehandsPlatform().bootstrap_session(body["email"], body["password"])
        _save_credentials(user_id, "2dehands", {
            "access_token": "session",
            "extra_data": {
                "cookies": session["cookies"],
                "user_agent": session["user_agent"],
                "email": body["email"],
                "password": body["password"],
            },
        })
        return {
            "status": "connected",
            "platform": "2dehands",
            "cookies_captured": len(session["cookies"]),
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/ebay/auth-url")
async def ebay_auth_url():
    try:
        return {"url": EbayPlatform().get_authorization_url()}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ebay/category-suggest")
async def ebay_category_suggest(q: str, brand: str = None, category: str = None,
                                gender: str = None, user_id: str = Depends(get_current_user)):
    """`q` is the raw title; brand/category/gender are the listing form's own
    fields. They're optional (older callers pass only `q`) but make the match far
    more reliable — a title alone is often mostly SKU, size and colour."""
    from backend.platforms.ebay import suggest_categories
    try:
        return {"suggestions": await suggest_categories(q, brand, category, gender)}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"eBay category lookup failed: {e}")


@router.get("/ebay/rubriekenboom")
async def ebay_rubriekenboom(user_id: str = Depends(get_current_user)):
    """De hele eBay-rubriekenboom van de ingestelde marktplaats, plat: id, naam,
    ouder, blad. Nodig om vaste rubrieken te kiezen, want eBay's zoeker raadt
    Toons schapenvacht als laarzen (gemeten 15-09-2026). Alleen een app-sleutel
    kan dit lezen, en die staat alleen op de server."""
    import httpx
    from backend.platforms.ebay import (TAXONOMY_API, _EBAY_TIMEOUT,
                                        _get_app_token, _get_category_tree_id)
    token = await _get_app_token()
    tree_id = await _get_category_tree_id()
    async with httpx.AsyncClient(timeout=_EBAY_TIMEOUT) as client:
        resp = await client.get(f"{TAXONOMY_API}/category_tree/{tree_id}",
                                headers={"Authorization": f"Bearer {token}",
                                         "Accept-Encoding": "gzip"})
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=resp.text[:300])
    plat = []
    stapel = [(resp.json()["rootCategoryNode"], None)]
    while stapel:
        knoop, ouder = stapel.pop()
        cat = knoop["category"]
        plat.append({"id": cat["categoryId"], "naam": cat["categoryName"], "ouder": ouder,
                     "blad": bool(knoop.get("leafCategoryTreeNode"))})
        stapel.extend((k, cat["categoryId"]) for k in knoop.get("childCategoryTreeNodes") or [])
    return {"boom": tree_id, "rubrieken": plat}


@router.get("/ebay/callback")
async def ebay_callback(achtergrond: BackgroundTasks, code: str,
                        user_id: str = Depends(get_current_user)):
    try:
        tokens = await EbayPlatform().exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"eBay authorization failed: {e}")
    # Opnieuw koppelen mag het verzendadres en de verzendinstellingen niet wissen:
    # _save_credentials schrijft extra_data weg, en de tokens hebben er geen.
    db = get_db()
    oud = (await naast_de_lus(lambda: db.table("platform_credentials").select("extra_data")
           .eq("user_id", user_id).eq("platform", "ebay").limit(1).execute())).data
    if oud and oud[0].get("extra_data"):
        bewaard = dict(oud[0]["extra_data"])
        # De markering "eBay weigert deze koppeling" hoort bij de oude sleutel.
        # Laat je hem staan, dan blijft eBay na het opnieuw koppelen ontkoppeld
        # ogen en is de knop Connect een knop die niets oplost.
        was_kapot = bewaard.pop("koppeling_kapot", None)
        tokens = {**tokens, "extra_data": bewaard}
    else:
        was_kapot = None
    _save_credentials(user_id, "ebay", tokens)
    # Niet in dit verzoek afwerken: elke eBay-plaatsing mag tot een minuut duren,
    # en de verkoper staat op deze pagina te wachten tot hij terug is in het
    # dashboard. Op de achtergrond, met een bovengrens, zodat een account met
    # honderden mislukte regels de server niet gijzelt.
    if was_kapot:
        achtergrond.add_task(_herplaats_na_herstel, user_id)
    return {"status": "connected", "platform": "ebay",
            "opnieuw_plaatsen_gestart": bool(was_kapot)}


async def _herplaats_na_herstel(user_id: str) -> int:
    """Zet de advertenties die op de dode koppeling stukliepen zelf weer klaar.

    Zonder dit moet de verkoper na het opnieuw koppelen elk artikel met de hand
    terugzoeken en opnieuw aanzetten. Bij Blackbird Guitars waren dat er zeven
    op twee dagen; bij een account dat een week uit staat loopt dat op.

    Alleen eBay-regels die in de fout staan worden geraakt, niets anders, en
    ten hoogste _HERPLAATS_GRENS stuks per keer.
    """
    from backend.services.crosslist import publish_to_platforms
    db = get_db()
    items = (await naast_de_lus(lambda: db.table("items").select("id")
             .eq("user_id", user_id).execute())).data or []
    ids = [i["id"] for i in items]
    stuk: list[str] = []
    for k in range(0, len(ids), 50):
        brok = ids[k:k + 50]
        rijen = (await naast_de_lus(lambda b=brok: db.table("listings")
                 .select("item_id,error_message").in_("item_id", b)
                 .eq("platform", "ebay").eq("status", "error").execute())).data or []
        # Alles wat op eBay in de fout staat, niet alleen wat de dode koppeling
        # raakte. Na het opnieuw koppelen is dit de enige beurt waarop het
        # vanzelf kan; anders moet de verkoper elk artikel met de hand terug
        # opzoeken. create_listing hergebruikt de bestaande offer per SKU, dus
        # een tweede poging levert geen tweede advertentie op.
        stuk.extend(r["item_id"] for r in rijen)
    gelukt = 0
    for item_id in stuk[:_HERPLAATS_GRENS]:
        try:
            await publish_to_platforms(item_id, ["ebay"], user_id)
            gelukt += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Kon eBay-advertentie %s niet opnieuw plaatsen: %s", item_id, e)
    return gelukt


def _ebay_rij(user_id: str) -> dict:
    rij = (get_db().table("platform_credentials").select("*")
           .eq("user_id", user_id).eq("platform", "ebay").limit(1).execute()).data
    if not rij:
        raise HTTPException(status_code=404, detail="Connect eBay first")
    return {**rij[0], "user_id": user_id}


@router.get("/ebay/gereedheid")
async def ebay_gereedheid(user_id: str = Depends(get_current_user)):
    """Staat alles klaar om op eBay te verkopen? Rechtstreeks nagevraagd bij eBay:
    verkopersregistratie, verkooplimiet, verzendadres en verzendinstellingen."""
    from backend.platforms import ebay_beleid
    rij = await naast_de_lus(lambda: _ebay_rij(user_id))
    platform = EbayPlatform()
    try:
        credentials = await platform._ensure_fresh_token(rij)
    except Exception as e:  # noqa: BLE001
        return {"verbonden": False, "fout": f"eBay no longer accepts this connection ({e}). Reconnect eBay."}
    headers = platform._auth_headers(credentials, write=True)
    extra = credentials.get("extra_data") or {}
    account = await ebay_beleid.lees_account(headers)
    verzending = {"instellingen": extra.get("verzending"), "status": "niet_ingesteld", "fout": None}
    if extra.get("verzending"):
        try:
            await ebay_beleid.beleid_voor_plaatsing(headers, credentials)
            verzending["status"] = "klaar"
        except ebay_beleid.EbayVerzendingNietKlaar:
            verzending["status"] = "wacht_op_ebay"
        except Exception as e:  # noqa: BLE001
            verzending["status"] = "fout"
            verzending["fout"] = str(e)
    return {
        "verbonden": True,
        "registratie_klaar": account["registratie_klaar"],
        "limiet": account["limiet"],
        "verificatie": account.get("verificatie"),
        "adres": bool((extra.get("ship_from") or {}).get("postal_code")),
        "verzending": verzending,
    }


@router.post("/ebay/verzending")
async def ebay_zet_verzending(body: dict, background_tasks: BackgroundTasks,
                              user_id: str = Depends(get_current_user)):
    """Verzendkosten, verzendtijd, retourtermijn en ophalen: opslaan, verkopersbeleid
    bij eBay aanzetten en de drie beleidsregels klaarzetten. Body: {kosten,
    verzenddagen, retourdagen, ophalen}."""
    from backend.platforms import ebay_beleid
    try:
        inst = ebay_beleid.controleer_instellingen(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    rij = await naast_de_lus(lambda: _ebay_rij(user_id))
    platform = EbayPlatform()
    credentials = await platform._ensure_fresh_token(rij)
    # Eerst bewaren, en oude beleidsnummers wissen: de volgende plaatsing moet de
    # nieuwe kosten gebruiken, ook als eBay nu nog niet klaar is.
    await naast_de_lus(lambda: ebay_beleid.bewaar_extra(user_id, {"verzending": inst, "ebay_beleid": None}))
    try:
        uitkomst = await ebay_beleid.richt_in(platform._auth_headers(credentials, write=True), inst)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Saved, but eBay did not accept it: {e}")
    if uitkomst["status"] == "klaar":
        await naast_de_lus(lambda: ebay_beleid.bewaar_extra(user_id, {"ebay_beleid": uitkomst["beleid"]}))
        background_tasks.add_task(ebay_beleid.hang_beleid_aan_live_advertenties, platform, user_id)
    return {"status": uitkomst["status"], "instellingen": inst}


@router.get("/ebay/ship-from")
def ebay_get_ship_from(user_id: str = Depends(get_current_user)):
    """Return the user's saved eBay ship-from address (used for their merchant
    location so eBay can derive Item.Country). Empty dict if none saved yet."""
    db = get_db()
    creds = (
        db.table("platform_credentials")
        .select("extra_data")
        .eq("user_id", user_id).eq("platform", "ebay").execute()
    )
    if not creds.data:
        raise HTTPException(status_code=404, detail="eBay is not connected")
    return {"ship_from": (creds.data[0].get("extra_data") or {}).get("ship_from") or {}}


@router.post("/ebay/ship-from")
async def ebay_set_ship_from(body: dict, user_id: str = Depends(get_current_user)):
    """Save the user's ship-from address and push it to their eBay merchant location.
    Body: {postal_code, city?, country?}"""
    postal = (body.get("postal_code") or "").strip()
    if not postal:
        raise HTTPException(status_code=400, detail="Postcode is required")
    db = get_db()
    creds = (
        (await naast_de_lus(lambda: db.table("platform_credentials")
        .select("*").eq("user_id", user_id).eq("platform", "ebay").execute()))
    )
    if not creds.data:
        raise HTTPException(status_code=404, detail="Connect eBay first")
    row = creds.data[0]
    extra = row.get("extra_data") or {}
    extra["ship_from"] = {
        "postal_code": postal,
        "city": (body.get("city") or "").strip(),
        "country": (body.get("country") or "NL").strip().upper(),
    }
    (await naast_de_lus(lambda: db.table("platform_credentials").update({"extra_data": extra}).eq(
        "user_id", user_id).eq("platform", "ebay").execute()))
    # Push to eBay so the location reflects the new address right away.
    try:
        await EbayPlatform().upsert_location({**row, "extra_data": extra})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Saved, but eBay rejected the address: {e}")
    return {"status": "saved", "ship_from": extra["ship_from"]}


# NA HET KOPPELEN: WAT ER AL OP SHOPIFY STAAT ZELF LATEN HERKENNEN (09-09-2026).
#
# Vrijwel niemand koppelt Shopify met een lege winkel. Zonder deze stap zag elk
# artikel dat toevallig ook op Shopify staat er meteen als "niet gelist" uit —
# gemeten op Revaleur's eigen winkel 241 van de 259 al-aanwezige artikelen. Draait
# op de achtergrond (kan bij een grote catalogus een minuut of wat duren) zodat de
# koppelknop niet op deze ronde hoeft te wachten. Zie backend/services/shopify_reconcile.py.
def _koppel_bestaande_shopify_catalogus(background_tasks: BackgroundTasks, user_id: str) -> None:
    from backend.services.shopify_reconcile import (reconcile_shopify_catalog,
                                                    reconcile_verweesde_shopify_listings)
    # Eerst koppelen wat er al staat, dan pas opruimen wat er niet meer is — in
    # die volgorde, want de opruimronde kijkt naar "is er nog een levende rij
    # voor dit artikel" en die levende rij moet er dan al staan.
    background_tasks.add_task(reconcile_shopify_catalog, user_id)
    background_tasks.add_task(reconcile_verweesde_shopify_listings, user_id)


# Laatste alarm per klant en melding, zodat vijf pogingen achter elkaar met
# dezelfde fout één mail geven en niet vijf.
_SHOPIFY_ALARM_SINDS: dict[tuple[str, str], float] = {}
SHOPIFY_ALARM_STILTE_SEC = 30 * 60


def _meld_mislukte_shopify_koppeling(user_id: str, shop: str, fout: Exception) -> bool:
    """Mail Daniel bij een mislukte Shopify-koppeling, met Shopify's eigen reden.

    Janneke (31d28378, 05-10-2026) liep vast bij stap 3 en niemand kon zien wat
    Shopify had gezegd: het stond nergens, en haar winkeladres en geheim worden
    pas bewaard als het lukt. Met deze mail ziet Daniel bij de eerstvolgende
    poging welke stap het is, terwijl de klant nog achter haar scherm zit."""
    import time
    from backend.services.email import send_email
    from backend.services.referral_mail import email_van

    sleutel = (user_id, str(fout))
    nu = time.time()
    if nu - _SHOPIFY_ALARM_SINDS.get(sleutel, 0) < SHOPIFY_ALARM_STILTE_SEC:
        return False
    _SHOPIFY_ALARM_SINDS[sleutel] = nu

    adres = email_van(user_id) or user_id
    code = getattr(fout, "code", "") or "geen"
    uitleg = getattr(fout, "uitleg", "") or ""
    tekst = (
        f"{adres} probeerde Shopify te koppelen en dat lukte niet.\n\n"
        f"Winkeladres: {shop or '(leeg)'}\n"
        f"Reden van Shopify: {code} {uitleg}".rstrip() + "\n"
        f"Dit zag de klant op het scherm:\n{fout}\n\n"
        "De klant kan het meteen opnieuw proberen. Lukt het, dan komt er geen mail.\n"
    )
    return bool(send_email(subject=f"Shopify koppelen mislukt: {adres}", body=tekst))


@router.get("/shopify/auth-url")
async def shopify_auth_url(shop: str, user_id: str = Depends(get_current_user)):
    shop = shop.strip().lower()
    if not is_valid_shop_domain(shop):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid Shopify store domain, e.g. your-store.myshopify.com",
        )
    try:
        return {"url": ShopifyPlatform().get_authorization_url(shop, state=user_id)}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/shopify/callback")
async def shopify_callback(shop: str, code: str, request: Request,
                           background_tasks: BackgroundTasks,
                           user_id: str = Depends(get_current_user)):
    shop = shop.strip().lower()
    if not is_valid_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Invalid shop domain")
    if not verify_install_hmac(dict(request.query_params)):
        raise HTTPException(status_code=400, detail="Invalid request signature")
    try:
        tokens = await ShopifyPlatform().exchange_code(shop, code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Shopify authorization failed: {e}")
    _save_credentials(user_id, "shopify", tokens)
    _koppel_bestaande_shopify_catalogus(background_tasks, user_id)
    return {"status": "connected", "platform": "shopify"}


@router.post("/shopify/connect-app")
async def shopify_connect_app(body: dict, background_tasks: BackgroundTasks,
                              user_id: str = Depends(get_current_user)):
    """Koppelen met een app die de winkelier zelf in zijn Dev Dashboard maakt.

    Body: {"shop": "...", "client_id": "...", "client_secret": "..."}

    DIT IS DE WEG DIE VOOR IEDEREEN WERKT. Shopify laat geen apps meer toe die
    koppelen met een marktplaats erbuiten, en heeft óók het aanmaken van
    sleutel-tonende apps in het winkelbeheer geschrapt. Wat overblijft: de
    winkelier maakt een app in zijn EIGEN Shopify-organisatie. App en winkel
    zitten dan per definitie in dezelfde organisatie, en dat is precies de
    voorwaarde voor de client credentials grant. Geen beoordeling, geen App
    Store, geen afhankelijkheid van Shopify's goedkeuring.
    """
    from backend.platforms.shopify import controleer_app_gegevens
    shop = re.sub(r"^https?://", "", str(body.get("shop") or "").strip().lower()).split("/")[0]
    try:
        g = await controleer_app_gegevens(shop, body.get("client_id"), body.get("client_secret"))
    except ValueError as e:
        # Wachten op de mail, want na de HTTPException draait geen achtergrondtaak
        # meer. Een haperende mailserver mag de klant niet laten wachten.
        import asyncio
        try:
            await asyncio.wait_for(asyncio.to_thread(_meld_mislukte_shopify_koppeling,
                                                     user_id, shop, e), timeout=8)
        except Exception as fout:
            logger.error("Alarm over mislukte Shopify-koppeling niet verstuurd: %s", fout)
        raise HTTPException(status_code=400, detail=str(e))

    _save_credentials(user_id, "shopify", {
        "access_token": g["access_token"],
        "extra_data": {
            "shop_domain": g["shop"],
            "shop_name": g["shop_name"],
            "scope": ",".join(g["scopes"]),
            # Deze twee zijn de eigenlijke koppeling: de sleutel zelf verloopt na
            # 24 uur en wordt hiermee steeds opnieuw opgehaald.
            "client_id": str(body.get("client_id")).strip(),
            "client_secret": str(body.get("client_secret")).strip(),
            "token_expires_at": g["expires_at"],
            "koppeling": "eigen_app",
        },
    })
    _koppel_bestaande_shopify_catalogus(background_tasks, user_id)
    return {
        "status": "connected",
        "platform": "shopify",
        "shop": g["shop"],
        "shop_name": g["shop_name"],
        "missing_optional_scopes": g["aanbevolen_ontbreekt"],
    }


@router.post("/shopify/connect-token")
async def shopify_connect_token(body: dict, background_tasks: BackgroundTasks,
                                user_id: str = Depends(get_current_user)):
    """Koppelen met een sleutel die de winkelier zelf aanmaakt.

    Body: {"shop": "mijn-winkel.myshopify.com", "access_token": "shpat_..."}

    WAAROM DEZE WEG BESTAAT. Shopify accepteert geen apps meer die koppelen met
    een marktplaats buiten Shopify (bericht van 28-08-2026, app op 'paused'), dus
    de koppelknop via de App Store is doodlopend. Een app die de winkelier zelf
    in zijn eigen beheerscherm maakt heeft geen enkele beoordeling nodig en werkt
    verder precies hetzelfde: dezelfde Admin API, dezelfde kopregel, dezelfde
    rechten. Alleen het verkrijgen van de sleutel verschilt.
    """
    from backend.platforms.shopify import controleer_admin_token
    shop = str(body.get("shop") or "").strip().lower()
    token = str(body.get("access_token") or "").strip()
    # Winkeliers plakken vaak de hele URL uit hun adresbalk.
    shop = re.sub(r"^https?://", "", shop).split("/")[0]
    try:
        gegevens = await controleer_admin_token(shop, token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _save_credentials(user_id, "shopify", {
        "access_token": token,
        "extra_data": {
            "shop_domain": gegevens["shop"],
            "shop_name": gegevens["shop_name"],
            "scope": ",".join(gegevens["scopes"]),
            # Vastleggen HOE er gekoppeld is. De verkoopmelding werkt anders bij
            # een zelfgemaakte app (geen webhook, wij kijken zelf na), en zonder
            # dit merkteken weet niets in de code welk van de twee het is.
            "koppeling": "eigen_sleutel",
        },
    })
    _koppel_bestaande_shopify_catalogus(background_tasks, user_id)
    return {
        "status": "connected",
        "platform": "shopify",
        "shop": gegevens["shop"],
        "shop_name": gegevens["shop_name"],
        # Niet blokkerend, maar de winkelier moet het wél weten.
        "missing_optional_scopes": gegevens["aanbevolen_ontbreekt"],
    }


@router.post("/vinted/bootstrap")
async def vinted_bootstrap(body: dict, user_id: str = Depends(get_current_user)):
    """
    Bootstrap a Vinted session via Playwright Stealth.
    Body: {"email": "...", "password": "..."}
    Stores session cookies in platform_credentials.
    """
    from backend.platforms.vinted import VintedPlatform
    platform = VintedPlatform()
    session = await platform.bootstrap_session(body["email"], body["password"])
    _save_credentials(user_id, "vinted", {
        "access_token": "session",
        "extra_data": {
            "cookies": session["cookies"],
            "user_agent": session["user_agent"],
            "email": body["email"],
            "password": body["password"],  # stored encrypted in prod
        }
    })
    return {"status": "connected", "platform": "vinted"}


@router.get("/marktplaats/debug")
async def marktplaats_debug(user_id: str = Depends(get_current_user)):
    """Navigate SYI form with stored session and capture the submit API call."""
    from playwright.async_api import async_playwright
    db = get_db()
    creds = eerste_rij(await naast_de_lus(lambda: db.table("platform_credentials").select("*").eq("user_id", user_id).eq("platform", "marktplaats").limit(1).execute()))
    if not creds:
        return {"error": "not connected"}
    extra = creds.get("extra_data") or {}
    cookies = extra.get("cookies", {})
    ua = extra.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    post_requests = []
    all_requests = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=ua, locale="nl-NL")

        # Inject cookies for all relevant Marktplaats domains
        cookie_list = []
        for k, v in cookies.items():
            for domain in [".marktplaats.nl", "www.marktplaats.nl", "marktplaats.nl"]:
                cookie_list.append({"name": k, "value": v, "domain": domain, "path": "/", "secure": True, "sameSite": "Lax"})
        await context.add_cookies(cookie_list)
        page = await context.new_page()

        async def on_request(req):
            url = req.url
            entry = {"method": req.method, "url": url}
            if req.method == "POST":
                try:
                    entry["post_data"] = req.post_data
                except Exception:
                    pass
                post_requests.append(entry)
            if not any(ext in url for ext in [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico", ".gif"]):
                all_requests.append(entry)

        page.on("request", on_request)

        # Use the correct ad-placement URL (target from login redirect)
        await page.goto("https://www.marktplaats.nl/plaats", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        title = await page.title()
        current_url = page.url
        page_text = (await page.inner_text("body"))[:400]

        # Grab all input fields and buttons visible on the page
        form_info = await page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input, select, textarea, button')).map(el => ({
                tag: el.tagName, type: el.type, name: el.name, id: el.id,
                placeholder: el.placeholder, text: el.innerText?.substring(0,30)
            }));
            const links = Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href, text: a.innerText.trim().substring(0, 40)
            })).slice(0, 10);
            return {inputs: inputs.slice(0, 20), links};
        }""")

        all_links = form_info.get("links", [])
        plaatsen_url = {"final_url": current_url}

        await browser.close()

    return {
        "title": title,
        "final_url": current_url,
        "page_text_preview": page_text,
        "form_elements": form_info.get("inputs", []),
        "links": all_links,
        "post_requests": post_requests[:10],
        "api_requests": [r for r in all_requests if any(x in r["url"] for x in ["api", "graphql", "/v1", "/v2"])][:20],
    }


@router.post("/marktplaats/sync-chrome-session")
async def marktplaats_sync_chrome(body: dict, user_id: str = Depends(get_current_user)):
    """
    Save Marktplaats session cookies extracted from a real Chrome browser.
    Body: {"cookies": {"__mpx": "...", "MpSession": "...", "aws-waf-token": "...", ...}, "email": "...", "password": "..."}
    Call this when headless bootstrap fails due to AWS WAF.
    """
    cookies = body.get("cookies", {})
    if not cookies:
        raise HTTPException(status_code=400, detail="No cookies provided")
    _save_credentials(user_id, "marktplaats", {
        "access_token": "session",
        "extra_data": {
            "cookies": cookies,
            "user_agent": body.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            "email": body.get("email", ""),
            "password": body.get("password", ""),
        },
    })
    return {"status": "synced", "platform": "marktplaats", "cookies_saved": len(cookies)}


@router.post("/2dehands/sync-chrome-session")
async def tweedehands_sync_chrome(body: dict, user_id: str = Depends(get_current_user)):
    """Save 2dehands session cookies from Chrome browser."""
    cookies = body.get("cookies", {})
    if not cookies:
        raise HTTPException(status_code=400, detail="No cookies provided")
    _save_credentials(user_id, "2dehands", {
        "access_token": "session",
        "extra_data": {
            "cookies": cookies,
            "user_agent": body.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
            "email": body.get("email", ""),
            "password": body.get("password", ""),
        },
    })
    return {"status": "synced", "platform": "2dehands", "cookies_saved": len(cookies)}


@router.get("/status")
def platform_status(user_id: str = Depends(get_current_user)):
    """Welke kanalen zijn écht gekoppeld.

    EEN RIJ IN DE DATABASE IS GEEN KOPPELING (21-09-2026, Blackbird Guitars).
    Hier werd alleen geteld of er een regel bestond. Toen eBay de opgeslagen
    sleutel van deze verkoper weigerde, bleef eBay twee dagen lang als
    gekoppeld in beeld terwijl elke plaatsing mislukte, en zag hij nergens
    een knop om het te herstellen. Weigert het kanaal de koppeling, dan telt
    hij hier niet meer mee en verschijnt Connect vanzelf weer.
    """
    db = get_db()
    result = (db.table("platform_credentials").select("platform,extra_data")
              .eq("user_id", user_id).execute())
    connected, kapot = [], []
    for r in result.data or []:
        reden = ((r.get("extra_data") or {}).get("koppeling_kapot") or {})
        if reden:
            kapot.append({"platform": r["platform"],
                          "sinds": reden.get("sinds"),
                          "reden": reden.get("reden")})
            continue
        connected.append(r["platform"])
    return {"connected": connected, "opnieuw_koppelen": kapot}


@router.delete("/{platform}/disconnect")
def disconnect_platform(platform: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    db.table("platform_credentials").delete().eq("user_id", user_id).eq("platform", platform).execute()
    return {"status": "disconnected", "platform": platform}


@router.post("/ai-listing")
async def ai_generate_listing(body: AIListingRequest, user_id: str = Depends(get_current_user)):
    """Generate a listing from photos using Claude Vision."""
    result = await generate_listing_from_photos(body.photo_urls, body.platforms)
    return result


def _save_credentials(user_id: str, platform: str, tokens: dict):
    db = get_db()
    db.table("platform_credentials").upsert({
        "user_id": user_id,
        "platform": platform,
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_expires_at": tokens.get("token_expires_at"),
        "extra_data": tokens.get("extra_data"),
    }, on_conflict="user_id,platform").execute()


# ── WooCommerce (09-10-2026) ─────────────────────────────────────────────
#
# Twee wegen naar dezelfde koppeling, zie backend/platforms/woocommerce.py:
#   1. Eén klik: de verkoper vult zijn winkeladres in, wij sturen hem naar
#      WooCommerce's eigen toestemmingsscherm in zijn winkel. Daar klikt hij op
#      Approve; zijn WINKEL stuurt de sleutel naar /woocommerce/callback.
#   2. Sleutel plakken: voor winkels waar dat scherm niet werkt (de winkel kan
#      ons niet bereiken, een beveiligingsplugin houdt het tegen).
# In beide gevallen wordt de sleutel pas als gekoppeld getoond als hij echt werkt.

WOO_RETURN_URL = "https://omnivaleur.com/app#platforms"
WOO_CALLBACK_URL = "https://omnivaleur.com/api/platforms/woocommerce/callback"


def _bewaar_woo(user_id: str, ck: str, cs: str, gegevens: dict, hoe: str,
                via_browser: bool = False) -> None:
    from backend.platforms.woocommerce import PLATFORM
    db = get_db()
    # De voorraadvlag en het merkteken van de bestellingen blijven staan bij
    # opnieuw koppelen; een nieuwe sleutel is geen nieuwe winkel.
    oud = ((db.table("platform_credentials").select("extra_data").eq("user_id", user_id)
            .eq("platform", PLATFORM).limit(1).execute().data or [{}])[0].get("extra_data") or {})
    zelfde_winkel = oud.get("api_root") == gegevens["api_root"]
    extra = {**(oud if zelfde_winkel else {}),
             "api_root": gegevens["api_root"], "site": gegevens["site"],
             "modus": gegevens["modus"], "koppeling": hoe}
    extra.pop("verkoop_fout", None)
    extra.pop("koppeling_kapot", None)
    if via_browser:
        extra["via_browser"] = True
    else:
        extra.pop("via_browser", None)
    _save_credentials(user_id, PLATFORM, {"access_token": ck, "refresh_token": cs,
                                          "extra_data": extra})


# Kopregel bij een 409: de winkel laat onze server niet binnen, het dashboard
# moet het via de browser van de klant doen (services/woocommerce_browser.py).
# Een kopregel en geen 200 met een vlag: een oude, gecachete app.html las een
# 200 als "gekoppeld".
VIA_BROWSER_KOP = "X-Woo-Via-Browser"


def _browser_api_root(adres: str, api_root: str | None) -> str | None:
    """Het API-adres dat de browser vond, als het bij deze winkel hoort."""
    from urllib.parse import urlsplit
    if not api_root:
        return None
    a, w = urlsplit(adres), urlsplit(api_root)
    kaal = lambda h: (h or "").lower().removeprefix("www.")  # noqa: E731
    if w.scheme != "https" or kaal(w.hostname) != kaal(a.hostname):
        return None
    if "/wp-json" not in w.path and "rest_route=" not in w.query:
        return None
    return api_root


@router.get("/woocommerce/auth-url")
async def woocommerce_auth_url(store: str, api_root: str | None = None,
                               user_id: str = Depends(get_current_user)):
    """Het toestemmingsadres in de winkel. Met `api_root`: dat vond de browser
    zelf, omdat de winkel onze server niet binnenlaat (409 hieronder)."""
    from backend.platforms.woocommerce import (WooFout, koppel_url, maak_staat,
                                               normaliseer_adres, ontdek_api)
    adres = normaliseer_adres(store)
    if not adres:
        raise HTTPException(status_code=400,
                            detail="Enter your shop's address, for example yourshop.nl.")
    if api_root:
        gevonden = _browser_api_root(adres, api_root)
        if not gevonden:
            raise HTTPException(status_code=400,
                                detail="Enter your shop's address, for example yourshop.nl.")
        return {"url": koppel_url(gevonden, maak_staat(user_id, gevonden, browser=True),
                                  WOO_RETURN_URL, WOO_CALLBACK_URL),
                "site": gevonden, "via_browser": True}
    try:
        api_root = await ontdek_api(adres)
    except WooFout as e:
        # Ook hier mailen: De Juiste Toon (10-10-2026) liep op deze stap vast en
        # zonder mail had niemand gezien wat de winkel ons werkelijk antwoordde.
        try:
            await asyncio.wait_for(asyncio.to_thread(_meld_mislukte_woo_koppeling,
                                                     user_id, adres, e), timeout=10)
        except Exception:  # noqa: BLE001 — de mail mag de melding niet tegenhouden
            pass
        if e.soort == "geblokkeerd":
            raise HTTPException(status_code=409, detail=str(e), headers={VIA_BROWSER_KOP: "1"})
        raise HTTPException(status_code=400, detail=str(e))
    if not api_root.lower().startswith("https://"):
        # WooCommerce stuurt de sleutel alleen naar een https-adres, en over http
        # werkt de knop-route in de praktijk niet. Plakken kan wel.
        raise HTTPException(status_code=400, detail=(
            "Your shop doesn't use https, so the one-click connection isn't available. "
            "Use 'Paste a key instead' below."))
    return {"url": koppel_url(api_root, maak_staat(user_id, api_root),
                              WOO_RETURN_URL, WOO_CALLBACK_URL),
            "site": api_root}


@router.post("/woocommerce/callback")
async def woocommerce_callback(request: Request, background_tasks: BackgroundTasks):
    """Hier stuurt de WINKEL de sleutel heen nadat de verkoper Approve klikte.

    Geen inlog: de winkel roept dit aan, niet de browser. Wie het is staat in de
    getekende staat die wij zelf in het toestemmingsadres zetten (lees_staat);
    zonder geldige handtekening wordt er niets bewaard. Antwoord altijd snel met
    200 bij een geldige staat: WooCommerce wacht hierop en toont de verkoper
    anders een foutmelding, terwijl de sleutel dan al bestaat."""
    from backend.platforms.woocommerce import lees_staat
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="no JSON")
    staat = lees_staat(str(body.get("user_id") or ""))
    ck, cs = str(body.get("consumer_key") or ""), str(body.get("consumer_secret") or "")
    if not staat or not (ck.startswith("ck_") and cs.startswith("cs_")):
        logger.warning("woocommerce-callback geweigerd: staat %s, sleutel %s",
                       "geldig" if staat else "ongeldig", "ja" if ck else "nee")
        raise HTTPException(status_code=403, detail="invalid state")
    background_tasks.add_task(_woo_controleer_en_bewaar, staat["u"], staat["a"], ck, cs,
                              bool(staat.get("b")))
    return {"ok": True}


async def _woo_controleer_en_bewaar(user_id: str, api_root: str, ck: str, cs: str,
                                    via_browser: bool = False) -> None:
    from backend.platforms.woocommerce import WooFout, controleer_sleutels, site_van_api
    if via_browser:
        # De winkel laat onze server niet binnen, dus hier niet controleren. De
        # sleutel komt van de winkel zelf, na Approve, met onze getekende staat:
        # die is echt. Het dashboard controleert hem via de browser zodra de
        # klant terug is (/woocommerce/browser-controle).
        await naast_de_lus(lambda: _bewaar_woo(user_id, ck, cs, {
            "api_root": api_root, "site": site_van_api(api_root), "modus": "basic"},
            "knop", via_browser=True))
        _woo_mislukt.pop(user_id, None)
        logger.info("woocommerce: %s gekoppeld via de knop, via de browser (%s)",
                    user_id[:8], api_root)
        return
    try:
        gegevens = await controleer_sleutels(api_root, ck, cs)
    except WooFout as e:
        logger.warning("woocommerce: sleutel van %s via de knop werkt niet: %s", user_id[:8], e)
        _woo_mislukt[user_id] = str(e)
        try:
            await asyncio.to_thread(_meld_mislukte_woo_koppeling, user_id, api_root, e)
        except Exception:  # noqa: BLE001
            pass
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("woocommerce: controle na de knop mislukt voor %s", user_id[:8])
        _woo_mislukt[user_id] = f"Could not check the key ({type(e).__name__}). Try again."
        return
    await naast_de_lus(lambda: _bewaar_woo(user_id, ck, cs, gegevens, "knop"))
    _woo_mislukt.pop(user_id, None)
    logger.info("woocommerce: %s gekoppeld via de knop (%s, %s)", user_id[:8],
                gegevens["site"], gegevens["modus"])


# Wat er misging na de knop, zodat het scherm het kan zeggen. In het geheugen:
# het gaat om de minuut na het klikken, en een herstart betekent hooguit dat
# de verkoper het nog eens probeert.
_woo_mislukt: dict[str, str] = {}


@router.post("/woocommerce/connect-keys")
async def woocommerce_connect_keys(body: dict, user_id: str = Depends(get_current_user)):
    """Koppelen met een sleutel die de verkoper zelf in WooCommerce aanmaakte.

    Body: {"store": "mijnwinkel.nl", "consumer_key": "ck_...", "consumer_secret": "cs_..."}
    Met "api_root" erbij (wat de browser vond): de winkel laat onze server niet
    binnen en de sleutel wordt via de browser van de klant gecontroleerd."""
    from backend.platforms.woocommerce import WooFout, controleer_sleutels, normaliseer_adres
    from backend.services import woocommerce_browser as wb
    store = str(body.get("store") or "").strip()
    browser_root = _browser_api_root(normaliseer_adres(store), str(body.get("api_root") or "")) \
        if body.get("api_root") else None
    if body.get("api_root") and not browser_root:
        raise HTTPException(status_code=400, detail="Enter your shop's address, for example yourshop.nl.")
    if browser_root and not await wb.wacht_op_browser(user_id):
        raise HTTPException(status_code=409, detail=wb.GEEN_BROWSER_MELDING)
    try:
        gegevens = await controleer_sleutels(
            browser_root or store, str(body.get("consumer_key") or ""),
            str(body.get("consumer_secret") or ""),
            transport=wb.BrowserTransport(user_id) if browser_root else None)
    except WooFout as e:
        try:
            await asyncio.wait_for(asyncio.to_thread(_meld_mislukte_woo_koppeling,
                                                     user_id, store, e), timeout=10)
        except Exception:  # noqa: BLE001 — de mail mag de melding niet tegenhouden
            pass
        if e.soort == "geblokkeerd" and not browser_root:
            raise HTTPException(status_code=409, detail=str(e), headers={VIA_BROWSER_KOP: "1"})
        raise HTTPException(status_code=400, detail=str(e))
    await naast_de_lus(lambda: _bewaar_woo(user_id, str(body["consumer_key"]).strip(),
                                           str(body["consumer_secret"]).strip(), gegevens, "sleutel",
                                           via_browser=bool(browser_root)))
    if browser_root:
        await _woo_webhook_op_achtergrond(user_id)
    return {"status": "connected", "platform": "woocommerce", "site": gegevens["site"],
            "producten": gegevens.get("producten")}


@router.get("/woocommerce/info")
def woocommerce_info(user_id: str = Depends(get_current_user)):
    """Gekoppeld, met welke winkel, en of het nakijken van verkopen nog lukt."""
    from backend.platforms.woocommerce import PLATFORM
    rij = (get_db().table("platform_credentials").select("extra_data").eq("user_id", user_id)
           .eq("platform", PLATFORM).limit(1).execute().data or [])
    extra = (rij[0].get("extra_data") if rij else None) or {}
    from backend.services.woocommerce_browser import WACHTRIJ
    return {"connected": bool(rij), "site": extra.get("site"),
            "verkoop_fout": extra.get("verkoop_fout"),
            "via_browser": bool(extra.get("via_browser")),
            "wacht_op_browser": len(extra.get(WACHTRIJ) or []),
            "mislukt": None if rij else _woo_mislukt.get(user_id)}


# ── Via de browser van de klant (services/woocommerce_browser.py) ────────

async def _woo_webhook_op_achtergrond(user_id: str) -> None:
    """Webhook regelen zonder het koppelen op te houden of te laten mislukken."""
    from backend.services.woocommerce_browser import houd_vast, zorg_voor_webhook

    async def _doe():
        try:
            uit = await zorg_voor_webhook(get_db(), user_id)
            logger.info("woocommerce: webhook voor %s: %s", user_id[:8], uit)
        except Exception as e:  # noqa: BLE001 — bij de volgende browserronde opnieuw
            logger.warning("woocommerce: webhook voor %s niet geregeld: %s", user_id[:8], e)
    houd_vast(asyncio.get_running_loop().create_task(_doe()))


@router.get("/woocommerce/browser/opdrachten")
async def woocommerce_browser_opdrachten(user_id: str = Depends(get_current_user)):
    """Het dashboard vraagt: moet ik iets bij de winkel doen? Wacht hooguit 25 s."""
    from backend.services.woocommerce_browser import haal_opdrachten
    return {"opdrachten": await haal_opdrachten(user_id)}


@router.post("/woocommerce/browser/antwoord")
async def woocommerce_browser_antwoord(body: dict, user_id: str = Depends(get_current_user)):
    from backend.services.woocommerce_browser import lever_antwoord
    return {"ok": lever_antwoord(user_id, str(body.get("id") or ""), body)}


@router.post("/woocommerce/browser-controle")
async def woocommerce_browser_controle(user_id: str = Depends(get_current_user)):
    """Na koppelen met de knop: werkt de sleutel via de browser? Regelt ook de webhook."""
    from backend.platforms.woocommerce import PLATFORM, WooFout, controleer_sleutels
    from backend.services import woocommerce_browser as wb
    rij = ((await naast_de_lus(lambda: get_db().table("platform_credentials").select("*")
            .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
    if not rij or not wb.via_browser(rij[0]):
        raise HTTPException(status_code=404, detail="Your WooCommerce shop isn't connected yet. "
                                                    "Connect it under Platforms first.")
    extra = rij[0].get("extra_data") or {}
    if not await wb.wacht_op_browser(user_id):
        raise HTTPException(status_code=409, detail=wb.GEEN_BROWSER_MELDING)
    try:
        gegevens = await controleer_sleutels(extra["api_root"], rij[0]["access_token"],
                                             rij[0]["refresh_token"],
                                             transport=wb.BrowserTransport(user_id))
    except WooFout as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _woo_webhook_op_achtergrond(user_id)
    return {"ok": True, "site": gegevens["site"], "producten": gegevens.get("producten")}


@router.post("/woocommerce/webhook/{token}")
async def woocommerce_webhook(token: str, request: Request, background_tasks: BackgroundTasks):
    """Hier meldt de WINKEL zelf een bestelling (alleen bij winkels via de browser).

    Openbaar: de winkel roept dit aan. Wie het is zegt het token in het adres,
    dat het echt de winkel is zegt de handtekening (geheim bij het aanmaken).
    Altijd snel 200 bij een geldig token: WooCommerce zet de webhook anders na
    vijf mislukte afleveringen stil uit."""
    from backend.platforms.woocommerce import PLATFORM
    from backend.services.woocommerce_browser import handtekening_klopt
    from backend.services.woocommerce_orders import verwerk_bestelling
    if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
        raise HTTPException(status_code=404, detail="unknown")
    rijen = ((await naast_de_lus(lambda: get_db().table("platform_credentials")
              .select("user_id,extra_data").eq("platform", PLATFORM).limit(1000).execute())).data or [])
    rij = next((r for r in rijen if (r.get("extra_data") or {}).get("webhook_token") == token), None)
    if not rij:
        raise HTTPException(status_code=404, detail="unknown")
    inhoud = await request.body()
    if inhoud.startswith(b"webhook_id="):
        return {"ok": True}     # de proefmelding bij het aanmaken
    if not handtekening_klopt((rij.get("extra_data") or {}).get("webhook_geheim") or "", inhoud,
                              request.headers.get("x-wc-webhook-signature")):
        logger.warning("woocommerce-webhook: handtekening klopt niet voor %s", rij["user_id"][:8])
        raise HTTPException(status_code=401, detail="bad signature")
    try:
        import json
        order = json.loads(inhoud)
    except ValueError:
        return {"ok": True}
    if isinstance(order, dict) and order.get("line_items") is not None:
        async def _verwerk():
            try:
                n = await verwerk_bestelling(get_db(), rij["user_id"], order)
                if n:
                    logger.info("woocommerce-webhook: %s bestelling %s, %d verkoop/verkopen",
                                rij["user_id"][:8], order.get("id"), n)
            except Exception:  # noqa: BLE001
                logger.exception("woocommerce-webhook: bestelling %s niet verwerkt", order.get("id"))
        background_tasks.add_task(_verwerk)
    return {"ok": True}


_WOO_ALARM_SINDS: dict = {}


def _meld_mislukte_woo_koppeling(user_id: str, winkel: str, fout: Exception) -> bool:
    """Mail Daniel bij een mislukte koppeling, met de reden. Zoals bij Shopify:
    bij Janneke kon niemand zien wat er misging terwijl zij nog achter haar
    scherm zat. Hooguit één mail per klant per fout per kwartier."""
    import time
    from backend.services.email import send_email
    from backend.services.referral_mail import email_van

    sleutel = (user_id, str(fout))
    nu = time.time()
    if nu - _WOO_ALARM_SINDS.get(sleutel, 0) < 900:
        return False
    _WOO_ALARM_SINDS[sleutel] = nu
    adres = email_van(user_id) or user_id
    tekst = (f"{adres} probeerde WooCommerce te koppelen en dat lukte niet.\n\n"
             f"Winkel: {winkel or '(leeg)'}\n"
             f"Soort fout: {getattr(fout, 'soort', type(fout).__name__)}\n"
             f"Dit zag de klant op het scherm:\n{fout}\n")
    if getattr(fout, "detail", ""):
        tekst += f"\nWat de winkel onze server antwoordde:\n{fout.detail}\n"
    return bool(send_email(subject=f"WooCommerce koppelen mislukt: {adres}", body=tekst))
