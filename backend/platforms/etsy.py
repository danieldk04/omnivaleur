"""
Etsy v3 API integration.
Requires: ETSY_CLIENT_ID env var + OAuth2 user token.
"""
from __future__ import annotations
import logging
import os
import httpx
from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

ETSY_CLIENT_ID = os.getenv("ETSY_CLIENT_ID", "")
ETSY_BASE = "https://openapi.etsy.com/v3"

CONDITION_MAP = {"new": "not_specified", "good": "not_specified", "fair": "not_specified", "poor": "not_specified"}


class EtsyPlatform(PlatformBase):
    platform_name = "etsy"

    def _token(self, credentials: dict) -> str:
        return credentials.get("access_token") or (credentials.get("extra_data") or {}).get("access_token", "")

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "x-api-key": ETSY_CLIENT_ID,
            "Content-Type": "application/json",
        }

    def get_authorization_url(self, state: str = "") -> str:
        from urllib.parse import urlencode
        import secrets
        code_verifier = secrets.token_urlsafe(32)
        params = {
            "response_type": "code",
            "client_id": ETSY_CLIENT_ID,
            "redirect_uri": os.getenv("ETSY_REDIRECT_URI", ""),
            "scope": "listings_w listings_r",
            "state": state or secrets.token_urlsafe(8),
            "code_challenge": code_verifier,
            "code_challenge_method": "plain",
        }
        return f"https://www.etsy.com/oauth/connect?{urlencode(params)}", code_verifier

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": ETSY_CLIENT_ID,
                    "redirect_uri": os.getenv("ETSY_REDIRECT_URI", ""),
                    "code": code,
                    "code_verifier": code_verifier,
                },
            )
            r.raise_for_status()
            return r.json()

    async def refresh_credentials(self, credentials: dict) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://api.etsy.com/v3/public/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": ETSY_CLIENT_ID,
                    "refresh_token": credentials.get("refresh_token"),
                },
            )
            r.raise_for_status()
            data = r.json()
            return {**credentials, "access_token": data["access_token"], "refresh_token": data.get("refresh_token")}

    async def _get_shop_id(self, token: str) -> str:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{ETSY_BASE}/application/users/me/shops", headers=self._headers(token))
            r.raise_for_status()
            shops = r.json().get("results", [])
            if not shops:
                raise RuntimeError("No Etsy shop found for this account")
            return str(shops[0]["shop_id"])

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)

        payload = {
            "title": item["title"][:140],
            "description": (item.get("description") or "")[:65000],
            "price": float(item["price"]),
            "quantity": 1,
            "who_made": "someone_else",
            "when_made": "2020_2024",
            "taxonomy_id": item.get("etsy_taxonomy_id", 1),
            "should_auto_renew": False,
            "is_taxable": False,
            "listing_type": "physical",
            "currency_code": "EUR",
        }

        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings",
                json=payload,
                headers=self._headers(token),
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy create listing failed {r.status_code}: {r.text}")
            listing = r.json()
            listing_id = str(listing["listing_id"])

            # Upload images
            for photo_url in (item.get("photo_urls") or [])[:10]:
                try:
                    await self._upload_image(c, shop_id, listing_id, photo_url, token)
                except Exception as e:
                    logger.warning(f"Etsy image upload failed: {e}")

        return {
            "platform_listing_id": listing_id,
            "platform_listing_url": f"https://www.etsy.com/listing/{listing_id}",
        }

    async def _upload_image(self, client, shop_id, listing_id, photo_url, token):
        img_resp = await client.get(photo_url)
        img_resp.raise_for_status()
        r = await client.post(
            f"{ETSY_BASE}/application/shops/{shop_id}/listings/{listing_id}/images",
            headers={"Authorization": f"Bearer {token}", "x-api-key": ETSY_CLIENT_ID},
            files={"image": ("photo.jpg", img_resp.content, "image/jpeg")},
        )
        r.raise_for_status()

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        async with httpx.AsyncClient() as c:
            r = await c.delete(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            return r.status_code in (200, 204)

    async def renew_listing(self, platform_listing_id: str, credentials: dict) -> dict:
        """
        Official Etsy renewal: PATCH the listing's state to 'active'. Etsy charges the
        normal listing fee and gives the listing a fresh "listed" timestamp — this is
        Etsy's own renewal mechanism (same one their web UI "Renew" button uses), not
        a workaround. Works for 'sold_out' and 'expired' listings; a currently-active
        listing doesn't need renewing.
        """
        token = self._token(credentials)
        shop_id = await self._get_shop_id(token)
        async with httpx.AsyncClient() as c:
            r = await c.patch(
                f"{ETSY_BASE}/application/shops/{shop_id}/listings/{platform_listing_id}",
                json={"state": "active", "quantity": 1},
                headers=self._headers(token),
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Etsy renew failed {r.status_code}: {r.text}")
            data = r.json()
            return {
                "platform_listing_id": str(data.get("listing_id", platform_listing_id)),
                "state": data.get("state"),
            }

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        token = self._token(credentials)
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{ETSY_BASE}/application/listings/{platform_listing_id}",
                headers=self._headers(token),
            )
            if r.status_code == 404:
                return "not_found"
            data = r.json()
            state = data.get("state", "")
            if state == "active":
                return "active"
            if state == "sold_out":
                return "sold"
            return state
