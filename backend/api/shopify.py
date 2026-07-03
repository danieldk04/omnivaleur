from fastapi import APIRouter, HTTPException, Query
from backend.platforms.shopify_importer import list_products, get_product, create_product, delete_product

router = APIRouter(prefix="/shopify", tags=["shopify"])


@router.get("/products")
async def fetch_products(
    limit: int = Query(50, le=250),
    page_info: str | None = Query(None),
):
    try:
        return await list_products(limit=limit, page_info=page_info)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/products/{product_id}")
async def fetch_product(product_id: str):
    try:
        return await get_product(product_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/products")
async def publish_product(item: dict):
    try:
        return await create_product(item)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/products/{product_id}")
async def remove_product(product_id: str):
    try:
        ok = await delete_product(product_id)
        return {"deleted": ok}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
