"""Seed the demo account with a few realistic items (real photos) for video recording."""
import requests

BASE = "https://crosslisteu.com"
EMAIL = "dkresellacademy@gmail.com"
PASSWORD = "95rwPSLgHxncWDV"

ITEMS = [
    dict(title="Nike Tech Fleece Jacket", brand="Nike", size="M", condition="good",
         price=48.0, purchase_price=18.0, category="Jackets", color="Black",
         photo_urls=["https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&h=800&fit=crop&q=80"]),
    dict(title="Adidas Samba OG", brand="Adidas", size="42", condition="good",
         price=65.0, purchase_price=25.0, category="Sneakers", color="Red/White",
         photo_urls=["https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&h=800&fit=crop&q=80"]),
    dict(title="Vintage Leather Bag", brand="Vintage", size="One size", condition="fair",
         price=35.0, purchase_price=10.0, category="Bags", color="Black",
         photo_urls=["https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800&h=800&fit=crop&q=80"]),
    dict(title="Zara Summer Dress Floral", brand="Zara", size="S", condition="new",
         price=22.0, purchase_price=8.0, category="Dresses", color="Red",
         photo_urls=["https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800&h=800&fit=crop&q=80"]),
    dict(title="New Era Cap 9FIFTY", brand="New Era", size="One size", condition="good",
         price=18.0, purchase_price=6.0, category="Accessories", color="Navy",
         photo_urls=["https://images.unsplash.com/photo-1521369909029-2afed882baee?w=800&h=800&fit=crop&q=80"]),
]

session = requests.Session()
res = session.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
res.raise_for_status()
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

for item in ITEMS:
    r = session.post(f"{BASE}/api/items/", json=item, headers=headers)
    if r.status_code >= 300:
        print("FAILED", item["title"], r.status_code, r.text[:300])
    else:
        print("Created:", item["title"])
