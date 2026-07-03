"""
Vinted internal API integration.
Uses Playwright Stealth for session bootstrapping to pass Datadome bot detection.
All subsequent calls use curl-cffi with captured cookies (Chrome TLS fingerprint).
"""
from __future__ import annotations
import json
import logging
from typing import Optional
try:
    from curl_cffi.requests import AsyncSession
except ImportError:
    AsyncSession = None
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

VINTED_BASE = "https://www.vinted.nl"
API_BASE = f"{VINTED_BASE}/api/v2"


class VintedPlatform(PlatformBase):
    platform_name = "vinted"

    async def bootstrap_session(self, email: str, password: str) -> dict:
        """
        Log in via Playwright Stealth, capture session cookies.
        Only call this when stored session returns 403.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            if HAS_STEALTH:
                await stealth_async(page)

            await page.goto(f"{VINTED_BASE}/login")
            await page.fill('input[name="username"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{VINTED_BASE}/**", timeout=15000)

            cookies = await context.cookies()
            await browser.close()

        cookie_dict = {c["name"]: c["value"] for c in cookies}
        return {
            "cookies": cookie_dict,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    def _extract_session(self, credentials: dict) -> tuple:
        """Extract cookies and user_agent from credentials (may be nested in extra_data)."""
        extra = credentials.get("extra_data") or {}
        cookies = credentials.get("cookies") or extra.get("cookies") or {}
        ua = credentials.get("user_agent") or extra.get("user_agent") or ""
        return cookies, ua

    def _build_headers(self, credentials: dict) -> dict:
        _, ua = self._extract_session(credentials)
        return {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "nl-NL,nl;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }

    async def _get(self, path: str, credentials: dict) -> dict:
        cookies, _ = self._extract_session(credentials)
        async with AsyncSession(impersonate="chrome120") as s:
            resp = await s.get(
                f"{API_BASE}{path}",
                headers=self._build_headers(credentials),
                cookies=cookies,
            )
            if resp.status_code == 401 or resp.status_code == 403:
                raise SessionExpiredError("Vinted session expired")
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, payload: dict, credentials: dict) -> dict:
        cookies, _ = self._extract_session(credentials)
        async with AsyncSession(impersonate="chrome120") as s:
            resp = await s.post(
                f"{API_BASE}{path}",
                json=payload,
                headers=self._build_headers(credentials),
                cookies=cookies,
            )
            if resp.status_code == 401 or resp.status_code == 403:
                raise SessionExpiredError("Vinted session expired")
            resp.raise_for_status()
            return resp.json()

    async def _delete(self, path: str, credentials: dict) -> bool:
        cookies, _ = self._extract_session(credentials)
        async with AsyncSession(impersonate="chrome120") as s:
            resp = await s.delete(
                f"{API_BASE}{path}",
                headers=self._build_headers(credentials),
                cookies=cookies,
            )
            if resp.status_code == 401 or resp.status_code == 403:
                raise SessionExpiredError("Vinted session expired")
            return resp.status_code in (200, 204)

    async def upload_photo(self, photo_url: str, credentials: dict) -> int:
        """Upload a photo by URL to Vinted's CDN. Returns photo_id."""
        import httpx
        async with httpx.AsyncClient() as client:
            img_resp = await client.get(photo_url)
            img_bytes = img_resp.content
            content_type = img_resp.headers.get("content-type", "image/jpeg")

        cookies, _ = self._extract_session(credentials)
        async with AsyncSession(impersonate="chrome120") as s:
            resp = await s.post(
                f"{API_BASE}/photos",
                files={"file": ("photo.jpg", img_bytes, content_type)},
                headers=self._build_headers(credentials),
                cookies=cookies,
            )
            if resp.status_code in (401, 403):
                raise SessionExpiredError("Vinted session expired")
            resp.raise_for_status()
            return resp.json()["photo"]["id"]

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        photo_ids = []
        for url in item.get("photo_urls", [])[:20]:
            try:
                pid = await self.upload_photo(url, credentials)
                photo_ids.append({"id": pid})
            except Exception as e:
                logger.warning(f"Photo upload failed for {url}: {e}")

        payload = {
            "item": {
                "title": item["title"][:60],
                "description": (item.get("description") or "")[:2000],
                "price": item["price"],
                "currency": "EUR",
                "category_id": item.get("vinted_category_id"),
                "brand_id": item.get("vinted_brand_id"),
                "size_id": item.get("vinted_size_id"),
                "status_id": {"new": 1, "good": 2, "fair": 3, "poor": 4}.get(
                    item.get("condition", "good"), 2
                ),
                "photos": photo_ids,
                "color_ids": item.get("vinted_color_ids", []),
                "is_for_swap": False,
                "is_hidden": False,
            }
        }
        result = await self._post("/items", payload, credentials)
        item_data = result.get("item", {})
        return {
            "platform_listing_id": str(item_data["id"]),
            "platform_listing_url": item_data.get("url", ""),
        }

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        return await self._delete(f"/items/{platform_listing_id}", credentials)

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        try:
            data = await self._get(f"/items/{platform_listing_id}", credentials)
            item = data.get("item", {})
            if item.get("can_be_sold") is False or item.get("is_closed"):
                return "sold"
            return "active"
        except SessionExpiredError:
            raise
        except Exception as e:
            if "404" in str(e):
                return "not_found"
            logger.error(f"Vinted status check failed: {e}")
            return "error"

    async def refresh_credentials(self, credentials: dict) -> dict:
        # For Vinted, refreshing means a new Playwright bootstrap.
        # Caller must provide email/password stored in platform_credentials.extra_data.
        extra = credentials.get("extra_data", {})
        email = extra.get("email")
        password = extra.get("password")
        if not email or not password:
            raise ValueError("Vinted credentials missing email/password for re-bootstrap")
        new_session = await self.bootstrap_session(email, password)
        return {**credentials, **new_session}


class SessionExpiredError(Exception):
    pass
