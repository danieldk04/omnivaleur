"""
Shopify Admin API — reads and writes products on a Shopify store.
Uses client credentials (Client ID + Secret) with 24h token caching.
"""
from __future__ import annotations
import logging
import re
import time
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)

_token_cache: dict = {"token": None, "expires_at": 0}


async def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{settings.shopify_store}/admin/oauth/access_token",
            json={
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    token = data["access_token"]
    expires_in = data.get("expires_in", 86400)
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in
    logger.info("Shopify token refreshed, expires in %ds", expires_in)
    return token


async def list_products(limit: int = 50, page_info: str | None = None) -> dict:
    token = await _get_token()
    params: dict = {"limit": limit, "status": "active"}
    if page_info:
        params["page_info"] = page_info

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://{settings.shopify_store}/admin/api/2024-10/products.json",
            params=params,
            headers={"X-Shopify-Access-Token": token},
        )
        resp.raise_for_status()

    products = resp.json().get("products", [])
    next_page = None
    link_header = resp.headers.get("link", "")
    if 'rel="next"' in link_header:
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip().strip("<>")
                for q in url_part.split("&"):
                    if q.startswith("page_info="):
                        next_page = q.split("=", 1)[1]

    return {"products": [_convert(p) for p in products], "next_page": next_page}


async def get_product(product_id: str) -> dict:
    token = await _get_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://{settings.shopify_store}/admin/api/2024-10/products/{product_id}.json",
            headers={"X-Shopify-Access-Token": token},
        )
        resp.raise_for_status()
    return _convert(resp.json()["product"])


async def create_product(item: dict) -> dict:
    """Create a product on Shopify from a CrossList item dict."""
    token = await _get_token()

    body_html = item.get("description", "")
    if not body_html:
        parts = []
        if item.get("material"):
            parts.append(f"Material: {item['material']}")
        if item.get("condition"):
            parts.append(f"Condition: {item['condition']}")
        body_html = "<br>".join(parts)

    tags = []
    if item.get("brand"):
        tags.append(item["brand"])
    if item.get("material"):
        tags.append(item["material"])
    if item.get("size"):
        tags.append(item["size"])

    payload = {
        "product": {
            "title": item.get("shopify_title") or item["title"],
            "body_html": body_html,
            "vendor": item.get("brand", ""),
            "tags": ", ".join(tags),
            "status": "active",
            "variants": [{
                "price": str(item.get("price", "0")),
                "compare_at_price": str(item["compare_at_price"]) if item.get("compare_at_price") else None,
                "sku": item.get("sku", ""),
                "inventory_management": None,
            }],
            "images": [{"src": url} for url in item.get("photo_urls", [])[:10]],
        }
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{settings.shopify_store}/admin/api/2024-10/products.json",
            json=payload,
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        product = resp.json()["product"]

    product_id = str(product["id"])
    handle = product.get("handle", product_id)
    return {
        "platform_listing_id": product_id,
        "platform_listing_url": f"https://{settings.shopify_store}/products/{handle}",
    }


async def delete_product(product_id: str) -> bool:
    token = await _get_token()
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"https://{settings.shopify_store}/admin/api/2024-10/products/{product_id}.json",
            headers={"X-Shopify-Access-Token": token},
        )
    return resp.status_code in (200, 204)


_DESC_FIELDS = {
    "material": re.compile(r"Material:\s*([^\n<]+)", re.IGNORECASE),
    "size": re.compile(r"\b(XS|S|M|L|XL|XXL|XXXL|XXS|\d{2,3})\b"),
    "color": re.compile(r"comes in ([a-z]+)!", re.IGNORECASE),
}

_BRAND_KEYWORDS = [
    "Ralph Lauren", "Massimo Dutti", "Suitsupply", "Profuomo",
    "Stone Island", "Zara", "Mango", "Gymshark", "North Face",
]


def _convert(p: dict) -> dict:
    variant = p.get("variants", [{}])[0]
    images = [img["src"] for img in p.get("images", [])]
    tags = [t.strip() for t in p.get("tags", "").split(",") if t.strip()]
    title = p.get("title", "")
    desc_raw = p.get("body_html", "")
    import html
    desc_text = re.sub(r"<[^>]+>", " ", desc_raw)
    desc_text = html.unescape(desc_text)

    size = None
    color = None
    material = None
    brand = None

    for opt in p.get("options", []):
        name = opt.get("name", "").lower()
        values = [v for v in opt.get("values", []) if v and v != "Default Title"]
        if "size" in name and values:
            size = values[0]
        elif ("color" in name or "colour" in name) and values:
            color = values[0]
        elif "material" in name and values:
            material = values[0]

    if not material:
        m = _DESC_FIELDS["material"].search(desc_text)
        if m:
            material = m.group(1).strip().rstrip(".")

    if not color:
        m = _DESC_FIELDS["color"].search(desc_text)
        if m:
            color = m.group(1).strip()

    if not size:
        parts = title.split(" - ")
        if len(parts) >= 2:
            size = parts[1].strip()

    for b in _BRAND_KEYWORDS:
        if b.lower() in title.lower():
            brand = b
            break

    for tag in tags:
        tl = tag.lower()
        if tl.startswith("brand:"):
            brand = tag.split(":", 1)[1].strip()
        elif tl.startswith("material:"):
            material = tag.split(":", 1)[1].strip()

    price_raw = variant.get("price", "0")
    try:
        price = float(price_raw)
    except ValueError:
        price = 0.0

    return {
        "shopify_id": str(p["id"]),
        "title": p.get("title", ""),
        "description": p.get("body_html", ""),
        "price": price,
        "photo_urls": images,
        "size": size,
        "color": color,
        "material": material,
        "brand": brand,
        "tags": tags,
        "sku": variant.get("sku") or str(p["id"]),
        "shopify_handle": p.get("handle", ""),
    }
