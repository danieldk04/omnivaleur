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

    @staticmethod
    def _ship_from_address(credentials: dict) -> dict:
        """Ship-from address for this user's eBay location. Prefers the per-user
        value saved when they connected eBay (extra_data.ship_from); falls back to
        the global env default so single-tenant setups keep working."""
        sf = (credentials.get("extra_data") or {}).get("ship_from") or {}
        address = {"country": sf.get("country") or settings.ebay_location_country or "NL"}
        postal = sf.get("postal_code") or settings.ebay_location_postal_code
        city = sf.get("city") or settings.ebay_location_city
        if postal:
            address["postalCode"] = postal
        if city:
            address["city"] = city
        return address

    async def _ensure_location(self, client: httpx.AsyncClient, credentials: dict) -> None:
        """Make sure a merchant location exists; eBay needs it to derive Item.Country
        when publishing an offer. Idempotent — a 409 (already exists) is fine."""
        get_resp = await client.get(
            f"{INVENTORY_API}/location/{MERCHANT_LOCATION_KEY}",
            headers=self._auth_headers(credentials),
        )
        if get_resp.status_code == 200:
            return
        address = self._ship_from_address(credentials)
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

    async def upsert_location(self, credentials: dict) -> None:
        """Create the merchant location, or update its address if it already exists.
        Called when a user saves/changes their ship-from address so eBay reflects it
        immediately (not only on the next publish)."""
        if not credentials.get("access_token"):
            raise RuntimeError("eBay is not connected.")
        credentials = await self._ensure_fresh_token(credentials)
        async with httpx.AsyncClient() as client:
            get_resp = await client.get(
                f"{INVENTORY_API}/location/{MERCHANT_LOCATION_KEY}",
                headers=self._auth_headers(credentials),
            )
            if get_resp.status_code != 200:
                await self._ensure_location(client, credentials)
                return
            resp = await client.post(
                f"{INVENTORY_API}/location/{MERCHANT_LOCATION_KEY}/update_location_details",
                json={"location": {"address": self._ship_from_address(credentials)}},
                headers=self._auth_headers(credentials, write=True),
            )
            if resp.status_code not in (200, 204):
                _raise_with_ebay_error(resp, "updating merchant location")

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

        # eBay clothing categories require category-specific item specifics (Style,
        # Type, Department, …) that vary per category. Fetch the required aspects
        # for this category and auto-fill any we're still missing, so publishing
        # never fails on a "specification X is missing" error. Best-effort.
        try:
            required = await _get_required_aspects(category_id)
            _fill_required_aspects(aspects, item, required)
        except Exception as e:
            logger.warning(f"eBay required-aspect enrichment mislukt (niet-blokkerend): {e}")

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
                "merchantLocationKey": MERCHANT_LOCATION_KEY,
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

    async def update_listing_price(self, offer_id: str, price: float, credentials: dict,
                                   sku: str = "") -> bool:
        """Reprice a LIVE offer. bulkUpdatePriceQuantity is the only Inventory-API
        call that changes the price of a published offer without republishing it:
        a plain PUT /offer/{id} demands the complete offer payload and would wipe
        anything not resent. eBay keys the request on SKU with the offers nested
        under it, so both ids are needed."""
        if not offer_id:
            raise RuntimeError("No eBay offer id on this listing")
        credentials = await self._ensure_fresh_token(credentials)
        payload = {"requests": [{
            "sku": sku,
            "offers": [{
                "offerId": offer_id,
                "price": {"value": f"{float(price):.2f}", "currency": "EUR"},
            }],
        }]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{INVENTORY_API}/bulk_update_price_quantity",
                json=payload,
                headers=self._auth_headers(credentials, write=True),
            )
        _raise_with_ebay_error(resp, "updating price")
        # A 200 can still carry per-offer failures in the response body — eBay
        # reports those instead of a non-2xx status, so treating HTTP 200 as
        # success would silently leave the old price live.
        for res in (resp.json().get("responses") or []):
            if int(res.get("statusCode") or 200) >= 400:
                errors = "; ".join(e.get("message", "") for e in (res.get("errors") or []))
                raise RuntimeError(f"eBay rejected the price update: {errors or res}")
        return True

    async def resolve_offer_by_sku(self, sku: str, credentials: dict) -> dict | None:
        """
        Best-effort lookup of an existing offer by its SKU, for delisting a listing
        whose offerId/listingId we never stored. eBay's Inventory API keys offers on
        SKU: getOffers — GET /sell/inventory/v1/offer?sku={sku} — returns every offer
        for that SKU. Returns {"platform_offer_id", "platform_listing_id"} on success,
        or None when it can't resolve (unknown sku, no offers, API error). Never raises.
        """
        if not sku:
            return None
        try:
            credentials = await self._ensure_fresh_token(credentials)
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{INVENTORY_API}/offer",
                    params={"sku": sku},
                    headers=self._auth_headers(credentials),
                )
            if not resp.is_success:
                logger.warning(f"eBay getOffers by SKU {sku} failed: {resp.status_code} {resp.text[:200]}")
                return None
            offers = resp.json().get("offers", []) or []
            if not offers:
                return None
            # Prefer a PUBLISHED offer (the live listing we want to withdraw).
            offer = next(
                (o for o in offers if str(o.get("status", "")).upper() == "PUBLISHED"),
                offers[0],
            )
            offer_id = offer.get("offerId")
            if not offer_id:
                return None
            listing_id = (offer.get("listing") or {}).get("listingId")
            return {"platform_offer_id": str(offer_id),
                    "platform_listing_id": str(listing_id) if listing_id else None}
        except Exception as e:
            logger.warning(f"eBay resolve_offer_by_sku({sku}) error: {e}")
            return None

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


_required_aspects_cache: dict = {}


async def _get_required_aspects(category_id: str) -> list[dict]:
    """Required item specifics for a category, via the Taxonomy API. Each entry is
    {name, values}: `values` is the closed list of allowed values (empty = free
    text). Cached per category — the taxonomy rarely changes. Never raises."""
    if category_id in _required_aspects_cache:
        return _required_aspects_cache[category_id]
    try:
        token = await _get_app_token()
        tree_id = await _get_category_tree_id()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TAXONOMY_API}/category_tree/{tree_id}/get_item_aspects_for_category",
                params={"category_id": category_id},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Kon eBay item-aspecten niet ophalen voor categorie {category_id}: {e}")
        return []
    out = []
    for a in data.get("aspects", []):
        if not a.get("aspectConstraint", {}).get("aspectRequired"):
            continue
        values = [v.get("localizedValue") for v in a.get("aspectValues", []) if v.get("localizedValue")]
        out.append({"name": a.get("localizedAspectName"), "values": values})
    _required_aspects_cache[category_id] = out
    return out


# eBay's Taxonomy API returns required-aspect names in the marketplace's own
# locale (e.g. ebay.nl → "Merk", "Kleur", "Maat", "Afdeling"). Without this map,
# _fill_required_aspects didn't recognize those as the same concept it already
# has real data for (brand/color/size/…) and fell back to the closed list's
# first value — producing a wrong, duplicated aspect (e.g. "Merkloos" next to
# the correct "Brand: Suitsupply"). Extend with more locales as needed.
_CONCEPT_ASPECT_SYNONYMS: dict[str, set[str]] = {
    "brand": {"brand", "merk", "marke", "marca", "marque"},
    "colour": {"colour", "color", "kleur", "farbe", "couleur", "colore"},
    "size": {"size", "maat", "größe", "taille", "talla"},
    "material": {"material", "materiaal", "matériau", "materiale"},
    "department": {"department", "afdeling", "abteilung", "département", "reparto", "gender"},
    "type": {"type", "stijl", "style", "typ", "tipo"},
}


def _canonical_concept(aspect_name_lower: str) -> str | None:
    for concept, synonyms in _CONCEPT_ASPECT_SYNONYMS.items():
        if aspect_name_lower in synonyms:
            return concept
    return None


def _concept_value(concept: str, item: dict) -> str | None:
    """Resolve the real item value for a canonical aspect concept, independent
    of which language/spelling eBay asked for it under."""
    if concept == "brand":
        return item.get("brand") or None
    if concept == "colour":
        return item.get("color") or None
    if concept == "size":
        return item.get("size") or None
    if concept == "material":
        return item.get("material") or None
    if concept == "type":
        # item["category"] is a coarse crosslist routing bucket (e.g.
        # "heren truien", labelled "Jumpers / Cardigans" — it deliberately
        # covers several garment types and is NOT itself a specific type/style
        # string). Handing that slug straight to eBay's Type/Style aspect would
        # never match the closed allowed-values list and would write the raw
        # Dutch slug as the aspect value, which is worse than no data at all.
        # There is no dedicated free-text garment-type field on the item, so
        # this concept is resolved separately in _fill_required_aspects by
        # matching the title against the aspect's own allowed values.
        return None
    if concept == "department":
        gender = (item.get("gender") or "").strip().lower()
        if "wom" in gender or "vrouw" in gender or "dames" in gender:
            return "Women"
        if "men" in gender or "man" in gender or "heren" in gender:
            return "Men"
        return None
    return None


# Department/gender allowed-value keywords per canonical side. eBay's closed
# list for this aspect is itself locale-specific ("Heren"/"Dames" on ebay.nl,
# "Men's"/"Women's" on ebay.com), so a plain substring match against "Men"/
# "Women" (see _concept_value) would miss "Heren"/"Dames" entirely.
_DEPARTMENT_KEYWORDS = {
    "men": {"men", "man", "mens", "heren", "herren", "homme", "uomo", "hombre"},
    "women": {"women", "woman", "womens", "dames", "damen", "femme", "donna", "mujer"},
}


def _best_allowed_match(value: str, allowed: list[str], *, concept: str | None = None) -> str:
    """Match a real item value against eBay's closed allowed-values list for an
    aspect (case-insensitive exact, then substring, then locale-keyword for
    department), so e.g. item color "Grey" lines up with an allowed "Grijs"/
    "Grey" entry with correct casing, and canonical "Men"/"Women" lines up with
    a localized "Heren"/"Dames" entry. Falls back to the raw value (still real
    data, just unnormalized) rather than an arbitrary default when nothing
    matches."""
    if not allowed:
        return value
    low = value.strip().lower()
    for a in allowed:
        if a.lower() == low:
            return a
    for a in allowed:
        if low in a.lower() or a.lower() in low:
            return a
    if concept == "department":
        side = "men" if low in _DEPARTMENT_KEYWORDS["men"] else (
            "women" if low in _DEPARTMENT_KEYWORDS["women"] else None
        )
        if side:
            keywords = _DEPARTMENT_KEYWORDS[side]
            for a in allowed:
                a_low = a.lower()
                if any(kw in a_low for kw in keywords):
                    return a
    return value


def _fill_required_aspects(aspects: dict, item: dict, required: list[dict]) -> None:
    """Fill any required aspect we don't already have. A required aspect name
    that's a translated synonym of a concept we have real item data for
    (brand/colour/size/material/department/type) is filled from that real
    data — under its own localized key, since eBay's aspects dict keys must
    match `localizedAspectName` exactly for the category — so no duplicate
    aspect pair ever disagrees (both hold the same correct value). Only when
    there's truly no real data for a required aspect do we fall back to the
    first allowed value so eBay accepts the listing (the seller can refine
    later)."""
    existing = {k.lower() for k in aspects}
    for req in required:
        name = req.get("name")
        if not name:
            continue
        low = name.lower()
        allowed = req.get("values") or []

        concept = _canonical_concept(low)
        val = _concept_value(concept, item) if concept else None
        if val:
            aspects[name] = [_best_allowed_match(val, allowed, concept=concept)]
            continue

        if concept == "type" and allowed:
            # No structured type/style data exists on the item (see
            # _concept_value) — fall back to scanning the title for one of the
            # aspect's own allowed values (titles typically contain the actual
            # garment word, e.g. "... Cardigan ...").
            title_low = (item.get("title") or "").lower()
            title_match = next((a for a in allowed if a.lower() in title_low), None)
            if title_match:
                aspects[name] = [title_match]
                continue

        if low in existing:
            continue

        # Legacy fallbacks for aspect names outside the synonym map, or where
        # we genuinely have no real item data for the concept.
        fallback = None
        if low == "size type":
            fallback = "Regular"
        if fallback is None and allowed:
            fallback = allowed[0]
        if fallback is None:
            continue  # free-text required aspect we can't infer — let eBay report it
        if allowed and fallback not in allowed:
            fallback = allowed[0]
        aspects[name] = [fallback]


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
    # ── Jewellery, watches and bags. These used to be forced into an
    # "accessoires" clothing key, whose hint was the useless word "accessories".
    "sieraden horloges dames": "womens wristwatch watch",
    "sieraden horloges heren": "mens wristwatch watch",
    "sieraden horloges kinderen": "kids wristwatch watch",
    "sieraden horloges antiek": "antique vintage wristwatch",
    "sieraden smartwatch": "smartwatch", "sieraden sporthorloge": "sports watch",
    "sieraden activity tracker": "fitness activity tracker",
    "sieraden kettingen": "necklace", "sieraden kettinghangers": "pendant necklace",
    "sieraden armbanden": "bracelet", "sieraden ringen": "ring",
    "sieraden oorbellen": "earrings", "sieraden bedels": "charm",
    "sieraden broches": "brooch", "sieraden enkelbandjes": "anklet",
    "sieraden kindersieraden": "kids jewellery", "sieraden antiek": "antique vintage jewellery",
    "sieraden damestassen": "womens handbag", "sieraden schoudertassen": "shoulder bag",
    "sieraden rugtassen": "backpack rucksack", "sieraden reistassen": "travel holdall bag",
    "sieraden sporttassen": "sports gym bag", "sieraden koffers": "suitcase luggage",
    "sieraden portemonnees": "wallet purse",
    "sieraden zonnebril dames": "womens sunglasses", "sieraden zonnebril heren": "mens sunglasses",
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


# eBay NL taxonomy segments → English. eBay ignores Accept-Language for the
# EBAY_NL category tree and always returns Dutch, so we translate the breadcrumb
# segments ourselves. This static map covers the clothing/accessories tree the
# dashboard actually uses; it is deterministic, instant and works even when no
# LLM key is configured (the previous LLM-only path silently left names Dutch
# whenever the key was missing or the call failed). Keys are lowercased.
_EBAY_SEGMENT_NL_EN = {
    "kleding en accessoires": "Clothing & Accessories",
    "heren: kleding, accessoires": "Men: clothing, accessories",
    "dames: kleding, accessoires": "Women: clothing, accessories",
    "kinderen: kleding, accessoires": "Kids: clothing, accessories",
    "heren: kleding": "Men: clothing",
    "dames: kleding": "Women: clothing",
    "kinderen: kleding": "Kids: clothing",
    "truien en vesten": "Jumpers & cardigans",
    "mantels, jassen en vesten": "Coats, jackets & waistcoats",
    "jassen en jacks": "Coats & jackets",
    "broeken": "Trousers",
    "spijkerbroeken, jeans": "Jeans",
    "jeans": "Jeans",
    "overhemden": "Shirts",
    "t-shirts": "T-shirts",
    "shirts": "Shirts",
    "shirts, tops": "Shirts & tops",
    "polo's": "Polo shirts",
    "truien": "Jumpers",
    "vesten": "Cardigans",
    "sokken": "Socks",
    "ondergoed": "Underwear",
    "schoenen": "Shoes",
    "accessoires": "Accessories",
    "tassen": "Bags",
    "tassen en portemonnees": "Bags & purses",
    "sjaals, dassen": "Scarves & ties",
    "riemen": "Belts",
    "petten en hoeden": "Caps & hats",
    "jurken": "Dresses",
    "rokken": "Skirts",
    "shorts": "Shorts",
    "sportkleding": "Sportswear",
    "trainingspakken": "Tracksuits",
    "hemden": "Shirts",
    "kostuumhemden": "Dress shirts",
    "casual overhemden, tops": "Casual shirts & tops",
    "tops en blouses": "Tops & blouses",
    "blouses": "Blouses",
    "truien, vesten": "Jumpers & cardigans",
    "jassen, mantels": "Coats & jackets",
    "pakken": "Suits",
    "pakken en colberts": "Suits & blazers",
    "kostuums": "Suits",
    "colberts": "Blazers",
    "stropdassen": "Ties",
    "sjaals": "Scarves",
    "handschoenen": "Gloves",
    "zwemkleding": "Swimwear",
    "badmode": "Swimwear",
    "nachtkleding": "Nightwear",
    "sport en vrije tijd": "Sport & leisure",
    "voetbal": "Football",
    "truitjes en shirts": "Jerseys & shirts",
    "buitenlandse clubs": "Foreign clubs",
    "spaanse clubs": "Spanish clubs",
    "franse clubs": "French clubs",
    "engelse clubs": "English clubs",
    "duitse clubs": "German clubs",
    "italiaanse clubs": "Italian clubs",
    "nederlandse clubs": "Dutch clubs",
    "sportverzamelobjecten": "Sports memorabilia",
    "muziek, cd's en platen": "Music, CDs & records",
    "cd's": "CDs",
    "lp's": "Vinyl records",
    "verzamelingen": "Collectables",
    "overig": "Other",
    "overige": "Other",
    "boeken, strips, tijdschriften": "Books, comics & magazines",
    "boeken": "Books",
    "speelgoed en spellen": "Toys & games",
    "elektronica": "Electronics",
    "computers, tablets en netwerken": "Computers, tablets & networking",
    "telefoons en accessoires": "Phones & accessories",
    "horloges": "Watches",
    "sieraden": "Jewellery",
    "sieraden en horloges": "Jewellery & watches",
    "zonnebrillen": "Sunglasses",
    "kleding": "Clothing",
    "jongens": "Boys",
    "meisjes": "Girls",
    "baby": "Baby",
    "unisex": "Unisex",
    "miniatuurvoertuigen": "Miniature vehicles",
    "auto's en vrachtwagens": "Cars & trucks",
    "fictie": "Fiction",
    "non-fictie": "Non-fiction",
    "tijdschriften": "Magazines",
    "strips": "Comics",
}

# Segments the LLM translated earlier in this process, so the same breadcrumb
# never costs a second call and never comes back worded differently.
_ebay_segment_learned: dict[str, str] = {}


def _lookup_segment(segment: str) -> str | None:
    """English name for one breadcrumb segment, or None if we don't know it yet."""
    key = segment.strip().lower()
    return _EBAY_SEGMENT_NL_EN.get(key) or _ebay_segment_learned.get(key)


def _split_path(name: str) -> list[str]:
    return [p.strip() for p in str(name or "").split(">")]


def _translate_segments_static(name: str) -> str:
    """Translate a ' > '-joined breadcrumb with what we already know. Unknown
    segments are left as-is; _unknown_segments() picks them up for the LLM."""
    return " > ".join(_lookup_segment(p) or p for p in _split_path(name))


def _unknown_segments(results: list[dict]) -> list[str]:
    """Segments we have no English name for. The old code instead guessed with a
    hardcoded list of Dutch words, which silently let anything outside that list
    through untranslated ("Hemden > Kostuumhemden", "Voetbal", "Verzamelingen").
    Not knowing a segment is the only reliable signal, so that is what we use."""
    unknown: list[str] = []
    for r in results:
        for p in _split_path(r["name"]):
            if p and _lookup_segment(p) is None and p not in unknown:
                unknown.append(p)
    return unknown


async def _translate_category_names(results: list[dict]) -> list[dict]:
    """eBay's Accept-Language override isn't honoured for every marketplace's
    category tree (e.g. EBAY_NL always returns Dutch names) — translate the
    display names to English ourselves so the UI stays English-only. Static map
    first (deterministic, offline), LLM only for segments it didn't cover."""
    if not results:
        return results
    unknown = _unknown_segments(results)
    if unknown and settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            numbered = "\n".join(f"{i}: {s}" for i, s in enumerate(unknown))
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": (
                    "These are single segments of Dutch eBay category names. "
                    "Give the English name for each one. Keep the same numbering, "
                    "one line per segment, format 'number: English name'. "
                    "If a segment is already English or is a brand name, repeat it unchanged. "
                    "Return only those lines, nothing else.\n\n" + numbered
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
                translated = translated.strip()
                if 0 <= idx < len(unknown) and translated:
                    _ebay_segment_learned[unknown[idx].lower()] = translated
        except Exception as e:
            logger.warning(f"eBay category name translation failed: {e}")
    for r in results:
        r["name"] = _translate_segments_static(r["name"])
    return results


def _map_condition(condition: str) -> str:
    return {
        "new_with_tags": "NEW",
        "new": "NEW",
        "good": "USED_EXCELLENT",
        "fair": "USED_GOOD",
        "poor": "USED_ACCEPTABLE",
    }.get(condition, "USED_EXCELLENT")
