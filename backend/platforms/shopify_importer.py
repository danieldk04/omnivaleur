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


# Category words that describe a garment group ("jassen", "truien") rather than
# an audience segment — audience words would swamp the token-overlap match (every
# women's item would "match" every other women's collection) so they're excluded.
_STOPWORDS = {
    "heren", "dames", "kinderen", "unisex", "the", "a", "an", "for", "and", "of",
    "men", "mens", "women", "womens", "kids", "sport", "casual",
}


def _product_type_from_item(item: dict) -> str:
    """Best-effort Shopify `product_type` — the field Shopify's own smart
    collections match on via a "product type is X" rule. Our category taxonomy
    is Dutch and audience-prefixed (e.g. "heren jassen", "dames truien"); take
    the last word, which is always the actual garment, so it reads as a normal
    product type rather than exposing the internal Dutch taxonomy verbatim."""
    category = (item.get("category") or "").strip()
    if category:
        return category.split()[-1].capitalize()
    return (item.get("item_type") or "").strip().capitalize()


def _match_collection_id(item: dict, collections: list[dict]) -> int | None:
    """Keyword-in-title heuristic: pick the custom collection whose title shares
    the most meaningful words with the item's category/title/brand. No LLM call —
    this only needs to be roughly right, and a wrong guess (skipping assignment)
    is far safer than assigning to the wrong collection."""
    tokens: set[str] = set()
    for field in (item.get("category"), item.get("title"), item.get("brand")):
        if field:
            tokens.update(
                w for w in re.findall(r"[a-zA-Z]+", str(field).lower())
                if w not in _STOPWORDS and len(w) > 2
            )
    if not tokens or not collections:
        return None

    best_id, best_score = None, 0
    for c in collections:
        title_tokens = {
            w for w in re.findall(r"[a-zA-Z]+", (c.get("title") or "").lower())
            if w not in _STOPWORDS
        }
        score = len(tokens & title_tokens)
        if score > best_score:
            best_score, best_id = score, c.get("id")
    return best_id if best_score > 0 else None


async def _get_custom_collections(base_url: str, headers: dict) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{base_url}/custom_collections.json", params={"limit": 250}, headers=headers
            )
            resp.raise_for_status()
            return resp.json().get("custom_collections", [])
    except Exception as e:
        logger.warning(f"Shopify: failed to fetch custom collections: {e}")
        return []


async def _assign_to_collection(base_url: str, headers: dict, product_id: str, collection_id) -> None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/collects.json",
                json={"collect": {"product_id": int(product_id), "collection_id": collection_id}},
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.warning(f"Shopify: collect assignment failed ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.warning(f"Shopify: collect assignment error: {e}")


async def assign_best_collection(base_url: str, headers: dict, item: dict, product_id: str) -> None:
    """Auto-detect & assign the best-matching custom collection for a newly
    created product. Smart collections auto-populate from their own rules and
    can't be assigned to directly (see `_product_type_from_item`), so only
    custom/manual collections are targeted here. Best-effort — never raises."""
    collections = await _get_custom_collections(base_url, headers)
    collection_id = _match_collection_id(item, collections)
    if collection_id:
        await _assign_to_collection(base_url, headers, product_id, collection_id)
        logger.info(f"Shopify: assigned product {product_id} to collection {collection_id}")


def _public_photo_urls(item: dict) -> list[str]:
    """Only http(s) URLs are usable — Shopify fetches every image server-side, so a
    blob:/data:/local path (e.g. a photo the frontend hasn't finished uploading yet)
    would silently fail to attach. Shopify's own product image limit is 250, far
    above what any listing here has, so nothing is truncated below that."""
    urls = item.get("photo_urls") or []
    return [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))][:250]


async def create_product(item: dict) -> dict:
    """Create a product on Shopify from a Omnivaleur item dict."""
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
            "product_type": _product_type_from_item(item),
            "tags": ", ".join(tags),
            "status": "active",
            "variants": [{
                "price": str(item.get("price", "0")),
                "compare_at_price": str(item["compare_at_price"]) if item.get("compare_at_price") else None,
                "sku": item.get("sku", ""),
                "inventory_management": None,
            }],
            "images": [{"src": url} for url in _public_photo_urls(item)],
        }
    }

    # Shopify fetches every image URL server-side while creating the product, so
    # a listing with several photos regularly needs far more than httpx's default
    # 5s read timeout — that default is exactly what surfaced as
    # "Shopify: ReadTimeout: ReadTimeout('')" in the dashboard. Give it room.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        resp = await client.post(
            f"https://{settings.shopify_store}/admin/api/2024-10/products.json",
            json=payload,
            headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        product = resp.json()["product"]

    product_id = str(product["id"])
    handle = product.get("handle", product_id)

    await assign_best_collection(
        f"https://{settings.shopify_store}/admin/api/2024-10",
        {"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        item,
        product_id,
    )

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
