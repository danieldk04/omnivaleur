"""
Platform auth endpoints — login endpoints for all platforms.
"""
import re
from fastapi import APIRouter, HTTPException, Depends, Request
from backend.database import get_db, naast_de_lus
from backend.platforms.marktplaats import MarktplaatsPlatform, TweedehandsPlatform
from backend.platforms.ebay import EbayPlatform
from backend.platforms.shopify import ShopifyPlatform, is_valid_shop_domain, verify_install_hmac
from backend.models import AIListingRequest
from backend.services.ai_listing import generate_listing_from_photos
from backend.api.deps import get_current_user

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


@router.get("/ebay/callback")
async def ebay_callback(code: str, user_id: str = Depends(get_current_user)):
    try:
        tokens = await EbayPlatform().exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"eBay authorization failed: {e}")
    _save_credentials(user_id, "ebay", tokens)
    return {"status": "connected", "platform": "ebay"}


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
async def shopify_callback(shop: str, code: str, request: Request, user_id: str = Depends(get_current_user)):
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
    return {"status": "connected", "platform": "shopify"}


@router.post("/shopify/connect-app")
async def shopify_connect_app(body: dict, user_id: str = Depends(get_current_user)):
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
    return {
        "status": "connected",
        "platform": "shopify",
        "shop": g["shop"],
        "shop_name": g["shop_name"],
        "missing_optional_scopes": g["aanbevolen_ontbreekt"],
    }


@router.post("/shopify/connect-token")
async def shopify_connect_token(body: dict, user_id: str = Depends(get_current_user)):
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
    creds = (await naast_de_lus(lambda: db.table("platform_credentials").select("*").eq("user_id", user_id).eq("platform", "marktplaats").single().execute()))
    if not creds.data:
        return {"error": "not connected"}
    extra = creds.data.get("extra_data") or {}
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
    db = get_db()
    result = db.table("platform_credentials").select("platform").eq("user_id", user_id).execute()
    connected = [r["platform"] for r in result.data]
    return {"connected": connected}


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
