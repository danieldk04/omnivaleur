"""
eBay REST API integration (Sell Inventory API).
Requires free developer account at developer.ebay.com.
Uses OAuth2 with long-lived refresh tokens (18 months).
"""
from __future__ import annotations
import base64
import logging
import re
import time
from datetime import datetime, timezone, timedelta
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
    TAXONOMY_API = "https://api.sandbox.ebay.com/commerce/taxonomy/v1"
else:
    AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    INVENTORY_API = "https://api.ebay.com/sell/inventory/v1"
    TAXONOMY_API = "https://api.ebay.com/commerce/taxonomy/v1"

SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
]


class EbayCategoryRequiredError(Exception):
    """Raised when an item has no eBay category and no default is configured."""


# Every offer must point at a merchant location so eBay can derive Item.Country.
# One stable key per account is enough; we create it lazily on first publish.
MERCHANT_LOCATION_KEY = "OMNIVALEUR_MAIN"


def _with_expiry(token_response: dict) -> dict:
    """eBay returns `expires_in` (seconds), but credentials are refreshed based on
    an absolute `token_expires_at` — compute and attach it here so callers never
    have to remember to, which previously meant tokens were reused past expiry."""
    expires_in = token_response.get("expires_in")
    if expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in) - 60)
        token_response = {**token_response, "token_expires_at": expires_at.isoformat()}
    return token_response


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
            return _with_expiry(resp.json())

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
            return {**credentials, **_with_expiry(data)}

    def _auth_headers(self, credentials: dict, *, write: bool = False) -> dict:
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }
        # Write-calls (inventory_item PUT, offer POST) eisen een Content-Language;
        # eBay weigert ze anders met "Invalid value for header Content-Language".
        if write:
            headers["Content-Language"] = _content_language()
        return headers

    async def _ensure_fresh_token(self, credentials: dict) -> dict:
        expires_at = credentials.get("token_expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                refreshed = await self.refresh_credentials(credentials)
                self._persist_refreshed(credentials, refreshed)
                return refreshed
        return credentials

    def _persist_refreshed(self, old: dict, new: dict) -> None:
        """Schrijf een ververste access-token terug naar de database, zodat niet
        elke call opnieuw hoeft te verversen. Alleen als de credentials uit een
        echte DB-rij komen (bevat user_id). Niet-blokkerend: een fout hier mag de
        plaatsing niet laten mislukken."""
        user_id = old.get("user_id")
        if not user_id:
            return
        try:
            from backend.database import get_db
            get_db().table("platform_credentials").update({
                "access_token": new.get("access_token"),
                "token_expires_at": new.get("token_expires_at"),
                # eBay geeft bij refresh geen nieuwe refresh_token terug; behoud de oude.
                "refresh_token": new.get("refresh_token") or old.get("refresh_token"),
            }).eq("user_id", user_id).eq("platform", self.platform_name).execute()
        except Exception as e:
            logger.warning(f"Kon ververste eBay-token niet opslaan (niet-blokkerend): {e}")

    async def _ensure_location(self, client: httpx.AsyncClient, credentials: dict) -> None:
        """Make sure a merchant location exists; eBay needs it to derive Item.Country
        when publishing an offer. Idempotent — a 409 (already exists) is fine."""
        get_resp = await client.get(
            f"{INVENTORY_API}/location/{MERCHANT_LOCATION_KEY}",
            headers=self._auth_headers(credentials),
        )
        if get_resp.status_code == 200:
            return
        address = {"country": settings.ebay_location_country or "NL"}
        if settings.ebay_location_postal_code:
            address["postalCode"] = settings.ebay_location_postal_code
        if settings.ebay_location_city:
            address["city"] = settings.ebay_location_city
        create_resp = await client.post(
            f"{INVENTORY_API}/location/{MERCHANT_LOCATION_KEY}",
            json={
                "location": {"address": address},
                "name": "Omnivaleur",
                "merchantLocationStatus": "ENABLED",
                "locationTypes": ["WAREHOUSE"],
            },
            headers=self._auth_headers(credentials, write=True),
        )
        # 204 = created, 409 = already existed (race). Anything else is a real error.
        if create_resp.status_code not in (200, 201, 204, 409):
            _raise_with_ebay_error(create_resp, "creating merchant location")

    async def create_listing(self, item: dict, credentials: dict) -> dict:
        if not credentials.get("access_token"):
            raise RuntimeError(
                "eBay is not connected — open Platforms and click 'Connect eBay', "
                "then complete the eBay sign-in before publishing."
            )
        credentials = await self._ensure_fresh_token(credentials)
        sku = item.get("sku") or item["id"]

        # Categorie-keten: 1) expliciet op het item, 2) auto-resolutie via de
        # Taxonomy API op basis van de titel (gegarandeerd geldige leaf), 3) het
        # geconfigureerde EBAY_DEFAULT_CATEGORY_ID als laatste backstop.
        category_id = item.get("ebay_category_id")
        if not category_id:
            try:
                category_id = await resolve_category_id(
                    item.get("title", ""), item.get("brand"),
                    item.get("category"), item.get("gender"),
                )
                if category_id:
                    logger.info(f"eBay-categorie automatisch bepaald voor '{item.get('title', sku)}': {category_id}")
            except Exception as e:
                logger.warning(f"eBay categorie-auto-resolutie mislukt (val terug op default): {e}")
        if not category_id:
            category_id = settings.ebay_default_category_id
        if not category_id:
            raise EbayCategoryRequiredError(
                f"Item '{item.get('title', sku)}' has no eBay category and auto-resolution "
                "returned nothing. Set an eBay category ID on the item (look it up at "
                "https://www.ebay.com/sch/allcategories/all-categories) or configure "
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
            await self._ensure_location(client, credentials)

            inv_resp = await client.put(
                f"{INVENTORY_API}/inventory_item/{sku}",
                json=inventory_payload,
                headers=self._auth_headers(credentials, write=True),
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
                headers=self._auth_headers(credentials, write=True),
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
            "platform_offer_id": offer_id,
        }

    async def delete_listing(self, offer_id: str, credentials: dict) -> bool:
        """Ends a live listing. `offer_id` must be the offerId from create_listing
        (stored as `platform_offer_id`), not the public listingId — eBay's Inventory
        API operates on offers, and a published offer can only be ended via /withdraw,
        not DELETE (which only works for never-published offers)."""
        credentials = await self._ensure_fresh_token(credentials)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{INVENTORY_API}/offer/{offer_id}/withdraw",
                headers=self._auth_headers(credentials),
            )
            if resp.status_code in (200, 204):
                return True
            # Fall back to DELETE in case the offer was never actually published.
            resp = await client.delete(
                f"{INVENTORY_API}/offer/{offer_id}",
                headers=self._auth_headers(credentials),
            )
            return resp.status_code in (200, 204)

    async def relist_ended(self, offer_id: str, credentials: dict) -> dict:
        """
        Republish a withdrawn/ended offer via eBay's own publish endpoint — the
        official "Sell similar / relist" mechanism. Only valid for offers that are
        NOT currently live: eBay's duplicate-listing policy prohibits having two
        active listings for the same item, so this must never be called on an
        offer that's still published (get_listing_status(...) != 'active').
        """
        credentials = await self._ensure_fresh_token(credentials)
        status = await self.get_listing_status(offer_id, credentials)
        if status == "active":
            raise RuntimeError("Offer is still live on eBay — relist only applies to ended listings")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{INVENTORY_API}/offer/{offer_id}/publish",
                headers=self._auth_headers(credentials),
            )
            _raise_with_ebay_error(resp, "relisting ended offer")
            listing_id = resp.json().get("listingId", offer_id)
        domain = _MARKETPLACE_DOMAINS.get(settings.ebay_marketplace_id, "ebay.com")
        return {
            "platform_listing_id": listing_id,
            "platform_listing_url": f"https://www.{domain}/itm/{listing_id}",
            "platform_offer_id": offer_id,
        }

    async def get_listing_status(self, offer_id: str, credentials: dict) -> str:
        credentials = await self._ensure_fresh_token(credentials)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{INVENTORY_API}/offer/{offer_id}",
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


_MARKETPLACE_DOMAINS = {
    "EBAY_NL": "ebay.nl", "EBAY_DE": "ebay.de", "EBAY_GB": "ebay.co.uk",
    "EBAY_FR": "ebay.fr", "EBAY_BE": "ebay.be", "EBAY_IT": "ebay.it",
    "EBAY_ES": "ebay.es", "EBAY_US": "ebay.com",
}

# eBay's Inventory API verplicht een Content-Language-header op de write-calls
# (create/replace inventory_item en create offer). Zonder deze header weigert eBay
# met "Invalid value for header Content-Language" — de write mislukt dan volledig.
# Moet een BCP-47 taalcode zijn die past bij de marketplace.
_MARKETPLACE_LANGUAGES = {
    "EBAY_NL": "nl-NL", "EBAY_DE": "de-DE", "EBAY_GB": "en-GB",
    "EBAY_FR": "fr-FR", "EBAY_BE": "nl-BE", "EBAY_IT": "it-IT",
    "EBAY_ES": "es-ES", "EBAY_US": "en-US",
}


def _content_language() -> str:
    return _MARKETPLACE_LANGUAGES.get(settings.ebay_marketplace_id, "en-US")


def _raise_with_ebay_error(resp: httpx.Response, action: str) -> None:
    if resp.is_success:
        return
    detail = resp.text[:500]
    try:
        errors = resp.json().get("errors", [])
        if errors:
            detail = "; ".join(e.get("message", "") for e in errors)
    except Exception:
        pass
    logger.error(f"eBay error while {action}: {resp.status_code} {detail}")
    raise RuntimeError(f"eBay error while {action}: {detail}")


_app_token_cache: dict = {"token": None, "expires_at": 0}
_category_tree_cache: dict = {"tree_id": None}


def _basic_auth_header() -> str:
    raw = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
    return base64.b64encode(raw.encode()).decode()


async def _get_app_token() -> str:
    """App-level token (client_credentials grant) for public catalog data
    like category suggestions — no connected eBay user account required."""
    now = time.time()
    if _app_token_cache["token"] and now < _app_token_cache["expires_at"] - 60:
        return _app_token_cache["token"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {_basic_auth_header()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    _app_token_cache["token"] = data["access_token"]
    _app_token_cache["expires_at"] = now + data.get("expires_in", 7200)
    return _app_token_cache["token"]


async def _get_category_tree_id() -> str:
    if _category_tree_cache["tree_id"]:
        return _category_tree_cache["tree_id"]
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TAXONOMY_API}/get_default_category_tree_id",
            params={"marketplace_id": settings.ebay_marketplace_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        tree_id = resp.json()["categoryTreeId"]
    _category_tree_cache["tree_id"] = tree_id
    return tree_id


def _clean_ebay_query(query: str) -> str:
    """
    Strip the noise that derails eBay's category matcher.

    The raw title goes to eBay's relevance engine as-is, and inventory prefixes
    plus loose numbers are actively harmful: "(1324) White Suitsupply Shoes -
    Men 43" was suggested as Toys > Miniature vehicles, because 1:24 and 1:43
    are the standard scales for model cars — eBay read the SKU and the shoe size
    as scale markers. None of these numbers say anything about what the item IS.
    """
    q = re.sub(r"^\s*[\(\[]\s*\d+\s*[\)\]]\s*", " ", query)   # leading (1324) / [1324] SKU
    q = re.sub(r"\b\d+\s*[:/]\s*\d+\b", " ", q)                # 1:24-style scale markers
    q = re.sub(r"(?<![a-z0-9])\d+(?![a-z0-9])", " ", q, flags=re.I)  # standalone numbers (sizes)
    q = re.sub(r"[-–—]+", " ", q)                              # separator dashes
    q = re.sub(r"\s+", " ", q).strip()
    return q


def _build_ebay_query(query: str, brand: str | None = None,
                      category: str | None = None, gender: str | None = None) -> str:
    """
    Build the text handed to eBay's matcher: a cleaned title plus the context the
    listing form already knows. Our own category is the single strongest signal
    about what the garment is — leaving it out meant eBay had to guess from a
    title that might be mostly SKU and size.
    """
    cleaned = _clean_ebay_query(query)
    parts = []
    if gender:
        parts.append(_EBAY_GENDER_WORDS.get(gender.lower().strip(), ""))
    if brand and brand.strip().lower() not in cleaned.lower():
        parts.append(brand.strip())
    parts.append(cleaned)
    if category:
        parts.append(_EBAY_CATEGORY_HINTS.get(category.lower().strip(), ""))
    text = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", text).strip() or query.strip()


_EBAY_GENDER_WORDS = {"heren": "mens", "dames": "womens", "kinderen": "kids", "unisex": ""}

# Our category keys -> plain English garment words eBay's matcher understands.
_EBAY_CATEGORY_HINTS = {
    "jeans": "jeans", "heren jeans": "jeans", "broeken": "trousers",
    "heren chinos": "chinos trousers", "shorts": "shorts", "heren shorts": "shorts",
    "sportbroeken": "athletic shorts", "heren sportbroeken": "athletic shorts",
    "sportleggings": "athletic leggings", "sport bh": "sports bra",
    "rokken": "skirt", "jurken casual": "dress", "jurken feest": "party dress",
    "blouses": "blouse", "tops": "top t-shirt", "heren t-shirts": "t-shirt",
    "heren polo's": "polo shirt", "heren overhemden": "shirt",
    "truien": "jumper sweater", "heren truien": "jumper sweater",
    "unisex truien": "jumper sweater", "hoodies": "hoodie", "heren hoodies": "hoodie",
    "jassen": "coat jacket", "heren jassen": "coat jacket", "unisex jassen": "coat jacket",
    "heren pakken": "suit", "zwemkleding": "swimwear", "ondergoed": "underwear",
    "sneakers dames": "sneakers shoes", "heren sneakers": "sneakers shoes",
    "unisex schoenen": "shoes", "schoenen dames": "shoes", "heren schoenen": "shoes",
    "heren formele schoenen": "formal dress shoes", "hakken": "heels",
    "laarzen dames": "boots", "heren laarzen": "boots", "sandalen": "sandals",
    "accessoires dames": "accessories", "heren accessoires": "accessories",
    "unisex accessoires": "accessories", "unisex sportkleding": "sportswear",
    "kinderen schoenen": "kids shoes", "kinderen sportkleding": "kids sportswear",
    "jongens kleding": "boys clothing", "meisjes kleding": "girls clothing",
    "babykleding": "baby clothing", "peuterkleding": "toddler clothing",
    "tieners jongens": "boys clothing", "tieners meisjes": "girls clothing",
    # ── Non-clothing: games, consoles, phones. eBay's Taxonomy API resolves
    # these well from the title alone; the hint sharpens the product type.
    "games playstation 5": "playstation 5 video game", "games playstation 4": "playstation 4 video game",
    "games playstation 3": "playstation 3 video game", "games playstation 2": "playstation 2 video game",
    "games playstation 1": "playstation 1 video game", "games psp": "psp video game",
    "games ps vita": "ps vita video game", "games nintendo switch": "nintendo switch video game",
    "games nintendo wii u": "wii u video game", "games nintendo wii": "wii video game",
    "games nintendo 3ds": "nintendo 3ds video game", "games nintendo ds": "nintendo ds video game",
    "games gamecube": "gamecube video game", "games nintendo 64": "nintendo 64 video game",
    "games snes": "super nintendo video game", "games nes": "nes video game",
    "games gameboy": "game boy video game", "games xbox series": "xbox series video game",
    "games xbox one": "xbox one video game", "games xbox 360": "xbox 360 video game",
    "games xbox original": "original xbox video game", "games pc": "pc video game",
    "games sega": "sega video game", "games atari": "atari video game", "games overige": "video game",
    "games console playstation 5": "playstation 5 console", "games console playstation 4": "playstation 4 console",
    "games console playstation 3": "playstation 3 console", "games console playstation 2": "playstation 2 console",
    "games console playstation 1": "playstation 1 console", "games console ps vita": "ps vita console",
    "games console psp": "psp console", "games console nintendo switch": "nintendo switch console",
    "games console nintendo switch lite": "nintendo switch lite console", "games console nintendo wii u": "wii u console",
    "games console nintendo wii": "wii console", "games console nintendo 3ds": "nintendo 3ds console",
    "games console nintendo ds": "nintendo ds console", "games console gamecube": "gamecube console",
    "games console nintendo 64": "nintendo 64 console", "games console snes": "super nintendo console",
    "games console nes": "nes console", "games console gameboy": "game boy console",
    "games console xbox series": "xbox series console", "games console xbox one": "xbox one console",
    "games console xbox 360": "xbox 360 console", "games console xbox original": "original xbox console",
    "games console sega": "sega console", "games console atari": "atari console", "games console overige": "game console",
    "electronics telefoon apple iphone": "apple iphone smartphone", "electronics telefoon samsung": "samsung smartphone",
    "electronics telefoon huawei": "huawei smartphone", "electronics telefoon sony": "sony smartphone",
    "electronics telefoon nokia": "nokia mobile phone", "electronics telefoon lg": "lg smartphone",
    "electronics telefoon motorola": "motorola smartphone", "electronics telefoon htc": "htc smartphone",
    "electronics telefoon blackberry": "blackberry smartphone", "electronics telefoon overige": "smartphone mobile phone",
}


async def suggest_categories(query: str, brand: str | None = None,
                             category: str | None = None,
                             gender: str | None = None) -> list[dict]:
    """Look up eBay category suggestions for free text via the Taxonomy API,
    so users don't have to hunt for category IDs manually."""
    if not settings.ebay_app_id:
        raise RuntimeError("eBay is not configured yet: set EBAY_APP_ID and EBAY_CERT_ID.")
    if not query or not query.strip():
        return []
    search_text = _build_ebay_query(query, brand, category, gender)
    logger.info(f"eBay category lookup: {query!r} -> {search_text!r}")
    results = await _raw_category_suggestions(search_text)
    return await _translate_category_names(results)


async def _raw_category_suggestions(search_text: str) -> list[dict]:
    """Ruwe Taxonomy-suggesties [{category_id, name}, ...] zonder vertaling —
    gedeeld door de UI-suggestie en de listing-tijd fallback-resolver."""
    token = await _get_app_token()
    tree_id = await _get_category_tree_id()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{TAXONOMY_API}/category_tree/{tree_id}/get_category_suggestions",
            params={"q": search_text},
            headers={"Authorization": f"Bearer {token}", "Accept-Language": "en-US"},
        )
        resp.raise_for_status()
        data = resp.json()
    results = []
    for s in data.get("categorySuggestions", [])[:10]:
        ancestors = [a["categoryName"] for a in reversed(s.get("categoryTreeNodeAncestors", []))]
        path = " > ".join(ancestors + [s["category"]["categoryName"]])
        results.append({"category_id": s["category"]["categoryId"], "name": path})
    return results


async def resolve_category_id(query: str, brand: str | None = None,
                              category: str | None = None,
                              gender: str | None = None) -> str | None:
    """Beste-gok eBay-categorie-ID voor een item op basis van de titel, gebruikt
    als fallback bij het plaatsen wanneer het item zelf geen ebay_category_id heeft.
    Geeft een gegarandeerd geldige leaf-categorie terug (of None)."""
    if not settings.ebay_app_id or not query or not query.strip():
        return None
    search_text = _build_ebay_query(query, brand, category, gender)
    results = await _raw_category_suggestions(search_text)
    return results[0]["category_id"] if results else None


async def _translate_category_names(results: list[dict]) -> list[dict]:
    """eBay's Accept-Language override isn't honoured for every marketplace's
    category tree (e.g. EBAY_NL always returns Dutch names) — translate the
    display names to English ourselves so the UI stays English-only."""
    if not results or not settings.anthropic_api_key:
        return results
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        numbered = "\n".join(f"{i}: {r['name']}" for i, r in enumerate(results))
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": (
                "Translate each eBay category breadcrumb path below to English. "
                "Keep the same numbering and the same '>' separators, translate every segment. "
                "Return only the translated lines, nothing else.\n\n" + numbered
            )}],
        )
        text = response.content[0].text.strip()
        for line in text.splitlines():
            if ":" not in line:
                continue
            idx_str, translated = line.split(":", 1)
            try:
                idx = int(idx_str.strip())
            except ValueError:
                continue
            if 0 <= idx < len(results):
                results[idx]["name"] = translated.strip()
    except Exception as e:
        logger.warning(f"eBay category name translation failed: {e}")
    return results


def _map_condition(condition: str) -> str:
    return {
        "new_with_tags": "NEW",
        "new": "NEW",
        "good": "USED_EXCELLENT",
        "fair": "USED_GOOD",
        "poor": "USED_ACCEPTABLE",
    }.get(condition, "USED_EXCELLENT")
