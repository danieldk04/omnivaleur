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
        raw = item.get("price")
        # Skip when the price is absent — recording 0 would wrongly show the item
        # as "sold for €0.00" and make profit negative. Better to leave it unknown
        # so analytics falls back to the asking price as a confirmable estimate.
        if not sku or raw in (None, ""):
            continue
        try:
            unit = float(raw)
            qty = int(item.get("quantity") or 1)
        except (ValueError, TypeError):
            continue
        if unit <= 0:
            continue
        prices[sku] = round(unit * qty, 2)
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
        from backend.platforms.shopify_importer import (
            _product_type_from_item, _public_photo_urls, assign_best_collection,
            _attach_missing_images, _ensure_stock_of_one,
            _set_taxonomy_category, _publish_to_all_channels,
        )
        raw_desc = item.get("description") or ""
        body_html = raw_desc.replace("\r\n", "\n").replace("\n", "<br>")
        photo_urls = _public_photo_urls(item)
        logger.info(
            "Shopify(client) create_product: sending %d public image URL(s) of %d raw photo_urls; first=%s",
            len(photo_urls), len(item.get("photo_urls") or []), photo_urls[:2],
        )
        payload = {
            "product": {
                "title": item.get("shopify_title") or item["title"],
                "body_html": body_html,
                # Without this Shopify silently falls back to the SHOP NAME, which is
                # why every product showed the store as its vendor instead of the brand.
                "vendor": (item.get("brand") or "").strip(),
                "product_type": _product_type_from_item(item),
                "variants": [{
                    "price": str(item["price"]),
                    "compare_at_price": str(item["compare_at_price"]) if item.get("compare_at_price") else None,
                    "sku": item.get("sku", ""),
                    # Single second-hand piece — track stock at 1 so Shopify sells
                    # it out on its own rather than accepting a second order.
                    "inventory_management": "shopify",
                    "inventory_policy": "deny",
                    "inventory_quantity": 1,
                }],
                "images": [{"src": url} for url in photo_urls],
            }
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as c:
            r = await c.post(f"{self.base}/products.json", json=payload, headers=self.headers)
            r.raise_for_status()
            product = r.json().get("product", {})

        if product.get("id"):
            pid = str(product["id"])
            logger.info(
                "Shopify(client) create_product: product %s created with %d/%d image(s) attached via src",
                pid, len(product.get("images") or []), len(photo_urls),
            )
            await _attach_missing_images(self.base, self.headers, pid, photo_urls, product)
            await _ensure_stock_of_one(self.base, self.headers, product)
            await assign_best_collection(self.base, self.headers, item, pid)
            await _set_taxonomy_category(self.base, self.headers, pid, item)
            await _publish_to_all_channels(self.base, self.headers, pid)

        return product

    async def update_price(self, product_id: str, price: float) -> bool:
        """Write a new price onto the product's variant. Shopify prices live on the
        VARIANT, not the product, so the variant id has to be read back first —
        PUTting a price onto /products/{id}.json without one is silently ignored."""
        import httpx
        if not product_id:
            raise RuntimeError("No Shopify product id on this listing")
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
            r = await c.get(f"{self.base}/products/{product_id}.json", headers=self.headers)
            if r.status_code == 404:
                raise RuntimeError(f"Shopify product {product_id} no longer exists")
            r.raise_for_status()
            variants = (r.json().get("product") or {}).get("variants") or []
            if not variants:
                raise RuntimeError(f"Shopify product {product_id} has no variant to price")
            variant_id = variants[0]["id"]
            u = await c.put(
                f"{self.base}/variants/{variant_id}.json",
                json={"variant": {"id": variant_id, "price": f"{float(price):.2f}"}},
                headers=self.headers,
            )
        if not u.is_success:
            raise RuntimeError(
                f"Shopify refused the price update on variant {variant_id}: "
                f"HTTP {u.status_code} {(u.text or '')[:200]}"
            )
        return True

    async def delete_product(self, product_id: str) -> bool:
        import httpx
        # Returning a bare False here surfaced upstream as "delete_listing returned
        # False" — which says nothing about WHY (wrong store, revoked token, no
        # product id, product already gone). Raise with the status and body so the
        # dashboard shows something the user can actually act on.
        if not product_id:
            raise RuntimeError(
                "No Shopify product id on this listing, so there's nothing to delete. "
                "Re-link the listing (paste its Shopify URL) and try again."
            )
        async with httpx.AsyncClient() as c:
            r = await c.delete(f"{self.base}/products/{product_id}.json", headers=self.headers)
        if r.status_code in (200, 204):
            return True
        if r.status_code == 404:
            # Already gone. Delist means "make sure it isn't there" — so a product
            # that no longer exists is a success, not an error to alarm the user with.
            return True
        raise RuntimeError(
            f"Shopify refused to delete product {product_id} on {self.base}: "
            f"HTTP {r.status_code} {(r.text or '')[:200]}"
        )


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

    async def update_listing_price(self, platform_listing_id: str, price: float, credentials: dict) -> bool:
        shop, token = _shop_creds(credentials)
        if not shop or not token:
            # Same single-store fallback the create/delete paths use: the globally
            # configured store, whose token is fetched (and cached) on demand.
            from backend.platforms.shopify_importer import _get_token
            shop, token = settings.shopify_store, await _get_token()
        if not shop or not token:
            raise RuntimeError("No Shopify store connected")
        return await ShopifyClient(shop, token).update_price(platform_listing_id, price)

    async def refresh_credentials(self, credentials: dict) -> dict:
        return credentials  # Shopify offline access tokens don't expire

    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        return "active"
