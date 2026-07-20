"""
Webhook handlers for platforms that support push notifications.
Shopify: orders/paid → auto-delist everywhere.
eBay: item sold notification.
"""
import hashlib
from fastapi import APIRouter, Request, HTTPException
from backend.services.crosslist import handle_item_sold
from backend.database import get_db
from backend.config import settings

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

    if listing_id:
        db = get_db()
        listing = db.table("listings").select("item_id").eq("platform_listing_id", str(listing_id)).eq("platform", "ebay").execute()
        if listing.data:
            await handle_item_sold(listing.data[0]["item_id"], "ebay", sold_price=_ebay_sale_price(item_data))

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

    db = get_db()
    for sku in skus:
        item = db.table("items").select("id").eq("sku", sku).execute()
        if item.data:
            await handle_item_sold(item.data[0]["id"], "shopify", sold_price=sku_prices.get(sku))

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
        listing = db.table("listings").select("item_id,platform").eq("platform_listing_id", ad_id).in_("platform", ["marktplaats", "2dehands"]).execute()
        if listing.data:
            await handle_item_sold(listing.data[0]["item_id"], listing.data[0]["platform"])

    return {"status": "ok"}
