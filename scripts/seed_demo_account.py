#!/usr/bin/env python3
"""
One-off: create a demo account with realistic items/listings/sales history for
recording social media / marketing videos. Safe to re-run — it looks up the
account by email first and reuses it instead of creating duplicates.

Usage: python3 scripts/seed_demo_account.py
"""
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db

DEMO_EMAIL = "demo@crosslisteu.com"
DEMO_PASSWORD = "CrossListDemo2026!"

PLATFORMS = ["marktplaats", "2dehands", "vinted", "ebay", "shopify"]

ITEMS = [
    dict(title="Nike Tech Fleece Jacket", brand="Nike", size="M", category="Jassen", color="Zwart",
         condition="good", price=68, purchase_price=22, photo="tech-fleece-jacket"),
    dict(title="Adidas Samba OG Sneakers", brand="Adidas", size="42", category="Schoenen", color="Wit/Zwart",
         condition="good", price=75, purchase_price=35, photo="samba-og"),
    dict(title="Levi's 501 Vintage Jeans", brand="Levi's", size="32/32", category="Spijkerbroeken", color="Blauw",
         condition="fair", price=45, purchase_price=12, photo="levis-501"),
    dict(title="The North Face Fleece Vest", brand="The North Face", size="L", category="Vesten", color="Groen",
         condition="new", price=52, purchase_price=18, photo="north-face-vest"),
    dict(title="Ralph Lauren Polo Shirt", brand="Ralph Lauren", size="M", category="Polo's", color="Navy",
         condition="good", price=32, purchase_price=8, photo="ralph-lauren-polo"),
    dict(title="New Era 9FIFTY Cap NY Yankees", brand="New Era", size="One size", category="Accessoires", color="Zwart",
         condition="new", price=24, purchase_price=9, photo="new-era-cap"),
    dict(title="Carhartt WIP Chore Jacket", brand="Carhartt", size="L", category="Jassen", color="Bruin",
         condition="good", price=89, purchase_price=30, photo="carhartt-jacket"),
    dict(title="Vintage Champion Hoodie", brand="Champion", size="M", category="Truien", color="Grijs",
         condition="fair", price=38, purchase_price=10, photo="champion-hoodie"),
    dict(title="Nike Air Force 1 '07", brand="Nike", size="43", category="Schoenen", color="Wit",
         condition="good", price=65, purchase_price=25, photo="air-force-1"),
    dict(title="Zara Satin Midi Dress", brand="Zara", size="S", category="Jurken", color="Bordeaux",
         condition="new", price=28, purchase_price=6, photo="zara-dress"),
    dict(title="Patagonia Better Sweater", brand="Patagonia", size="M", category="Truien", color="Navy",
         condition="good", price=58, purchase_price=20, photo="patagonia-sweater"),
    dict(title="Vintage Levi's Denim Jacket", brand="Levi's", size="L", category="Jassen", color="Lichtblauw",
         condition="fair", price=55, purchase_price=15, photo="denim-jacket"),
    dict(title="Stone Island Sweatshirt", brand="Stone Island", size="M", category="Truien", color="Beige",
         condition="good", price=110, purchase_price=45, photo="stone-island"),
    dict(title="Dr. Martens 1460 Boots", brand="Dr. Martens", size="40", category="Schoenen", color="Zwart",
         condition="good", price=72, purchase_price=28, photo="dr-martens"),
    dict(title="Tommy Hilfiger Button-Up Shirt", brand="Tommy Hilfiger", size="M", category="Overhemden", color="Wit/Blauw",
         condition="new", price=26, purchase_price=7, photo="tommy-shirt"),
]


def photo_url(seed: str, n: int) -> str:
    return f"https://picsum.photos/seed/crosslisteu-{seed}-{n}/600/600"


def get_or_create_demo_user(db):
    existing = db.auth.admin.list_users()
    for u in existing:
        if u.email == DEMO_EMAIL:
            print(f"Reusing existing demo user {u.id}")
            return u.id
    res = db.auth.admin.create_user({
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "email_confirm": True,
    })
    print(f"Created demo user {res.user.id}")
    return res.user.id


def seed(db, user_id: str):
    now = datetime.now(timezone.utc)

    # Wipe any previous demo data for a clean re-seed.
    old_items = db.table("items").select("id").eq("user_id", user_id).execute().data or []
    if old_items:
        db.table("items").delete().eq("user_id", user_id).execute()

    for idx, it in enumerate(ITEMS):
        created_at = now - timedelta(days=random.randint(5, 90))
        item_row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "sku": f"DEMO-{idx + 1:03d}",
            "title": it["title"],
            "description": (
                f"{it['title']} in {it['condition'] if it['condition'] != 'new' else 'nieuwstaat'} conditie. "
                f"Maat {it['size']}, kleur {it['color']}. Verzending binnen 1-2 werkdagen, "
                f"gecombineerde verzending mogelijk bij meerdere aankopen."
            ),
            "price": it["price"],
            "purchase_price": it["purchase_price"],
            "brand": it["brand"],
            "size": it["size"],
            "condition": it["condition"],
            "category": it["category"],
            "color": it["color"],
            "photo_urls": [photo_url(it["photo"], n) for n in range(1, random.randint(3, 5))],
            "created_at": created_at.isoformat(),
        }
        db.table("items").insert(item_row).execute()

        # Cross-list to 2-4 platforms per item.
        n_platforms = random.randint(2, 4)
        chosen = random.sample(PLATFORMS, n_platforms)
        is_sold = idx % 4 == 0  # ~25% sold, so revenue/analytics charts have data
        sold_platform = random.choice(chosen) if is_sold else None

        for platform in chosen:
            listed_at = created_at + timedelta(hours=random.randint(1, 6))
            sold = platform == sold_platform
            listing_row = {
                "id": str(uuid.uuid4()),
                "item_id": item_row["id"],
                "platform": platform,
                "platform_listing_id": f"{platform}-{uuid.uuid4().hex[:8]}",
                "platform_listing_url": _fake_listing_url(platform, it["title"]),
                "status": "sold" if sold else "active",
                "listed_at": listed_at.isoformat(),
                "sold_at": (listed_at + timedelta(days=random.randint(1, 21))).isoformat() if sold else None,
                "last_checked": now.isoformat(),
                "last_refreshed_at": (now - timedelta(days=random.randint(1, 10))).isoformat() if random.random() > 0.5 else None,
                "refresh_count": random.randint(0, 3),
            }
            db.table("listings").insert(listing_row).execute()

    # Active "pro" subscription so nothing is gated in the demo.
    db.table("subscriptions").upsert({
        "user_id": user_id,
        "status": "active",
        "plan": "pro",
        "current_period_end": (now + timedelta(days=365)).isoformat(),
    }, on_conflict="user_id").execute()

    print(f"Seeded {len(ITEMS)} items with cross-listed platform listings + sales history.")


def _fake_listing_url(platform: str, title: str) -> str:
    slug = title.lower().replace("'", "").replace(" ", "-")
    return {
        "marktplaats": f"https://www.marktplaats.nl/v/kleding/{slug}",
        "2dehands": f"https://www.2dehands.be/v/kleding/{slug}",
        "vinted": f"https://www.vinted.nl/items/{slug}",
        "ebay": f"https://www.ebay.com/itm/{slug}",
        "shopify": f"https://demo-store.myshopify.com/products/{slug}",
    }[platform]


if __name__ == "__main__":
    db = get_db()
    uid = get_or_create_demo_user(db)
    seed(db, uid)
    print()
    print("Demo account ready:")
    print(f"  URL:      https://crosslisteu.com/login.html")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
