"""Revaleur-herbouw: catalogus.json maken voor de statische winkel.

Bron nu: de publieke Shopify-feed (`/products.json`, `/collections.json`, blog-atom), want die
is wat klanten vandaag zien. Elk product krijgt `item_id` uit de Omnivaleur-database (via het
Shopify-listing-id) zodat de checkout het artikel op alle kanalen kan afmelden. Na de omzetting
komt de bron volledig uit de database (zie docs/revaleur-ontwerp.md).

Gebruik: python3 scripts/revaleur_catalogus.py [uitvoermap]   (standaard revaleur-site/data)
"""
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BRON = "https://revaleur.com"
REVALEUR_USER = "3bfbed2c-e8a7-4b28-8870-f3581d48afc5"


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode()


def _pagina(pad: str, sleutel: str) -> list:
    uit, p = [], 1
    while True:
        d = json.loads(_get(f"{BRON}/{pad}?limit=250&page={p}"))[sleutel]
        if not d:
            return uit
        uit += d
        p += 1


def _item_ids() -> dict:
    """listing-id (Shopify) -> item-id. Leeg als er geen databasesleutel is."""
    url, sleutel = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and sleutel):
        return {}
    kop = {"apikey": sleutel, "Authorization": "Bearer " + sleutel}

    def alle(pad):
        uit, o = [], 0
        while True:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"{url}/rest/v1/{pad}&limit=1000&offset={o}&order=id", headers=kop), timeout=60).read())
            uit += r
            o += 1000
            if len(r) < 1000:
                return uit
    mijn = {i["id"] for i in alle(f"items?user_id=eq.{REVALEUR_USER}&select=id")}
    return {l["platform_listing_id"]: l["item_id"] for l in
            alle("listings?platform=eq.shopify&status=eq.active&select=item_id,platform_listing_id")
            if l["item_id"] in mijn}


def _tekst(h: str) -> str:
    h = re.sub(r"<br\s*/?>|</p>|</li>", "\n", h or "")
    return re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def bouw(uitvoer: Path) -> dict:
    ids = _item_ids()
    producten = []
    for p in _pagina("products.json", "products"):
        v = p["variants"][0]
        producten.append({
            "id": str(p["id"]), "item_id": ids.get(str(p["id"])), "handle": p["handle"], "titel": p["title"],
            "merk": p["vendor"], "type": p["product_type"], "sku": v["sku"],
            "prijs": float(v["price"]), "retail": float(v["compare_at_price"]) if v["compare_at_price"] else None,
            "beschikbaar": bool(v["available"]), "beschrijving": p["body_html"] or "",
            "tekst": _tekst(p["body_html"]),
            "fotos": [{"src": i["src"], "b": i.get("width"), "h": i.get("height")} for i in p["images"]],
            "gemaakt": p["created_at"], "tags": p["tags"],
        })
    collecties = [{"handle": c["handle"], "titel": c["title"], "aantal": c["products_count"],
                   "omschrijving": c.get("body_html") or ""} for c in _pagina("collections.json", "collections")]
    # welke producten in welke collectie, in de volgorde van de winkel
    for c in collecties:
        c["producten"] = [str(p["id"]) for p in _pagina(f"collections/{c['handle']}/products.json", "products")]
    artikelen = []
    atom = _get(f"{BRON}/blogs/news.atom")
    for e in re.findall(r"<entry>(.*?)</entry>", atom, re.S):
        artikelen.append({
            "handle": re.search(r'href="[^"]*/blogs/news/([^"?]+)', e).group(1),
            "titel": html.unescape(re.search(r"<title>(.*?)</title>", e, re.S).group(1)),
            "datum": re.search(r"<published>(.*?)</published>", e).group(1)[:10],
            "html": html.unescape(re.search(r"<content[^>]*>(.*?)</content>", e, re.S).group(1)),
        })
    cat = {"producten": producten, "collecties": collecties, "artikelen": artikelen}
    uitvoer.mkdir(parents=True, exist_ok=True)
    (uitvoer / "catalogus.json").write_text(json.dumps(cat, ensure_ascii=False))
    return cat


if __name__ == "__main__":
    doel = Path(sys.argv[1] if len(sys.argv) > 1 else "revaleur-site/data")
    c = bouw(doel)
    print(len(c["producten"]), "producten,", len(c["collecties"]), "collecties,", len(c["artikelen"]), "artikelen;",
          sum(1 for p in c["producten"] if p["item_id"]), "gekoppeld aan een databaseartikel")
