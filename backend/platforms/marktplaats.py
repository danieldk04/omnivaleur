"""
Marktplaats.nl & 2dehands.be integration via Playwright form automation.
Uses real browser session cookies (AWS WAF requires a real prior session).
The /bootstrap endpoint captures cookies from a headless login attempt;
for WAF-protected accounts, use /sync-chrome-session instead.
"""
from __future__ import annotations
import logging
import os
import tempfile
from typing import Optional

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    async_playwright = None
    Page = None

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

# Category map: (cat1_id, bucket_id, cat3_id) for common clothing types
# cat1=621 (Kleding Dames), bucket/cat2 varies, cat3 = leaf category
_CATEGORY_CONFIGS = {
    "marktplaats": {
        "home_url": "https://www.marktplaats.nl",
        "login_url": "https://www.marktplaats.nl/identity/v2/login",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "locale": "nl-NL",
        # Default clothing category: Kleding Dames > Kleding > Spijkerbroeken
        "cat1": "621",
        "bucket": "162",
        "cat3": "636",
    },
    "2dehands": {
        "home_url": "https://www.2dehands.be",
        "login_url": "https://www.2dehands.be/identity/v2/login",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "locale": "nl-BE",
        "cat1": "621",
        "bucket": "162",
        "cat3": "636",
    },
}

_CONDITION_MAP = {
    "new": "Nieuw",
    "good": "Zo goed als nieuw",
    "fair": "Gedragen",
    "poor": "Beschadigd",
}

# EU-required manufacturer fields — use Revaleur as responsible party
_DEFAULT_MANUFACTURER = {
    "name": "Revaleur",
    "address": "4614RG Bergenop Zoom, Nederland",
    "email": "info@revaleur.com",
}


class MarktplaatsPlatform(PlatformBase):
    platform_name = "marktplaats"

    def __init__(self, platform: str = "marktplaats"):
        self._platform = platform
        self._cfg = _CATEGORY_CONFIGS[platform]

    def _extract_cookies(self, credentials: dict) -> dict:
        extra = credentials.get("extra_data") or {}
        return extra.get("cookies") or {}

    async def bootstrap_session(self, email: str, password: str) -> dict:
        """
        Attempt headless login. Works for 2dehands; for Marktplaats
        the AWS WAF may block the headless browser — use sync_from_chrome instead.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._cfg["user_agent"],
                locale=self._cfg["locale"],
            )
            page = await context.new_page()
            if HAS_STEALTH:
                await stealth_async(page)

            await page.goto(self._cfg["login_url"], wait_until="networkidle", timeout=25000)

            for sel in ['[data-testid="gdpr-consent-accept"]', 'button:has-text("Akkoord")']:
                try:
                    await page.click(sel, timeout=2000)
                    break
                except Exception:
                    pass

            for sel in ['input[name="email"]', 'input[type="email"]', '#email']:
                try:
                    await page.fill(sel, email, timeout=3000)
                    break
                except Exception:
                    pass

            for sel in ['input[name="password"]', 'input[type="password"]', '#password']:
                try:
                    await page.fill(sel, password, timeout=3000)
                    break
                except Exception:
                    pass

            await page.keyboard.press("Enter")
            await page.wait_for_load_state("networkidle", timeout=20000)

            # Verify we're actually logged in
            if "login" in page.url or "identity" in page.url:
                await browser.close()
                raise RuntimeError(
                    f"Login failed for {self._platform} — "
                    "AWS WAF may be blocking headless login. "
                    "Use POST /api/platforms/marktplaats/sync-chrome-session instead."
                )

            cookies = await context.cookies()
            await browser.close()

        cookie_dict = {c["name"]: c["value"] for c in cookies}
        logger.info(f"{self._platform} bootstrap: {len(cookie_dict)} cookies captured")
        return {"cookies": cookie_dict, "user_agent": self._cfg["user_agent"]}

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        """
        Fill and submit the ad form via Playwright.
        Requires valid session cookies (from Chrome or successful bootstrap).
        """
        cookies = self._extract_cookies(credentials)
        if not cookies:
            raise ValueError(f"{self._platform}: no session cookies — run bootstrap or sync-chrome-session first")

        cat1 = str(item.get("mp_cat1", self._cfg["cat1"]))
        bucket = str(item.get("mp_bucket", self._cfg["bucket"]))
        cat3 = str(item.get("mp_cat3", self._cfg["cat3"]))
        place_url = f"{self._cfg['home_url']}/plaats/{cat1}/{cat3}?bucketId={bucket}&title="

        listing_id: Optional[str] = None
        listing_url: Optional[str] = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._cfg["user_agent"],
                locale=self._cfg["locale"],
                viewport={"width": 1920, "height": 1080},
            )

            domain = self._cfg["home_url"].replace("https://www.", "")
            await context.add_cookies([
                {"name": k, "value": v, "domain": f".{domain}", "path": "/", "secure": True, "sameSite": "Lax"}
                for k, v in cookies.items()
            ])

            page = await context.new_page()

            # Track redirect — capture both /seller/view/m* and /v/*-m* patterns
            seen_urls = []

            async def on_navigation(frame):
                if frame == page.main_frame:
                    seen_urls.append(frame.url)

            page.on("framenavigated", on_navigation)

            await page.goto(place_url, wait_until="networkidle", timeout=30000)

            if "login" in page.url or "identity" in page.url:
                await browser.close()
                raise SessionExpiredError(
                    f"{self._platform} session expired — run bootstrap or sync-chrome-session"
                )

            # Upload photos first
            for photo_url in item.get("photo_urls", [])[:10]:
                try:
                    await self._upload_photo(page, photo_url)
                except Exception as e:
                    logger.warning(f"Photo upload failed ({photo_url}): {e}")

            # Title — use Playwright fill to trigger React state
            await page.locator('input[name="title_nl-NL"]').fill(item["title"][:60])

            # Dump testids to diagnose selector issues
            testids = await page.evaluate("""() =>
                [...document.querySelectorAll('[data-testid]')]
                    .map(e => e.getAttribute('data-testid'))
            """)
            logger.debug(f"{self._platform}: data-testids on page: {testids}")

            # Description — scroll into view then JS click + keyboard type
            desc_text = (item.get("description") or "")[:2000]
            desc_filled = False
            for desc_sel in [
                '[data-testid="text-editor-input_nl-NL"]',
                '[contenteditable="true"]',
            ]:
                try:
                    desc_el = page.locator(desc_sel).first
                    if await desc_el.count() == 0:
                        continue
                    # Scroll into view and focus via JS (bypasses viewport check)
                    await desc_el.evaluate("el => { el.scrollIntoView(); el.focus(); el.click(); }")
                    await page.wait_for_timeout(300)
                    await page.keyboard.type(desc_text, delay=5)
                    desc_filled = True
                    logger.info(f"{self._platform}: description filled via {desc_sel}")
                    break
                except Exception as e:
                    logger.warning(f"{self._platform}: desc selector {desc_sel} failed: {e}")
            if not desc_filled:
                logger.warning(f"{self._platform}: all description selectors failed")

            # Price
            await page.locator('input[name="price.value"]').fill(str(item["price"]))

            # Manufacturer fields (appear in some browser contexts — fill if present)
            mf = item.get("manufacturer") or _DEFAULT_MANUFACTURER
            for name, val in [
                ("textAttribute[manufacturerTradename]", mf.get("name", _DEFAULT_MANUFACTURER["name"])),
                ("textAttribute[manufacturerAddress]", mf.get("address", _DEFAULT_MANUFACTURER["address"])),
                ("textAttribute[manufacturerEmail]", mf.get("email", _DEFAULT_MANUFACTURER["email"])),
            ]:
                try:
                    el = page.locator(f'input[name="{name}"]').first
                    if await el.count() > 0:
                        await el.fill(val, timeout=2000)
                except Exception:
                    pass

            # Delivery and bundle via JS (force click, avoids viewport issues)
            await page.evaluate("""() => {
                const d = [...document.querySelectorAll('input[type="radio"]')]
                    .find(r => r.value === 'Ophalen of Verzenden');
                if (d) d.click();
                const g = [...document.querySelectorAll('input[type="radio"]')]
                    .find(r => r.value === 'FREE');
                if (g) g.click();
            }""")

            await page.wait_for_timeout(500)

            # Log form state before submit
            form_state = await page.evaluate("""() => ({
                title: document.querySelector('input[name="title_nl-NL"]')?.value,
                price: document.querySelector('input[name="price.value"]')?.value,
                desc: document.querySelector('[data-testid="text-editor-input_nl-NL"]')?.textContent,
                submitBtn: !!document.querySelector('button[type="submit"]'),
            })""")
            logger.info(f"{self._platform} form state before submit: {form_state}")

            # Submit
            await page.evaluate("document.querySelector('button[type=\"submit\"]').click()")
            await page.wait_for_timeout(8000)

            # Extract listing ID from any URL seen during/after submit
            final_url = page.url
            all_urls = seen_urls + [final_url]
            logger.info(f"{self._platform}: URLs seen after submit: {all_urls}")

            import re
            for url in all_urls:
                # /seller/view/m1234567890
                m = re.search(r'/seller/view/(m\d+)', url)
                if m:
                    listing_id = m.group(1)
                    break
                # /v/category/slug/m1234567890-title or /v/...m1234567890
                m = re.search(r'/(m\d{8,})', url)
                if m:
                    listing_id = m.group(1)
                    break

            await browser.close()

        if not listing_id:
            raise RuntimeError(
                f"{self._platform}: form submit didn't result in a listing. Last URL: {final_url}, seen: {all_urls}"
            )

        return {
            "platform_listing_id": listing_id,
            "platform_listing_url": f"{self._cfg['home_url']}/seller/view/{listing_id}",
        }

    async def _fill_input(self, page: Page, selector: str, value: str):
        try:
            el = page.locator(selector).first
            await el.fill(value, timeout=3000)
        except Exception:
            pass

    async def _fill_named_input(self, page: Page, name: str, value: str):
        try:
            el = page.locator(f'input[name="{name}"]').first
            await el.fill(value, timeout=3000)
        except Exception:
            pass

    async def _click_label_or_radio(self, page: Page, text: str):
        try:
            el = page.locator(f'label:has-text("{text}"), span:text-is("{text}")').first
            await el.click(timeout=2000)
        except Exception:
            pass

    async def _click_radio_by_value(self, page: Page, value: str):
        try:
            el = page.locator(f'input[type="radio"][value="{value}"]').first
            await el.click(timeout=1000)
        except Exception:
            pass

    async def _upload_photo(self, page: Page, photo_url: str):
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(photo_url, timeout=15)
            resp.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(resp.content)
            tmp = f.name

        try:
            file_input = page.locator('input[type="file"]').first
            await file_input.set_input_files(tmp, timeout=5000)
            await page.wait_for_timeout(2000)
        finally:
            os.unlink(tmp)

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        """Navigate to /seller/view/{id} and click Verwijder."""
        cookies = self._extract_cookies(credentials)
        mgmt_url = f"{self._cfg['home_url']}/seller/view/{platform_listing_id}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self._cfg["user_agent"])
            domain = self._cfg["home_url"].replace("https://www.", "")
            await context.add_cookies([
                {"name": k, "value": v, "domain": f".{domain}", "path": "/"}
                for k, v in cookies.items()
            ])
            page = await context.new_page()
            await page.goto(mgmt_url, wait_until="networkidle", timeout=20000)

            deleted = False
            # Click Verwijder button
            for text in ["Verwijder", "Verwijderen", "Delete"]:
                try:
                    btn = page.locator(f'button:has-text("{text}")').first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        # Confirm if dialog appears
                        for confirm_text in ["Bevestigen", "Ja", "Verwijder"]:
                            try:
                                confirm = page.locator(f'button:has-text("{confirm_text}")').first
                                if await confirm.is_visible(timeout=2000):
                                    await confirm.click()
                                    await page.wait_for_timeout(2000)
                            except Exception:
                                pass
                        deleted = "deleteAdSuccess" in page.url or "delete" in page.url.lower()
                        break
                except Exception:
                    pass

            await browser.close()
            return deleted

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        """Check if listing still exists via /seller/view/{id}."""
        from curl_cffi.requests import AsyncSession
        cookies = self._extract_cookies(credentials)
        url = f"{self._cfg['home_url']}/seller/view/{platform_listing_id}"
        async with AsyncSession(impersonate="chrome120") as s:
            resp = await s.get(url, cookies=cookies, timeout=10)
            if resp.status_code == 404:
                return "not_found"
            text = resp.text
            if "verkocht" in text.lower() or "niet meer beschikbaar" in text.lower():
                return "sold"
            if resp.status_code == 200:
                return "active"
        return "error"

    async def refresh_credentials(self, credentials: dict) -> dict:
        extra = credentials.get("extra_data") or {}
        email = extra.get("email")
        password = extra.get("password")
        if not email or not password:
            raise ValueError(f"{self._platform}: missing email/password for re-bootstrap")
        session = await self.bootstrap_session(email, password)
        return {**credentials, "extra_data": {**extra, **session}}


class TweedehandsPlatform(MarktplaatsPlatform):
    platform_name = "2dehands"

    def __init__(self):
        super().__init__(platform="2dehands")


class SessionExpiredError(Exception):
    pass
