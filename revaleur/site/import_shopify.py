"""Revaleur: eenmalige import uit de Shopify-winkel (en catalogus.json voor de bouw).

Leest alleen publieke Shopify-feeds, niets van Omnivaleur. De database van Revaleur (revaleur/sql/schema.sql) is na de
omzetting de bron; `catalogus_uit_db.py` bouwt dan catalogus.json daaruit.

Gebruik:
    python3 -m revaleur.site.import_shopify                 # alleen revaleur/site/data/catalogus.json
    python3 -m revaleur.site.import_shopify --naar-db       # ook laden in het Revaleur-Supabaseproject
                                                            # (REVALEUR_SUPABASE_URL en REVALEUR_SUPABASE_SERVICE_KEY)
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

BRON = "https://revaleur.com"


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


def _tekst(h: str) -> str:
    h = re.sub(r"<br\s*/?>|</p>|</li>", "\n", h or "")
    return re.sub(r"\n\s*\n+", "\n", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


def bouw(uitvoer: Path) -> dict:
    producten = []
    for p in _pagina("products.json", "products"):
        v = p["variants"][0]
        producten.append({
            "id": str(p["id"]), "handle": p["handle"], "titel": p["title"],
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


def naar_db(cat: dict) -> None:
    """Laadt de catalogus in het Revaleur-project (upsert, veilig om opnieuw te draaien)."""
    from revaleur.shop_api.db import get_db
    db = get_db()
    rijen = [{"id": p["id"], "handle": p["handle"], "sku": p["sku"], "titel": p["titel"], "merk": p["merk"], "type": p["type"],
              "prijs": p["prijs"], "retail": p["retail"], "beschrijving_html": p["beschrijving"], "fotos": p["fotos"],
              "tags": p["tags"], "status": "beschikbaar" if p["beschikbaar"] else "verkocht", "gemaakt_op": p["gemaakt"]}
             for p in cat["producten"]]
    for i in range(0, len(rijen), 100):
        db.table("producten").upsert(rijen[i:i + 100]).execute()
    db.table("collecties").upsert([{"handle": c["handle"], "titel": c["titel"], "omschrijving": c["omschrijving"],
                                    "producten": c["producten"]} for c in cat["collecties"]]).execute()
    db.table("artikelen").upsert([{"handle": a["handle"], "titel": a["titel"], "datum": a["datum"], "html": a["html"]}
                                  for a in cat["artikelen"]]).execute()


if __name__ == "__main__":
    doel = Path(__file__).parent / "data"
    c = bouw(doel)
    print(len(c["producten"]), "producten,", len(c["collecties"]), "collecties,", len(c["artikelen"]), "artikelen")
    if "--naar-db" in sys.argv:
        naar_db(c)
        print("geladen in het Revaleur-project")
