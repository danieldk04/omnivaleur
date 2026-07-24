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


# Our category slugs are internal, Dutch and audience-prefixed ("heren truien").
# A Shopify storefront is a customer-facing English shop, so publishing "Truien"
# as the product_type leaks the internal taxonomy. Map the garment word of every
# slug in the app's category list to a normal English product type.
_NL_EN_TYPE = {
    "jeans": "Jeans", "broeken": "Trousers", "chinos": "Chinos", "shorts": "Shorts",
    "rokken": "Skirt", "jurken": "Dress", "blouses": "Blouse", "tops": "Top",
    "t-shirts": "T-shirt", "polo's": "Polo Shirt", "overhemden": "Shirt",
    "truien": "Sweater", "hoodies": "Hoodie", "jassen": "Jacket", "pakken": "Suit",
    "sportbroeken": "Sports Shorts", "sportleggings": "Leggings",
    "zwemkleding": "Swimwear", "ondergoed": "Underwear", "bh": "Sports Bra",
    "sneakers": "Sneakers", "schoenen": "Shoes", "hakken": "Heels",
    "laarzen": "Boots", "sandalen": "Sandals", "accessoires": "Accessories",
    "sportkleding": "Sportswear", "babykleding": "Baby Clothing",
    "peuterkleding": "Toddler Clothing", "kleding": "Clothing",
}

# Words that appear in our English titles but are never the garment itself —
# every title ends in "- <size> - <condition>", and colours/conditions sit right
# next to the noun, so without these the "last meaningful word" of
# "Brown Profuomo Turtleneck - Men XL - Very Good" comes out as "Good".
_TITLE_NOISE = {
    "very", "good", "great", "excellent", "perfect", "fair", "poor", "new",
    "used", "vintage", "condition", "size", "black", "white", "brown", "blue",
    "green", "grey", "gray", "beige", "navy", "cream", "pink", "purple", "red",
    "yellow", "orange", "wool", "cotton", "leather", "denim", "silk", "linen",
}


def _english_type_from_category(category: str) -> str:
    """English product type for one of our internal category slugs, or ""."""
    cat = (category or "").strip().lower()
    if not cat:
        return ""
    if cat.startswith("games console"):
        return "Console"
    if cat.startswith("games "):
        return "Video Game"
    if "telefoon" in cat:
        return "Phone"
    for word in reversed(cat.split()):
        if word in _NL_EN_TYPE:
            return _NL_EN_TYPE[word]
    return ""


def _english_type_from_title(title: str) -> str:
    """Garment noun out of an English listing title. Only the part BEFORE the
    first " - " is considered — everything after it is the size/condition suffix
    ("- Men XL - Very Good"), which is why a naive last-word scan returned
    "Good"."""
    head = (title or "").split(" - ")[0]
    words = [
        w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", head)
        if w.lower() not in _STOPWORDS and w.lower() not in _TITLE_NOISE and len(w) > 2
    ]
    return words[-1].capitalize() if words else ""


def _product_type_from_item(item: dict) -> str:
    """Best-effort Shopify `product_type` — the field Shopify's own smart
    collections match on via a "product type is X" rule.

    Order: known Dutch category slug → English type (deterministic, and the
    single most reliable signal), else the item's title, which on the Shopify
    path is always the English-translated title (crosslist puts shopify in
    _ENGLISH_PLATFORMS). `item_type` is only "clothing"/"games"/"electronics" —
    never a garment — so it's the very last resort rather than the first."""
    mapped = _english_type_from_category(item.get("category") or "")
    if mapped:
        return mapped
    from_title = _english_type_from_title(item.get("title") or "")
    if from_title:
        return from_title
    return (item.get("item_type") or "").strip().capitalize()


def _match_collection_ids_by_tokens(item: dict, collections: list[dict], limit: int) -> list[dict]:
    """Cheap fallback: custom collections whose title shares meaningful words with
    the item. Only works when item and store speak the same language, which is
    exactly why the LLM matcher below exists — but it costs nothing and keeps
    assignment working when the API key is missing or Anthropic is down."""
    tokens: set[str] = set()
    for field in (item.get("category"), item.get("title"), item.get("brand")):
        if field:
            tokens.update(
                w for w in re.findall(r"[a-zA-Z]+", str(field).lower())
                if w not in _STOPWORDS and len(w) > 2
            )
    if not tokens:
        return []
    scored = []
    for c in collections:
        title_tokens = {
            w for w in re.findall(r"[a-zA-Z]+", (c.get("title") or "").lower())
            if w not in _STOPWORDS
        }
        score = len(tokens & title_tokens)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda s: -s[0])
    return [c for _, c in scored[:limit]]


async def _match_collection_ids_with_claude(item: dict, collections: list[dict], limit: int) -> list[dict]:
    """Semantic match: ask Haiku which of the store's own collection titles this
    item belongs in. Token overlap structurally can't do this — our category is
    Dutch ("heren truien") while a store's collections are in whatever language
    and wording the merchant chose ("SWEATERS", "KNITWEAR", "MENSWEAR") — and it
    can't map a synonym like "Turtleneck" onto "Sweaters" either.

    Returns [] on any failure (including no API key) so the caller falls back.
    Never invents a collection: only titles returned that EXACTLY match a fetched
    collection title (case-insensitively) are used.
    """
    try:
        import anthropic as _anthropic
        from backend.config import settings as _settings
        if not _settings.anthropic_api_key:
            return []
        titles = [str(c.get("title") or "").strip() for c in collections if c.get("title")]
        if not titles:
            return []

        facts = {
            "title": item.get("title"),
            "brand": item.get("brand"),
            "product_type": _product_type_from_item(item),
            "category": item.get("category"),
            "material": item.get("material"),
        }
        described = "\n".join(f"{k}: {v}" for k, v in facts.items() if v)
        listed = "\n".join(titles)
        prompt = (
            "You assign a second-hand fashion product to the collections of a Shopify store.\n\n"
            f"Product:\n{described}\n\n"
            f"The store's collections (exact titles):\n{listed}\n\n"
            "Return the collection titles this product genuinely belongs in, at most "
            f"{limit}, one per line, copied EXACTLY as written above (same spelling and casing). "
            "The product and the collections may be in different languages — match on meaning, "
            "not on words. Only include a collection if the product really fits it; a generic "
            "catch-all collection is not a fit. If none fit, return exactly NONE. "
            "Return only the titles or NONE, no commentary."
        )
        import asyncio
        client = _anthropic.Anthropic(api_key=_settings.anthropic_api_key)
        response = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        raw = response.content[0].text.strip()
        logger.info("Shopify: collection matcher (Claude) returned: %r", raw[:300])
        if not raw or raw.strip().upper().startswith("NONE"):
            return []
        by_title = {str(c.get("title") or "").strip().lower(): c for c in collections}
        chosen: list[dict] = []
        for line in raw.splitlines():
            c = by_title.get(line.strip().strip("-•* ").lower())
            if c is not None and c not in chosen:
                chosen.append(c)
        return chosen[:limit]
    except Exception as e:
        logger.warning(f"Shopify: Claude collection matching failed: {e}")
        return []


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


async def _assign_to_collection(base_url: str, headers: dict, product_id: str, collection_id) -> bool:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/collects.json",
                json={"collect": {"product_id": int(product_id), "collection_id": collection_id}},
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.warning(f"Shopify: collect assignment failed ({resp.status_code}): {resp.text}")
                return False
            return True
    except Exception as e:
        logger.warning(f"Shopify: collect assignment error: {e}")
        return False


# A product can genuinely belong in several collections ("SWEATERS" and
# "MENSWEAR"), but spraying it across everything is worse than picking nothing.
MAX_COLLECTIONS_PER_PRODUCT = 3


async def assign_best_collection(base_url: str, headers: dict, item: dict, product_id: str) -> None:
    """Auto-detect & assign the matching custom collections for a newly created
    product. Smart collections auto-populate from their own rules and can't be
    assigned to via collects.json, so only custom/manual collections are targeted
    here (a store's "ALL VINTAGE"-style collections filling themselves is Shopify
    doing that, not us). Best-effort — never raises, so a matching failure can
    never abort the product create."""
    collections = await _get_custom_collections(base_url, headers)
    logger.info(
        "Shopify: fetched %d custom collection(s) for product %s: %s",
        len(collections), product_id,
        [c.get("title") for c in collections][:20],
    )
    if not collections:
        logger.info(
            f"Shopify: store has 0 CUSTOM collections (smart collections can't be assigned to) — "
            f"skipping collection assignment for product {product_id}"
        )
        return

    chosen = await _match_collection_ids_with_claude(item, collections, MAX_COLLECTIONS_PER_PRODUCT)
    how = "claude"
    if not chosen:
        chosen = _match_collection_ids_by_tokens(item, collections, MAX_COLLECTIONS_PER_PRODUCT)
        how = "token-fallback"
    if not chosen:
        logger.info(
            f"Shopify: no collection matched among {len(collections)} custom collection(s) "
            f"for product {product_id} (claude found none and no keyword overlap) — skipping assignment"
        )
        return

    for c in chosen:
        ok = await _assign_to_collection(base_url, headers, product_id, c.get("id"))
        logger.info(
            "Shopify: assign product %s → collection %r (%s) via %s: %s",
            product_id, c.get("title"), c.get("id"), how, "OK" if ok else "FAILED",
        )


def _public_photo_urls(item: dict) -> list[str]:
    """Only http(s) URLs are usable — Shopify fetches every image server-side, so a
    blob:/data:/local path (e.g. a photo the frontend hasn't finished uploading yet)
    would silently fail to attach. Shopify's own product image limit is 250, far
    above what any listing here has, so nothing is truncated below that."""
    urls = item.get("photo_urls") or []
    return [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))][:250]


async def _ensure_stock_of_one(base_url: str, headers: dict, product: dict) -> None:
    """Shopify has been phasing out setting `inventory_quantity` straight from the
    product-create payload. When it's ignored the variant lands on 0, which shows the
    item as SOLD OUT the moment it goes live — worse than not tracking at all. Read
    back what actually stuck and correct it via the inventory-levels API.
    Best-effort: logs and returns, never raises."""
    variant = (product.get("variants") or [{}])[0]
    try:
        if int(variant.get("inventory_quantity") or 0) == 1:
            return
    except (TypeError, ValueError):
        pass
    inventory_item_id = variant.get("inventory_item_id")
    if not inventory_item_id:
        logger.warning("Shopify: variant has no inventory_item_id — cannot set stock to 1")
        return
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            loc = await client.get(f"{base_url}/locations.json", headers=headers)
            loc.raise_for_status()
            locations = loc.json().get("locations") or []
            if not locations:
                logger.warning("Shopify: no locations returned — cannot set stock to 1")
                return
            resp = await client.post(
                f"{base_url}/inventory_levels/set.json",
                json={"location_id": locations[0]["id"],
                      "inventory_item_id": inventory_item_id,
                      "available": 1},
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Shopify: could not set stock to 1 (%s): %s — the product may show as sold out. "
                    "Usually means the token lacks write_inventory/read_locations.",
                    resp.status_code, resp.text[:200])
            else:
                logger.info("Shopify: stock set to 1 for inventory item %s", inventory_item_id)
    except Exception as e:
        logger.warning(f"Shopify: stock correction failed: {e}")


async def _attach_missing_images(base_url: str, headers: dict, product_id: str, urls: list[str], product: dict) -> None:
    """Robust image attachment fallback (ISSUE 3).

    Shopify normally fetches each `images[].src` URL server-side while creating the
    product. If its servers can't reach our Supabase public URL (bucket not public,
    egress blocked, ...) those images silently never attach — the product is created
    fine (price/collections work) but has zero photos. Here, for any photo Shopify
    didn't attach via `src`, we fetch the bytes OURSELVES (the backend CAN reach
    Supabase) and POST them as a base64 `attachment`, which can't silently fail the
    way a remote `src` fetch can.

    Best-effort: never raises, so a photo failure can never abort the product create.
    """
    if not urls:
        return
    attached = len(product.get("images") or [])
    if attached >= len(urls):
        return  # Shopify already fetched every image via src — nothing to do
    # src attaches in the order sent, so the tail is what failed to fetch.
    missing = urls[attached:]
    import base64
    for url in missing:
        try:
            # Reuse the same generous timeout as the create call — Supabase image
            # fetches plus the Shopify upload can take a while for several photos.
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                img = await client.get(url)
                if img.status_code != 200 or not img.content:
                    logger.warning(f"Shopify: base64 fallback couldn't fetch {url} (HTTP {img.status_code})")
                    continue
                b64 = base64.b64encode(img.content).decode()
                resp = await client.post(
                    f"{base_url}/products/{product_id}/images.json",
                    json={"image": {"attachment": b64}},
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.warning(f"Shopify: base64 image attach failed ({resp.status_code}): {resp.text[:200]}")
                else:
                    logger.info(f"Shopify: attached image via base64 fallback for product {product_id} ({url})")
        except Exception as e:
            logger.warning(f"Shopify: base64 image fallback errored for {url}: {e}")


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

    photo_urls = _public_photo_urls(item)
    # Diagnostic (ISSUE 3): make the true cause of "no photos" visible on the next
    # publish — how many usable public URLs we send vs how many raw photo_urls the
    # item carried (a big gap means they were blob:/local and got filtered out).
    logger.info(
        "Shopify create_product: sending %d public image URL(s) of %d raw photo_urls; first=%s",
        len(photo_urls), len(item.get("photo_urls") or []), photo_urls[:2],
    )

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
                # Track stock with a quantity of exactly 1: every item here is a
                # single second-hand piece, so Shopify marks it sold out by itself
                # once it sells instead of letting a second buyer order it.
                "inventory_management": "shopify",
                "inventory_policy": "deny",
                "inventory_quantity": 1,
            }],
            "images": [{"src": url} for url in photo_urls],
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

    _returned = len(product.get("images") or [])
    logger.info(
        "Shopify create_product: product %s created with %d/%d image(s) attached via src",
        product_id, _returned, len(photo_urls),
    )

    base_url = f"https://{settings.shopify_store}/admin/api/2024-10"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    # If Shopify couldn't fetch some/all of our src URLs, attach the bytes directly.
    await _attach_missing_images(base_url, headers, product_id, photo_urls, product)

    await _ensure_stock_of_one(base_url, headers, product)

    await assign_best_collection(base_url, headers, item, product_id)

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
