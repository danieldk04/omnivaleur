"""
Platform auth endpoints — login endpoints for all platforms.
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.platforms.marktplaats import MarktplaatsPlatform, TweedehandsPlatform
from backend.platforms.ebay import EbayPlatform
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
    return {"url": EbayPlatform().get_authorization_url()}


@router.get("/ebay/callback")
async def ebay_callback(code: str, user_id: str = Depends(get_current_user)):
    tokens = await EbayPlatform().exchange_code(code)
    _save_credentials(user_id, "ebay", tokens)
    return {"status": "connected", "platform": "ebay"}


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
    creds = db.table("platform_credentials").select("*").eq("user_id", user_id).eq("platform", "marktplaats").single().execute()
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
async def platform_status(user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("platform_credentials").select("platform").eq("user_id", user_id).execute()
    connected = [r["platform"] for r in result.data]
    return {"connected": connected}


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
