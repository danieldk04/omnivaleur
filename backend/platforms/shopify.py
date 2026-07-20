"""
Shopify integration — source of truth for inventory and sales.
Webhooks: orders/paid → auto-delist from all other platforms.
Products: sync inventory from Shopify to Omnivaleur items.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import re
from typing import Optional
from urllib.parse import urlencode
from backend.config import settings

logger = logging.getLogger(__name__)

SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")

_SHOP_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.myshopify\.com$")


def is_valid_shop_domain(shop: str) -> bool:
    """Only allow genuine *.myshopify.com hosts — prevents SSRF via a crafted `shop` param."""
    return bool(_SHOP_DOMAIN_RE.match(shop or ""))


def verify_install_hmac(params: dict) -> bool:
    """Verify the HMAC Shopify attaches to OAuth install/callback redirects."""
    if not settings.shopify_client_secret:
        return True  # skip in dev before app credentials are configured
    received = params.get("hmac", "")
    pairs = sorted((k, v) for k, v in params.items() if k not in ("hmac", "signature"))
    message = "&".join(f"{k}={v}" for k, v in pairs)
    digest = hmac.new(settings.shopify_client_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, received or "")


def verify_webhook(raw_body: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook signature."""
    if not SHOPIFY_WEBHOOK_SECRET:
        return True  # Skip verification in dev
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).digest()
    import base64
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, hmac_header or "")


def extract_skus_from_order(order: dict) -> list[str]:
    """Pull SKUs from a Shopify order's line items."""
    skus = []
    for item in order.get("line_items", []):
        sku = item.get("sku")
        if sku:
            skus.append(sku)
    return skus


def extract_sku_prices_from_order(order: dict) -> dict[str, float]:
    """
    Map each SKU to the amount actually charged for it (unit price × quantity),
    so a sale records what the buyer really paid — not the item's asking price.
    """
    prices: dict[str, float] = {}
    for item in order.get("line_items", []):
        sku = item.get("sku")
        if not sku:
            continue
        try:
            unit = float(item.get("price") or 0)
            qty = int(item.get("quantity") or 1)
            prices[sku] = round(unit * qty, 2)
        except (ValueError, TypeError):
            continue
    return prices


class ShopifyClient:
    """Minimal Shopify Admin API client."""

    def __init__(self, shop_domain: str, access_token: str):
        self.base = f"https://{shop_domain}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    async def get_products(self, limit: int = 250) -> list[dict]:
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.base}/products.json?limit={limit}", headers=self.headers)
            r.raise_for_status()
            return r.json().get("products", [])

    async def create_product(self, item: dict) -> dict:
        import httpx
        raw_desc = item.get("description") or ""
        body_html = raw_desc.replace("\r\n", "\n").replace("\n", "<br>")
        payload = {
            "product": {
                "title": item.get("shopify_title") or item["title"],
                "body_html": body_html,
                "variants": [{"price": str(item["price"]), "sku": item.get("sku", "")}],
                "images": [{"src": url} for url in (item.get("photo_urls") or [])[:10]],
            }
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.base}/products.json", json=payload, headers=self.headers)
            r.raise_for_status()
            return r.json().get("product", {})

    async def delete_product(self, product_id: str) -> bool:
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.delete(f"{self.base}/products/{product_id}.json", headers=self.headers)
            return r.status_code == 200


def shopify_product_to_item(product: dict) -> dict:
    """Map Shopify product fields to our item schema."""
    variant = product.get("variants", [{}])[0]
    images = [img["src"] for img in product.get("images", [])]
    return {
        "title": product.get("title", ""),
        "description": product.get("body_html", ""),
        "price": float(variant.get("price", 0)),
        "sku": variant.get("sku", ""),
        "photo_urls": images,
    }


from backend.platforms.base import PlatformBase
from backend.platforms.shopify_importer import create_product, delete_product


def _shop_creds(credentials: dict) -> tuple[Optional[str], Optional[str]]:
    extra = (credentials or {}).get("extra_data") or {}
    return extra.get("shop_domain"), credentials.get("access_token") if credentials else None


class ShopifyPlatform(PlatformBase):
    platform_name = "shopify"

    def get_authorization_url(self, shop: str, state: str = "") -> str:
        if not settings.shopify_client_id:
            raise RuntimeError(
                "Shopify is not configured yet: set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET "
                "(from a custom app in your Shopify Partner account) before connecting a store."
            )
        params = {
            "client_id": settings.shopify_client_id,
            "scope": settings.shopify_scopes,
            "redirect_uri": settings.shopify_redirect_uri,
            "state": state,
        }
        return f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, shop: str, code: str) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://{shop}/admin/oauth/access_token",
                json={
                    "client_id": settings.shopify_client_id,
                    "client_secret": settings.shopify_client_secret,
                    "code": code,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "access_token": data["access_token"],
            "extra_data": {"shop_domain": shop, "scope": data.get("scope", "")},
        }

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        shop, token = _shop_creds(credentials)
        if not shop or not token:
            # No per-user store connected yet — fall back to the single globally
            # configured store (existing behaviour for the account this was built for).
            return await create_product(item)
        product = await ShopifyClient(shop, token).create_product(item)
        product_id = str(product["id"])
        return {
            "platform_listing_id": product_id,
            "platform_listing_url": f"https://{shop}/products/{product.get('handle', product_id)}",
        }

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        shop, token = _shop_creds(credentials)
        if not shop or not token:
            return await delete_product(platform_listing_id)
        return await ShopifyClient(shop, token).delete_product(platform_listing_id)

    async def refresh_credentials(self, credentials: dict) -> dict:
        return credentials  # Shopify offline access tokens don't expire

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        return "active"
