from fastapi import APIRouter, HTTPException, Depends
from backend.models import ItemCreate, ItemOut
from backend.database import get_db
from backend.api.deps import get_current_user
import logging
import uuid

logger = logging.getLogger(__name__)

_PENDING_COLUMNS = set()

router = APIRouter(prefix="/items", tags=["items"])


def _strip_missing(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in _PENDING_COLUMNS}


@router.post("/", response_model=dict)
def create_item(item: ItemCreate, user_id: str = Depends(get_current_user)):
    db = get_db()
    data = item.model_dump()
    data["id"] = str(uuid.uuid4())
    data["user_id"] = user_id
    if not data.get("sku"):
        data["sku"] = f"REV-{data['id'][:8].upper()}"
    # Geen 502 of 503 als foutcode: Cloudflare vervangt die antwoorden door zijn
    # eigen foutpagina, waardoor de echte reden de browser nooit bereikte en de
    # gebruiker "de server duurde te lang" te zien kreeg bij een fout die in
    # 0,4 seconde optrad. 500 komt wél ongewijzigd door.
    try:
        result = execute_with_retry(
            db.table("items").insert(_strip_missing(data)), dubbel_is_ok=True
        )
    except Exception as e:
        logger.exception("Item insert failed for user %s", user_id)
        record_error("items.insert", e)
        raise HTTPException(status_code=500, detail=f"Opslaan mislukt: {e}")
    # None = de rij stond er al na een herhaalde poging (zie execute_with_retry).
    if result is None:
        return {**data, "id": data["id"]}
    if not result.data:
        logger.error("Item insert returned no row for user %s", user_id)
        record_error("items.insert", RuntimeError("insert gaf geen rij terug"))
        raise HTTPException(status_code=500, detail="Het item is niet opgeslagen — probeer het nog eens.")
    return result.data[0]


@router.get("/", response_model=list)
def list_items(limit: int = 50, offset: int = 0, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = (
        db.table("items")
        .select("*")
        .eq("user_id", user_id)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return result.data


@router.get("/{item_id}")
def get_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    result = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    return result.data


@router.patch("/{item_id}")
async def update_item(item_id: str, updates: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    clean = _strip_missing(updates)

    # A price change has to reach the marketplaces, not just this row. Without
    # this the dashboard showed the new price while every channel kept selling
    # at the old one — which made the whole Stale stock "Apply" flow pointless.
    prior = None
    price_fields = {"price", "price_marktplaats", "price_2dehands",
                    "price_vinted", "price_ebay", "price_shopify"}
    if price_fields & set(clean):
        prior = db.table("items").select("*").eq("id", item_id).eq("user_id", user_id).execute().data
        prior = prior[0] if prior else None

    try:
        result = execute_with_retry(
            db.table("items")
            .update(clean)
            .eq("id", item_id)
            .eq("user_id", user_id)
        )
    except Exception as e:
        logger.exception("Item update failed for %s", item_id)
        record_error("items.update", e)
        raise HTTPException(status_code=500, detail=f"Wijziging niet opgeslagen: {e}")
    if not result.data:
        raise HTTPException(status_code=404, detail="Item not found")
    item = result.data[0]

    def _changed(field: str) -> bool:
        if field not in clean or prior is None:
            return False
        try:
            return float(prior.get(field) or 0) != float(clean.get(field) or 0)
        except (TypeError, ValueError):
            return prior.get(field) != clean.get(field)

    if prior is not None and any(_changed(f) for f in price_fields):
        from backend.services.crosslist import sync_price_to_platforms
        # Best-effort: a marketplace that refuses the new price must not fail the
        # save itself, so the outcome is reported alongside the item instead.
        try:
            item["price_sync"] = await sync_price_to_platforms(item_id, user_id)
        except Exception as e:  # noqa: BLE001 - never break the save
            logger.exception("Price sync raised for item %s", item_id)
            item["price_sync"] = [{"status": "error", "error": str(e)}]

    return item


@router.delete("/{item_id}")
def delete_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    # Verify ownership
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    listing_ids = [l["id"] for l in (db.table("listings").select("id").eq("item_id", item_id).execute().data or [])]
    for lid in listing_ids:
        db.table("sync_events").delete().eq("listing_id", lid).execute()
    db.table("listings").delete().eq("item_id", item_id).execute()
    db.table("jobs").delete().eq("item_id", item_id).execute()
    db.table("items").delete().eq("id", item_id).execute()
    return {"deleted": item_id}


@router.post("/{item_id}/delist")
async def delist_item(item_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    from backend.services.crosslist import delist_all_platforms
    results = await delist_all_platforms(item_id, user_id)
    return {"item_id": item_id, "results": results}


@router.post("/{item_id}/crosslist")
async def crosslist_item(item_id: str, body: dict, user_id: str = Depends(get_current_user)):
    db = get_db()
    item = db.table("items").select("id").eq("id", item_id).eq("user_id", user_id).execute()
    if not item.data:
        raise HTTPException(status_code=404, detail="Item not found")
    platforms = body.get("platforms", [])
    if not platforms:
        raise HTTPException(status_code=400, detail="No platforms specified")
    from backend.services.crosslist import publish_to_platforms, CrosslistValidationError
    try:
        results = await publish_to_platforms(item_id, platforms, user_id)
    except CrosslistValidationError as e:
        raise HTTPException(status_code=422, detail={"missing_fields": e.missing})
    return {"item_id": item_id, "results": results}
