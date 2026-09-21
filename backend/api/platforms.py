"""
Platform auth endpoints — login endpoints for all platforms.
"""
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
