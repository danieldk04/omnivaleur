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


# Een sleutel die de winkelier zelf aanmaakt begint altijd met shpat_ (Admin API
# access token). shpca_/shpss_ zijn andere soorten en werken hier niet; die
# meteen weigeren scheelt de winkelier een onbegrijpelijke 401 van Shopify.
_ADMIN_TOKEN_RE = re.compile(r"^shpat_[0-9a-fA-F]{32,}$")

# Wat de app minimaal moet mogen om te kunnen werken. Precies dezelfde rechten
# als bij de knop-koppeling (settings.shopify_scopes), maar hier moeten we ze
# zelf controleren: bij een zelfgemaakte app vinkt de winkelier ze met de hand
# aan, en één vergeten vinkje levert anders pas weken later een onverklaarbare
# fout op midden in een publicatie.
VERPLICHTE_SCOPES = ("read_products", "write_products")
# Nodig voor voorraad en verkoopkanalen. Ontbreken ze, dan kan er wél
# geïmporteerd en gepubliceerd worden, maar blijft een product onzichtbaar in de
# winkel of staat de voorraad verkeerd. Dat melden we, we blokkeren het niet.
AANBEVOLEN_SCOPES = ("write_inventory", "read_locations", "read_publications",
                     "write_publications", "read_orders")


def is_valid_admin_token(token: str) -> bool:
    return bool(_ADMIN_TOKEN_RE.match((token or "").strip()))


async def controleer_app_gegevens(shop: str, client_id: str, client_secret: str) -> dict:
    """Controleer een eigen app vóór we hem opslaan, door er echt een sleutel mee
    op te halen. Alleen dán weten we zeker dat het werkt — en dat is precies wat
    hier misging toen we de winkelier stappen gaven die Shopify had geschrapt."""
    shop = (shop or "").strip().lower()
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not is_valid_shop_domain(shop):
        raise ValueError("That doesn't look like a Shopify store address. "
                         "It should end in .myshopify.com, for example my-store.myshopify.com.")
    if not client_id or not client_secret:
        raise ValueError("Fill in both the client ID and the client secret from your app's "
                         "Settings page in the Shopify Dev Dashboard.")

    vers = await vraag_token(shop, client_id, client_secret)
    toegekend = set(vers["scopes"])

    # Geeft de uitwisseling zelf geen rechten terug, vraag het dan alsnog na bij
    # de bron. Nooit oordelen op een leeg antwoord: dan zou een winkelier te
    # horen krijgen dat alles ontbreekt terwijl er niets mis is.
    if not toegekend:
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
            rs = await c.get(f"https://{shop}/admin/oauth/access_scopes.json",
                             headers={"X-Shopify-Access-Token": vers["access_token"]})
        if rs.status_code == 200:
            toegekend = {x.get("handle") for x in (rs.json().get("access_scopes") or [])}
        if not toegekend:
            raise ValueError(
                "Shopify gave us a working key but wouldn't say which permissions it has. "
                "Check that your new version is Released and shows as Active, then try again."
            )
        vers["scopes"] = sorted(toegekend)

    ontbreekt = [x for x in VERPLICHTE_SCOPES if x not in toegekend]
    if ontbreekt:
        raise ValueError(
            "This app doesn't have enough permissions yet. Missing: " + ", ".join(ontbreekt)
            + ". Open the app in the Dev Dashboard, add those scopes to its configuration, "
              "release a new version, and try again."
        )

    # De sleutel klopt; nu nog bewijzen dat de winkel echt antwoordt.
    import httpx
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
        r = await c.get(f"https://{shop}/admin/api/2024-01/shop.json?fields=name",
                        headers={"X-Shopify-Access-Token": vers["access_token"]})
    if r.status_code >= 400:
        raise ValueError("The credentials work but the store didn't answer. "
                         "Check that the app is installed on this store, then try again.")

    return {
        "shop": shop,
        "shop_name": (r.json().get("shop") or {}).get("name") or shop,
        "scopes": vers["scopes"],
        "access_token": vers["access_token"],
        "expires_at": vers["expires_at"],
        "aanbevolen_ontbreekt": [x for x in AANBEVOLEN_SCOPES if x not in toegekend],
    }


async def controleer_admin_token(shop: str, token: str) -> dict:
    """Controleer een zelfgemaakte sleutel vóór we hem opslaan.

    WAAROM DIT ER IS. Shopify accepteert sinds 28-08-2026 geen apps meer die
    koppelen met een marktplaats buiten Shopify, dus de knop-koppeling via de
    App Store is geen weg meer. Winkeliers maken nu zelf een app in hun eigen
    beheerscherm en plakken de sleutel bij ons. Dat betekent ook dat niemand
    anders meer controleert of die sleutel klopt en genoeg mag — dus doen wij
    het hier, meteen, in plaats van het te ontdekken als er een publicatie
    mislukt.

    Levert de winkelnaam, de toegekende rechten, en welke daarvan ontbreken.
    Gooit ValueError met een leesbare uitleg als de sleutel niet bruikbaar is.
    """
    import httpx

    shop = (shop or "").strip().lower()
    token = (token or "").strip()
    if not is_valid_shop_domain(shop):
        raise ValueError("That doesn't look like a Shopify store address. "
                         "It should end in .myshopify.com, for example my-store.myshopify.com.")
    if not is_valid_admin_token(token):
        raise ValueError("That doesn't look like an Admin API access token. "
                         "It starts with shpat_ and you'll find it in your Shopify admin under "
                         "the app you created, on the API credentials tab.")

    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as c:
        try:
            r = await c.get(f"https://{shop}/admin/oauth/access_scopes.json", headers=headers)
        except httpx.HTTPError as e:
            raise ValueError(f"We couldn't reach {shop}. Check the store address and try again.") from e
        if r.status_code in (401, 403):
            raise ValueError("Shopify rejected that token. Check that you copied the whole "
                             "Admin API access token, and that it belongs to this store.")
        if r.status_code == 404:
            raise ValueError(f"{shop} doesn't exist, or that token belongs to a different store.")
        if r.status_code >= 400:
            raise ValueError(f"Shopify returned an unexpected error ({r.status_code}). Please try again.")
        toegekend = {s.get("handle") for s in (r.json().get("access_scopes") or [])}

        # De rechten kloppen; nu nog bewijzen dat de winkel echt antwoordt.
        # access_scopes zegt alleen iets over de sleutel, niet over de winkel.
        rs = await c.get(f"https://{shop}/admin/api/2024-01/shop.json?fields=name,myshopify_domain",
                         headers=headers)
        if rs.status_code >= 400:
            raise ValueError("The token is valid but the store didn't answer. "
                             "Give it a minute and try again.")
        winkel = (rs.json().get("shop") or {})

    ontbreekt = [s for s in VERPLICHTE_SCOPES if s not in toegekend]
    if ontbreekt:
        raise ValueError(
            "This app doesn't have enough permissions yet. Missing: "
            + ", ".join(ontbreekt)
            + ". Open the app in your Shopify admin, tick those under Admin API access scopes, "
              "save, and copy the token again."
        )

    return {
        "shop": shop,
        "shop_name": winkel.get("name") or shop,
        "scopes": sorted(toegekend),
        "aanbevolen_ontbreekt": [s for s in AANBEVOLEN_SCOPES if s not in toegekend],
    }


def verify_webhook(raw_body: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook signature.

    Webhooks declared through the app's own version config (as ours are —
    the mandatory GDPR ones and orders/paid) are signed with the app's API
    secret, not a separate webhook secret. SHOPIFY_WEBHOOK_SECRET is only
    for a webhook subscription created by hand with its own signing key;
    fall back to the app secret since that covers every webhook we actually
    register. Silently accepting unsigned calls (returning True) would let
    anyone hit these endpoints and trigger customer-data actions.
    """
    secret = SHOPIFY_WEBHOOK_SECRET or settings.shopify_client_secret
    if not secret:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
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

    async def get_products(self, limit: int = 250, fields: str | None = None) -> list[dict]:
        """Producten ophalen. `fields` beperkt wat Shopify terugstuurt.

        Zonder tijdslimiet gold hier de standaard van vijf seconden, en een
        volledige lijst van 250 producten (met alle foto's en varianten erin)
        haalt dat niet — dan viel dit met een time-out om terwijl er niets mis
        was. Nu een ruime limiet, en de mogelijkheid om alleen te vragen wat je
        nodig hebt.
        """
        import httpx
        url = f"{self.base}/products.json?limit={limit}"
        if fields:
            url += f"&fields={fields}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as c:
            r = await c.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json().get("products", [])

    async def create_product(self, item: dict, on_created=None) -> dict:
        """`on_created` wordt aangeroepen zodra Shopify het product bevestigt.

        Waarom dat nodig is: ná het aanmaken volgen nog vijf stappen (foto's,
        voorraad, collectie, categorie, verkoopkanalen). Die kosten seconden, en
        als de gateway het verzoek in die tijd afkapt is het product wél online
        maar weet ons dashboard van niets — dan blijft het item eindeloos op
        "Publishing…" staan terwijl het op Shopify gewoon te koop staat. Precies
        dat is een keer gebeurd. Door het id meteen door te geven is dat venster
        weg: wat daarna nog misgaat, kost hooguit een foto of een collectie.
        """
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
            # Eerst vastleggen dát het bestaat, dan pas afmaken.
            if on_created:
                try:
                    await on_created(product)
                except Exception:
                    logger.exception("Shopify: vastleggen van het nieuwe product-id mislukte")
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


async def vraag_token(shop: str, client_id: str, client_secret: str) -> dict:
    """Een verse sleutel opvragen met de gegevens van de app zelf.

    Dit is Shopify's "client credentials grant". Waarom die hier nodig is: sinds
    2026 kan een winkelier in zijn winkelbeheer geen app meer aanmaken die een
    sleutel toont ("You can no longer create new admin-created custom apps").
    Hij maakt er nu een in zijn EIGEN Dev Dashboard, en daar staat geen sleutel
    maar een client-ID en een clientgeheim. Daarmee vragen we zelf een sleutel op.

    Dat mag alleen als de app en de winkel van dezelfde Shopify-organisatie zijn.
    Dat is precies het geval als de winkelier zijn eigen app voor zijn eigen
    winkel maakt — en dus werkt dit voor iedere klant, zonder dat Shopify er een
    app voor hoeft goed te keuren.

    De sleutel verloopt na 24 uur; vandaar dat we hem samen met zijn houdbaarheid
    teruggeven en de aanroeper hem opnieuw laat ophalen als hij oud is.
    """
    import httpx
    from datetime import datetime, timedelta, timezone

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as c:
        r = await c.post(
            f"https://{shop}/admin/oauth/access_token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if r.status_code in (400, 401, 403):
        raise ValueError(
            "Shopify didn't accept those app credentials. Check that the client ID and "
            "client secret belong to an app in the SAME Shopify organisation as this store, "
            "and that you installed the app on the store."
        )
    if r.status_code >= 400:
        raise ValueError(f"Shopify returned an unexpected error ({r.status_code}). Please try again.")
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise ValueError("Shopify accepted the request but returned no token. Please try again.")
    geldig_tot = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in") or 86399))
    return {
        "access_token": token,
        # De rechten kunnen met komma's ÓF met spaties gescheiden terugkomen —
        # OAuth doet het ene, deze uitwisseling soms het andere. Alleen op komma
        # splitsen leverde één lange sliert op, en dus de onterechte melding
        # "read_products ontbreekt" terwijl het recht gewoon aan stond.
        "scopes": sorted({x for x in re.split(r"[,\s]+", data.get("scope") or "") if x}),
        "expires_at": geldig_tot.isoformat(),
    }


# Hoe lang voor het verlopen we al een nieuwe sleutel halen. Een sleutel die
# midden in een publicatie verloopt kost een halve advertentie; tien minuten
# speling kost niets.
TOKEN_MARGE_MINUTEN = 10


async def _shop_creds(credentials: dict) -> tuple[Optional[str], Optional[str]]:
    """Winkeladres en een BRUIKBARE sleutel.

    Drie soorten koppeling komen hier binnen en moeten alle drie werken:
      1. de oude knop-koppeling (OAuth) — sleutel verloopt niet;
      2. een custom app van vóór 2026 — sleutel verloopt niet;
      3. een eigen app in de Dev Dashboard — client-ID en geheim, sleutel
         verloopt na 24 uur en wordt hier ververst.
    """
    from datetime import datetime, timezone

    if not credentials:
        return None, None
    extra = credentials.get("extra_data") or {}
    shop = extra.get("shop_domain")
    client_id = extra.get("client_id")
    client_secret = extra.get("client_secret")

    if not (shop and client_id and client_secret):
        return shop, credentials.get("access_token")

    # Nog geldig? Dan niet onnodig een nieuwe halen.
    bestaand = credentials.get("access_token")
    tot = extra.get("token_expires_at")
    if bestaand and tot:
        try:
            over = (datetime.fromisoformat(tot) - datetime.now(timezone.utc)).total_seconds()
            if over > TOKEN_MARGE_MINUTEN * 60:
                return shop, bestaand
        except (TypeError, ValueError):
            pass  # onleesbare datum: gewoon een nieuwe halen

    vers = await vraag_token(shop, client_id, client_secret)
    # Opslaan zodat de volgende aanroep hem niet opnieuw hoeft te halen. Lukt dat
    # niet, dan werken we gewoon door met de sleutel die we net kregen — een
    # mislukte opslag mag geen publicatie kosten.
    try:
        from backend.database import get_db, naast_de_lus
        db = get_db()
        (await naast_de_lus(lambda: db.table("platform_credentials").update({
            "access_token": vers["access_token"],
            "extra_data": {**extra, "token_expires_at": vers["expires_at"],
                           "scope": ",".join(vers["scopes"]) or extra.get("scope", "")},
        }).eq("user_id", credentials["user_id"]).eq("platform", "shopify").execute()))
    except Exception as e:  # noqa: BLE001
        logger.warning("shopify: verse sleutel niet opgeslagen: %s", e)
    return shop, vers["access_token"]


def _maak_vastleggen(shop: str, callback):
    """Verpakt de callback van de aanroeper zodat de platformlaag zelf niets van
    de database hoeft te weten — hij geeft alleen id en url door."""
    if not callback:
        return None

    async def _vastleggen(product: dict):
        pid = str(product.get("id"))
        await callback({
            "platform_listing_id": pid,
            "platform_listing_url": f"https://{shop}/products/{product.get('handle', pid)}",
        })

    return _vastleggen


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

    async def create_listing(self, item: dict, credentials: dict, on_created=None) -> dict:
        shop, token = await _shop_creds(credentials)
        if not shop or not token:
            # No per-user store connected yet — fall back to the single globally
            # configured store (existing behaviour for the account this was built for).
            return await create_product(item)
        product = await ShopifyClient(shop, token).create_product(
            item, on_created=_maak_vastleggen(shop, on_created),
        )
        product_id = str(product["id"])
        return {
            "platform_listing_id": product_id,
            "platform_listing_url": f"https://{shop}/products/{product.get('handle', product_id)}",
        }

    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        shop, token = await _shop_creds(credentials)
        if not shop or not token:
            return await delete_product(platform_listing_id)
        return await ShopifyClient(shop, token).delete_product(platform_listing_id)

    async def update_listing_price(self, platform_listing_id: str, price: float, credentials: dict) -> bool:
        shop, token = await _shop_creds(credentials)
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
