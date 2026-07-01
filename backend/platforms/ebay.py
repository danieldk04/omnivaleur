"""
eBay REST API integration (Sell Inventory API).
Requires free developer account at developer.ebay.com.
Uses OAuth2 with long-lived refresh tokens (18 months).
"""
from __future__ import annotations
import base64
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode
import httpx
from backend.config import settings
from backend.platforms.base import PlatformBase

logger = logging.getLogger(__name__)

# eBay exposes parallel sandbox/production environments with different hosts.
# Toggle via settings.ebay_sandbox while testing against a sandbox developer account.
if settings.ebay_sandbox:
    AUTH_URL = "https://auth.sandbox.ebay.com/oauth2/authorize"
    TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    INVENTORY_API = "https://api.sandbox.ebay.com/sell/inventory/v1"
else:
    AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    INVENTORY_API = "https://api.ebay.com/sell/inventory/v1"

SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
]


class EbayCategoryRequiredError(Exception):
    """Raised when an item has no eBay category and no default is configured."""


class EbayPlatform(PlatformBase):
    platform_name = "ebay"

    def get_authorization_url(self) -> str:
        if not settings.ebay_app_id:
            raise RuntimeError(
                "eBay is not configured yet: set EBAY_APP_ID and EBAY_CERT_ID "
                "(from developer.ebay.com) before connecting an eBay account."
            )
        params = {
            "client_id": settings.ebay_app_id,
            "redirect_uri": settings.ebay_redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def _basic_auth(self) -> str:
        raw = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
        return base64.b64encode(raw.encode()).decode()

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {self._basic_auth()}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.ebay_redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh_credentials(self, credentials: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {self._basic_auth()}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": credentials["refresh_token"],
                    "scope": " ".join(SCOPES),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {**credentials, "access_token": data["access_token"]}

    def _auth_headers(self, credentials: dict) -> dict:
        return {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
            "Accept-Language": "nl-NL",
        }

    async def _ensure_fresh_token(self, credentials: dict) -> dict:
        expires_at = credentials.get("token_expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                return await self.refresh_credentials(credentials)
        return credentials

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        credentials = await self._ensure_fresh_token(credentials)
        sku = item.get("sku") or item["id"]

        category_id = item.get("ebay_category_id") or settings.ebay_default_category_id
        if not category_id:
            raise EbayCategoryRequiredError(
                f"Item '{item.get('title', sku)}' has no eBay category. "
                "Set an eBay category ID on the item (look it up at "
                "https://www.ebay.com/sh/lst/categories) or configure "
                "EBAY_DEFAULT_CATEGORY_ID as a fallback."
            )

        # Step 1: Create inventory item
        aspects = {
            "Brand": [item["brand"]] if item.get("brand") else ["Unbranded"],
        }
        if item.get("size"):
            aspects["Size"] = [item["size"]]
        if item.get("color"):
            aspects["Colour"] = [item["color"]]
        if item.get("material"):
            aspects["Material"] = [item["material"]]

        inventory_payload = {
            "product": {
                "title": item["title"][:80],
                "description": item.get("description", ""),
                "imageUrls": item.get("photo_urls", [])[:12],
                "aspects": aspects,
            },
            "condition": _map_condition(item.get("condition", "good")),
            "availability": {
                "shipToLocationAvailability": {"quantity": 1}
            },
        }

        async with httpx.AsyncClient() as client:
            inv_resp = await client.put(
                f"{INVENTORY_API}/inventory_item/{sku}",
                json=inventory_payload,
                headers=self._auth_headers(credentials),
            )
            _raise_with_ebay_error(inv_resp, "creating inventory item")

            # Step 2: Create offer
            offer_payload = {
                "sku": sku,
                "marketplaceId": settings.ebay_marketplace_id,
                "format": "FIXED_PRICE",
                "pricingSummary": {
                    "price": {"value": str(item["price"]), "currency": "EUR"}
                },
                "categoryId": category_id,
                "listingDescription": item.get("description", ""),
                "quantityLimitPerBuyer": 1,
            }
            offer_resp = await client.post(
                f"{INVENTORY_API}/offer",
                json=offer_payload,
                headers=self._auth_headers(credentials),
            )
            _raise_with_ebay_error(offer_resp, "creating offer")
            offer_id = offer_resp.json()["offerId"]

            # Step 3: Publish offer
            pub_resp = await client.post(
                f"{INVENTORY_API}/offer/{offer_id}/publish",
                headers=self._auth_headers(credentials),
            )
            _raise_with_ebay_error(pub_resp, "publishing offer")
            listing_id = pub_resp.json().get("listingId", offer_id)

        domain = _MARKETPLACE_DOMAINS.get(settings.ebay_marketplace_id, "ebay.com")
        return {
            "platform_listing_id": listing_id,
            "platform_listing_url": f"https://www.{domain}/itm/{listing_id}",
        }

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        credentials = await self._ensure_fresh_token(credentials)
        async with httpx.AsyncClient() as client:
            # End the listing via the Trading API fallback approach
            resp = await client.delete(
                f"{INVENTORY_API}/offer/{platform_listing_id}",
                headers=self._auth_headers(credentials),
            )
            return resp.status_code in (200, 204)

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        credentials = await self._ensure_fresh_token(credentials)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{INVENTORY_API}/offer/{platform_listing_id}",
                headers=self._auth_headers(credentials),
            )
            if resp.status_code == 404:
                return "not_found"
            if not resp.is_success:
                return "error"
            status = resp.json().get("status", "").upper()
            if status in ("ENDED", "SOLD"):
                return "sold"
            return "active"


def _map_condition(condition: str) -> str:
    return {
        "new": "NEW",
        "good": "USED_EXCELLENT",
        "fair": "USED_GOOD",
        "poor": "USED_ACCEPTABLE",
    }.get(condition, "USED_EXCELLENT")
