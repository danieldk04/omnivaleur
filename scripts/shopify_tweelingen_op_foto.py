"""Hetzelfde stuk twee keer bij ons: één keer uit Shopify, één keer uit Marktplaats/Vinted.

WAAROM (19-11-2026, Esther, hetisvintastisch, 3eeceb51)
Esther verkocht in haar webshop, en die avond zette onze nachtelijke herplaatsing
precies die artikelen opnieuw op Marktplaats. Oorzaak: bij het importeren van haar
Shopify-winkel (17-11, 538 producten) herkende de tweelingzoeker haar Marktplaats-
advertenties niet als hetzelfde stuk. Het taalmodel koppelde willekeurig en de
controle daarna keurde de echte paren af op kleine verschillen ("lichtgrijs" tegen
"grijs", een andere prijs in de webshop). Elk product werd dus een TWEEDE artikel.
Een verkoop in Shopify boekte de Shopify-kopie als verkocht; de Marktplaats-kopie
wist van niets en bleef online, en werd zelfs herplaatst.

Titels liegen hier, foto's niet: een verkoper gebruikt in zijn webshop en op
Marktplaats dezelfde foto's. Dit script vergelijkt per artikel dat op een kanaal
staat (zonder Shopify-rij) de eerste foto's met de Shopify-producten die qua titel
het meest lijken (perceptuele hash). Alleen een vrijwel identieke foto (afstand
<= MAX_AFSTAND) die bovendien één-op-één is, telt als hetzelfde stuk.

Wat het met --schrijf doet, per bewezen paar:
  - Shopify-product nog niet bij ons (kandidaat 'pending'): koppelen aan het
    bestaande artikel (zelfde pad als de knop Link in het importscherm).
  - Shopify-product is een tweede artikel: de Shopify-advertentierij en de
    opdrachten verhuizen naar het kanaal-artikel, de lege kopie verdwijnt
    (zoals merge_items). Eerst gaat alles wat verdwijnt naar een logboek in
    ~/.omnivaleur/herstel/, zodat het terug te zetten is.
Overgeslagen: een paar waarvan één kant verkocht is, een Shopify-product dat bij
twee artikelen past, en een kopie die zelf nog op een ander kanaal staat.

    python3 scripts/shopify_tweelingen_op_foto.py --user-id <uuid>            # droog
    python3 scripts/shopify_tweelingen_op_foto.py --user-id <uuid> --schrijf
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import concurrent.futures as cf
import io
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

MAX_AFSTAND = 2          # phash-afstand; 0 en 2 zijn dezelfde foto, opnieuw gecomprimeerd
TOP_TITELS = 10          # zoveel Shopify-producten per artikel naast elkaar leggen
LEVEND = {"active", "relisting", "pending", "hidden"}
_STOP = set("vintage retro de het een en met van in jaren voor set x cm the and of".split())


def _woorden(t: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if w not in _STOP and len(w) > 1}


def _hash(url: str, klein: bool = False):
    from PIL import Image
    import imagehash
    try:
        u = url + ("&" if "?" in url else "?") + "width=256" if klein else url
        r = requests.get(u, timeout=20)
        r.raise_for_status()
        return imagehash.phash(Image.open(io.BytesIO(r.content)).convert("RGB"))
    except Exception:  # noqa: BLE001 — een foto die niet laadt bewijst niets
        return None


def shopify_producten(shop: str, token: str) -> list[dict]:
    uit = []
    for status in ("active", "draft", "archived"):
        url = f"https://{shop}/admin/api/2024-01/products.json?limit=250&status={status}"
        while url:
            r = requests.get(url, headers={"X-Shopify-Access-Token": token}, timeout=60)
            r.raise_for_status()
            for p in r.json()["products"]:
                uit.append({"id": str(p["id"]), "title": p["title"],
                            "qty": sum((v.get("inventory_quantity") or 0) for v in p["variants"]),
                            "img": [i["src"] for i in p.get("images", [])][:3]})
            m = re.search(r'<([^>]+)>; rel="next"', r.headers.get("Link", ""))
            url = m.group(1) if m else None
    return uit


def zoek_paren(items: dict, per_item: dict, producten: list[dict]) -> list[dict]:
    """Bewezen paren (artikel op een kanaal, Shopify-product) op foto."""
    doel = [iid for iid, ls in per_item.items()
            if "shopify" not in ls and any(ls[p]["status"] in LEVEND for p in ls)]
    pw = [(p, _woorden(p["title"])) for p in producten]

    def een(iid):
        w = _woorden(items[iid]["title"])
        kand = sorted(pw, key=lambda x: -len(w & x[1]) / max(1, len(w | x[1])))[:TOP_TITELS]
        eigen = [h for h in (_hash(f) for f in (items[iid].get("photo_urls") or [])[:2]) if h is not None]
        if not eigen:
            return iid, []
        treffers = []
        for p, _ in kand:
            afst = min((h - e for h in (_hash(u, True) for u in p["img"]) if h is not None
                        for e in eigen), default=99)
            if afst <= MAX_AFSTAND:
                treffers.append((int(afst), p))
        return iid, treffers

    with cf.ThreadPoolExecutor(12) as ex:
        res = list(ex.map(een, doel))
    per_product = collections.Counter(p["id"] for _, t in res for _, p in t)
    paren = []
    for iid, t in res:
        if len(t) != 1:
            continue                       # geen of meer dan één product: niet raden
        afst, p = t[0]
        if per_product[p["id"]] != 1:
            continue                       # twee artikelen claimen dit product
        paren.append({"item": iid, "product": p, "afstand": afst})
    return paren


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--schrijf", action="store_true")
    a = ap.parse_args()
    from backend.database import fetch_all, fetch_all_in, get_db
    from backend.platforms.shopify import _shop_creds
    db, uid = get_db(), a.user_id
    cred = (db.table("platform_credentials").select("*").eq("user_id", uid)
            .eq("platform", "shopify").limit(1).execute().data or [None])[0]
    if not cred:
        print("Geen Shopify-koppeling.")
        return 0
    shop, token = await _shop_creds(cred)
    items = {i["id"]: i for i in fetch_all(lambda: db.table("items")
             .select("id,title,photo_urls").eq("user_id", uid))}
    rijen = fetch_all_in(lambda: db.table("listings").select(
        "id,item_id,platform,platform_listing_id,status"), "item_id", list(items))
    per_item: dict = collections.defaultdict(dict)
    for r in rijen:
        per_item[r["item_id"]][r["platform"]] = r
    for iid in items:
        per_item.setdefault(iid, {})
    item_van_product = {r["platform_listing_id"]: r["item_id"] for r in rijen
                        if r["platform"] == "shopify" and r.get("platform_listing_id")}
    kandidaat = {c["platform_listing_id"]: c for c in fetch_all(lambda: db.table(
        "import_candidates").select("id,platform_listing_id,status").eq("user_id", uid)
        .eq("platform", "shopify"))}
    producten = shopify_producten(shop, token)
    paren = zoek_paren(items, per_item, producten)

    plan = collections.Counter()
    acties = []
    for p in paren:
        iid, pid = p["item"], p["product"]["id"]
        kopie = item_van_product.get(pid)
        kanalen = per_item[iid]
        if any(r["status"] == "sold" for r in kanalen.values()):
            plan["overgeslagen: kanaal-artikel al verkocht"] += 1
            continue
        if kopie and kopie != iid:
            kl = per_item[kopie]
            if set(kl) - {"shopify"}:
                plan["overgeslagen: kopie staat ook op een ander kanaal"] += 1
                continue
            if any(r["status"] == "sold" for r in kl.values()):
                plan["overgeslagen: Shopify-kopie al verkocht (los afhandelen)"] += 1
                continue
            acties.append(("samenvoegen", iid, kopie, p))
            plan["samenvoegen"] += 1
        elif (kandidaat.get(pid) or {}).get("status") == "pending":
            acties.append(("koppelen", iid, kandidaat[pid]["id"], p))
            plan["koppelen"] += 1
        else:
            plan[f"overgeslagen: kandidaat {(kandidaat.get(pid) or {}).get('status')}"] += 1
    print(f"{len(paren)} bewezen paren op foto: {dict(plan)}")
    if not a.schrijf:
        for soort, iid, ander, p in acties[:400]:
            print(f"  {soort}: {items[iid]['title'][:50]} == {p['product']['title'][:50]} "
                  f"(afstand {p['afstand']})")
        return 0

    from backend.api.imports import link_candidate
    logpad = os.path.expanduser(f"~/.omnivaleur/herstel/shopify_tweelingen_{uid[:8]}_"
                                f"{datetime.now():%Y%m%d_%H%M}.jsonl")
    os.makedirs(os.path.dirname(logpad), exist_ok=True)
    gedaan = collections.Counter()
    with open(logpad, "a", encoding="utf-8") as log:
        for soort, iid, ander, p in acties:
            if soort == "koppelen":
                log.write(json.dumps({"soort": soort, "item": iid, "kandidaat": ander,
                                      "product": p["product"]["id"]}) + "\n")
                await link_candidate(ander, {"item_id": iid}, user_id=uid)
                gedaan[soort] += 1
                continue
            kopie_rij = db.table("items").select("*").eq("id", ander).execute().data
            kopie_listings = db.table("listings").select("*").eq("item_id", ander).execute().data
            kopie_jobs = db.table("jobs").select("id").eq("item_id", ander).execute().data
            log.write(json.dumps({"soort": soort, "houd": iid, "kopie": kopie_rij,
                                  "listings": kopie_listings,
                                  "jobs": [j["id"] for j in kopie_jobs]}, default=str) + "\n")
            log.flush()
            db.table("listings").update({"item_id": iid}).eq("item_id", ander).execute()
            db.table("jobs").update({"item_id": iid}).eq("item_id", ander).execute()
            db.table("import_candidates").update({"suggested_item_id": iid}) \
                .eq("suggested_item_id", ander).execute()
            db.table("items").delete().eq("id", ander).eq("user_id", uid).execute()
            gedaan[soort] += 1
    print(f"Gedaan: {dict(gedaan)}. Terugzetten kan uit {logpad}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
