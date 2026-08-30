"""
Webhook handlers for platforms that support push notifications.
Shopify: orders/paid → auto-delist everywhere.
eBay: item sold notification.
"""
import hashlib
from fastapi import APIRouter, Request, HTTPException
from backend.services.crosslist import handle_item_sold
from backend.database import get_db, naast_de_lus
from backend.config import settings
from backend.platforms.shopify import verify_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/ebay")
async def ebay_webhook_verify(challenge_code: str):
    """
    eBay's endpoint-verification handshake (run once when you register the
    notification URL in the developer portal). eBay sends a GET with
    ?challenge_code=... and expects back the SHA-256 hash of
    challengeCode + verificationToken + endpointURL, hex-encoded.
    Requires EBAY_VERIFICATION_TOKEN to be set to the same value configured
    in the developer portal (32-80 chars).
    """
    if not settings.ebay_verification_token:
        raise HTTPException(status_code=500, detail="EBAY_VERIFICATION_TOKEN not configured")
    m = hashlib.sha256()
    m.update(challenge_code.encode("utf-8"))
    m.update(settings.ebay_verification_token.encode("utf-8"))
    m.update(settings.ebay_webhook_url.encode("utf-8"))
    return {"challengeResponse": m.hexdigest()}


@router.post("/ebay")
async def ebay_webhook(request: Request):
    """
    eBay Marketplace Account Deletion / Item Sold notification.
    Configure in eBay developer portal under Application Settings > Notifications,
    using EBAY_WEBHOOK_URL as the endpoint and EBAY_VERIFICATION_TOKEN as the token.
    """
    payload = await request.json()
    notification_type = payload.get("metadata", {}).get("topic", "")

    if notification_type == "MARKETPLACE_ACCOUNT_DELETION":
        # Handle account deletion (GDPR requirement)
        return {"status": "acknowledged"}

    # Item sold notification
    item_data = payload.get("data", {})
    listing_id = item_data.get("listingId") or item_data.get("itemId")

    # Best-effort: eBay sale notifications may carry the actual sale amount under a
    # few different shapes. Record it when present so revenue reflects reality.
    def _ebay_sale_price(d):
        for key in ("salePrice", "totalPrice", "price", "amount"):
            v = d.get(key)
            if isinstance(v, dict):
                v = v.get("value") or v.get("amount")
            if v is not None:
                try:
                    return round(float(v), 2)
                except (ValueError, TypeError):
                    pass
        return None

    # Net als de prijs: eBay hangt het moment van de verkoop onder wisselende
    # namen in de melding. De ECHTE datum is belangrijk, want zonder krijgt de
    # verkoop de klok van het moment van verwerken — en bij een herhaalde of
    # vertraagde melding staat de omzet dan op de verkeerde dag.
    def _ebay_sale_time(payload_, d):
        for bron in (d, payload_.get("metadata") or {}, payload_):
            for key in ("saleDate", "soldDate", "creationDate", "eventDate", "emitTime", "publishDate"):
                v = bron.get(key)
                if isinstance(v, dict):
                    v = v.get("value")
                if v:
                    return v
        return None

    if listing_id:
        db = get_db()
        listing = (await naast_de_lus(lambda: db.table("listings").select("item_id").eq("platform_listing_id", str(listing_id)).eq("platform", "ebay").execute()))
        if listing.data:
            await handle_item_sold(listing.data[0]["item_id"], "ebay",
                                   sold_price=_ebay_sale_price(item_data),
                                   sold_at=_ebay_sale_time(payload, item_data))

    return {"status": "ok"}


@router.post("/shopify/orders-paid")
async def shopify_order_paid(request: Request):
    """
    Shopify sends this when an order is paid.
    We find the item by SKU and delist from all other platforms.
    Register in Shopify Partner Dashboard > Webhooks > orders/paid.
    """
    from backend.platforms.shopify import verify_webhook, extract_skus_from_order, extract_sku_prices_from_order
    raw = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not verify_webhook(raw, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    order = json.loads(raw)
    skus = extract_skus_from_order(order)
    if not skus:
        return {"status": "no_skus"}
    # Shopify tells us the real amount paid per line item — record it as the sold price.
    sku_prices = extract_sku_prices_from_order(order)

    # Shopify weet precies wanneer de bestelling betaald is. Die datum meegeven,
    # anders krijgt een bestelling die wij later verwerken de dag van vandaag.
    besteld_op = order.get("processed_at") or order.get("created_at")

    db = get_db()
    for sku in skus:
        item = (await naast_de_lus(lambda: db.table("items").select("id").eq("sku", sku).execute()))
        if item.data:
            await handle_item_sold(item.data[0]["id"], "shopify",
                                   sold_price=sku_prices.get(sku), sold_at=besteld_op)

    return {"status": "ok", "skus_processed": skus}


@router.post("/marktplaats")
async def marktplaats_webhook(request: Request):
    """
    Marktplaats advertisement status webhook.
    Configure webhook URL in Marktplaats partner portal.
    """
    payload = await request.json()
    event = payload.get("event")
    ad_id = str(payload.get("advertisementId", ""))

    if event in ("sold", "closed") and ad_id:
        db = get_db()
        listing = (await naast_de_lus(lambda: db.table("listings").select("item_id,platform").eq("platform_listing_id", ad_id).in_("platform", ["marktplaats", "2dehands"]).execute()))
        if listing.data:
            await handle_item_sold(listing.data[0]["item_id"], listing.data[0]["platform"])

    return {"status": "ok"}


@router.post("/shopify/customers/data_request")
async def shopify_customers_data_request(request: Request):
    """
    Mandatory GDPR webhook: a shop owner's customer asked what data the app
    holds on them. We never receive or store Shopify customer data — only
    the shop's own products/inventory — so there is nothing to return.
    """
    raw = await request.body()
    if not verify_webhook(raw, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return {"status": "ok"}


@router.post("/shopify/customers/redact")
async def shopify_customers_redact(request: Request):
    """
    Mandatory GDPR webhook: erase a specific customer's data. Same as
    data_request — this app never stores Shopify customer data, so there
    is nothing to erase.
    """
    raw = await request.body()
    if not verify_webhook(raw, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return {"status": "ok"}


@router.post("/shopify/shop/redact")
async def shopify_shop_redact(request: Request):
    """
    Mandatory GDPR webhook, sent 48h after a shop uninstalls the app: erase
    everything tied to that shop. We drop the stored access token so it can
    no longer be used, matching what Shopify expects on redaction.
    """
    raw = await request.body()
    if not verify_webhook(raw, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    payload = json.loads(raw)
    shop_domain = payload.get("shop_domain")
    if shop_domain:
        db = get_db()
        rows = (await naast_de_lus(
            lambda: db.table("platform_credentials").select("id,extra_data")
            .eq("platform", "shopify").execute()
        )).data or []
        for row in rows:
            if (row.get("extra_data") or {}).get("shop_domain") == shop_domain:
                await naast_de_lus(
                    lambda: db.table("platform_credentials").delete().eq("id", row["id"]).execute()
                )

    return {"status": "ok"}
