"""
Webhook handlers for platforms that support push notifications.
Shopify: orders/paid → auto-delist everywhere.
eBay: item sold notification.
"""
from fastapi import APIRouter, Request, HTTPException
from backend.services.crosslist import handle_item_sold
from backend.database import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/ebay")
async def ebay_webhook(request: Request):
    """
    eBay Marketplace Account Deletion / Item Sold notification.
    Configure in eBay developer portal under Application Settings > Notifications.
    """
    payload = await request.json()

    # eBay sends a challenge token for endpoint verification
    if "challenge" in payload:
        return {"challengeResponse": payload["challenge"]}

    notification_type = payload.get("metadata", {}).get("topic", "")

    if notification_type == "MARKETPLACE_ACCOUNT_DELETION":
        # Handle account deletion (GDPR requirement)
        return {"status": "acknowledged"}

    # Item sold notification
    item_data = payload.get("data", {})
    listing_id = item_data.get("listingId") or item_data.get("itemId")

    if listing_id:
        db = get_db()
        listing = db.table("listings").select("item_id").eq("platform_listing_id", str(listing_id)).eq("platform", "ebay").execute()
        if listing.data:
            await handle_item_sold(listing.data[0]["item_id"], "ebay")

    return {"status": "ok"}


@router.post("/shopify/orders-paid")
async def shopify_order_paid(request: Request):
    """
    Shopify sends this when an order is paid.
    We find the item by SKU and delist from all other platforms.
    Register in Shopify Partner Dashboard > Webhooks > orders/paid.
    """
    from backend.platforms.shopify import verify_webhook, extract_skus_from_order
    raw = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not verify_webhook(raw, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    order = json.loads(raw)
    skus = extract_skus_from_order(order)
    if not skus:
        return {"status": "no_skus"}

    db = get_db()
    for sku in skus:
        item = db.table("items").select("id").eq("sku", sku).execute()
        if item.data:
            await handle_item_sold(item.data[0]["id"], "shopify")

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
