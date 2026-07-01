from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class ItemCreate(BaseModel):
    title: str = Field(max_length=100)
    title_en: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    description_en: Optional[str] = None
    shopify_title: Optional[str] = None
    bid_percentage: Optional[int] = None
    sku: Optional[str] = None
    price: float
    purchase_price: Optional[float] = None
    compare_at_price: Optional[float] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    condition: str = "good"  # new/good/fair/poor
    category: Optional[str] = None
    gender: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    photo_urls: list[str] = []
    price_marktplaats: Optional[float] = None
    price_2dehands: Optional[float] = None
    price_vinted: Optional[float] = None
    ebay_category_id: Optional[str] = None


class ItemOut(ItemCreate):
    id: str
    sku: Optional[str]
    created_at: datetime
    updated_at: datetime
    days_in_stock: Optional[int]


class ListingCreate(BaseModel):
    item_id: str
    platforms: list[str]  # ['vinted', 'marktplaats', 'ebay', '2dehands']


class ListingOut(BaseModel):
    id: str
    item_id: str
    platform: str
    platform_listing_id: Optional[str]
    platform_listing_url: Optional[str]
    status: str
    listed_at: Optional[datetime]
    sold_at: Optional[datetime]
    error_message: Optional[str]


class PlatformCredentialIn(BaseModel):
    platform: str
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    extra_data: Optional[dict] = None


class AIListingRequest(BaseModel):
    photo_urls: list[str]
    platforms: list[str] = ["vinted", "marktplaats", "ebay"]
