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

DEMO_EMAIL = "danieldekoning66+demo@gmail.com"
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
    # Uitgebreid zodat de dashboard-screenshots in blogs een vólle, geloofwaardige
    # voorraad tonen i.p.v. een half-lege demo. Bewust breed over categorieën:
    # kleding, schoenen, elektronica, boeken, meubels, verzamelobjecten — dat zijn
    # exact de niches waar de Pillar B-artikelen over gaan, dus de screenshots
    # sluiten aan bij de tekst eromheen.
    dict(title="Arc'teryx Beta LT Jacket", brand="Arc'teryx", size="M", category="Jassen", color="Zwart",
         condition="good", price=185, purchase_price=80, photo="arcteryx-beta"),
    dict(title="Nike Dunk Low Panda", brand="Nike", size="44", category="Schoenen", color="Wit/Zwart",
         condition="good", price=95, purchase_price=48, photo="dunk-low"),
    dict(title="New Balance 550 White Green", brand="New Balance", size="41", category="Schoenen", color="Wit/Groen",
         condition="new", price=88, purchase_price=42, photo="nb-550"),
    dict(title="Vintage Burberry Trench Coat", brand="Burberry", size="L", category="Jassen", color="Beige",
         condition="fair", price=240, purchase_price=95, photo="burberry-trench"),
    dict(title="Sony WH-1000XM4 Koptelefoon", brand="Sony", size="One size", category="Elektronica", color="Zwart",
         condition="good", price=145, purchase_price=70, photo="sony-xm4"),
    dict(title="Apple iPhone 12 64GB", brand="Apple", size="One size", category="Elektronica", color="Blauw",
         condition="good", price=210, purchase_price=140, photo="iphone-12"),
    dict(title="Nintendo Switch OLED", brand="Nintendo", size="One size", category="Elektronica", color="Wit",
         condition="good", price=225, purchase_price=155, photo="switch-oled"),
    dict(title="Lego Star Wars Millennium Falcon", brand="Lego", size="One size", category="Verzamelobjecten", color="Grijs",
         condition="new", price=135, purchase_price=75, photo="lego-falcon"),
    dict(title="Vintage Omega Seamaster Band", brand="Omega", size="One size", category="Accessoires", color="Zilver",
         condition="good", price=165, purchase_price=60, photo="omega-band"),
    dict(title="Eames Style Eetkamerstoel", brand="Vitra", size="One size", category="Meubels", color="Wit",
         condition="good", price=95, purchase_price=35, photo="eames-chair"),
    dict(title="Teakhouten Vintage Dressoir", brand="Onbekend", size="One size", category="Meubels", color="Bruin",
         condition="fair", price=320, purchase_price=120, photo="teak-dressoir"),
    dict(title="Louis Vuitton Neverfull MM", brand="Louis Vuitton", size="One size", category="Tassen", color="Bruin",
         condition="good", price=780, purchase_price=420, photo="lv-neverfull"),
    dict(title="Michael Kors Schoudertas", brand="Michael Kors", size="One size", category="Tassen", color="Zwart",
         condition="good", price=72, purchase_price=28, photo="mk-tas"),
    dict(title="Harry Potter Boxset Hardcover", brand="Bloomsbury", size="One size", category="Boeken", color="Divers",
         condition="good", price=68, purchase_price=22, photo="hp-boxset"),
    dict(title="Dune - Frank Herbert Eerste Druk", brand="Onbekend", size="One size", category="Boeken", color="Divers",
         condition="fair", price=115, purchase_price=30, photo="dune-boek"),
    dict(title="Stussy Basic Logo Tee", brand="Stussy", size="L", category="T-shirts", color="Zwart",
         condition="good", price=34, purchase_price=12, photo="stussy-tee"),
    dict(title="Moncler Bodywarmer", brand="Moncler", size="M", category="Vesten", color="Navy",
         condition="good", price=295, purchase_price=140, photo="moncler-vest"),
    dict(title="Vintage Adidas Trainingsjack", brand="Adidas", size="L", category="Jassen", color="Rood",
         condition="fair", price=42, purchase_price=11, photo="adidas-track"),
    dict(title="Casio G-Shock DW-5600", brand="Casio", size="One size", category="Accessoires", color="Zwart",
         condition="good", price=78, purchase_price=38, photo="gshock"),
    dict(title="Uniqlo Down Jacket", brand="Uniqlo", size="S", category="Jassen", color="Zwart",
         condition="new", price=45, purchase_price=15, photo="uniqlo-down"),
    dict(title="Vintage Persian Loper Kleed", brand="Onbekend", size="One size", category="Meubels", color="Rood",
         condition="good", price=180, purchase_price=65, photo="perzisch-kleed"),
    dict(title="Pokémon Charizard Holo Kaart", brand="Pokémon", size="One size", category="Verzamelobjecten", color="Divers",
         condition="good", price=420, purchase_price=180, photo="charizard"),
    dict(title="Jordan 1 Mid Chicago", brand="Nike", size="42", category="Schoenen", color="Rood/Wit",
         condition="good", price=125, purchase_price=65, photo="jordan-1"),
    dict(title="Acne Studios Sjaal", brand="Acne Studios", size="One size", category="Accessoires", color="Grijs",
         condition="new", price=110, purchase_price=45, photo="acne-sjaal"),
    dict(title="COS Wollen Winterjas", brand="COS", size="M", category="Jassen", color="Camel",
         condition="good", price=98, purchase_price=32, photo="cos-jas"),
]


def photo_url(seed: str, n: int) -> str:
    return f"https://picsum.photos/seed/crosslisteu-{seed}-{n}/600/600"


# SUPABASE_KEY here is the anon key, not service_role, so auth.admin.* (list/create
# with email_confirm) isn't reachable — 403s. The account was created once via a
# plain sign_up (needs the usual email-confirmation click) and its id is fixed here
# so re-seeds don't need admin access at all.
DEMO_USER_ID = "ce6efe8f-a845-46ed-a363-93ec8cc05297"


def get_or_create_demo_user(db):
    return DEMO_USER_ID


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

    # Subscriptions RLS requires a real authenticated (per-user) session, which this
    # script doesn't have — the backend's own /api/billing/status endpoint lazily
    # creates a 7-day "trialing" subscription the first time the demo account logs
    # in and hits it, which is enough to unlock the dashboard for a demo/recording.

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
    print(f"  URL:      https://omnivaleur.com/login.html")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
