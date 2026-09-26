"""Zet voor zoekertjes die al op 2dehands staan een bijwerking van de verzendkosten klaar.

WAAROM (26-09-2026, Egbert Brouwer / Papa's Plectrums). Tot extensie 1.0.353
kreeg elk zoekertje op 2dehands Bpost 0-2 kg (EUR 7,10), ook als de verkoper
hetzelfde artikel op Marktplaats zelf verstuurt voor een eigen bedrag. Nieuwe
zoekertjes krijgen nu dat eigen bedrag; dit script doet het voor de bestaande.

Per zoekertje: staat het artikel op Marktplaats met "Zelf verzenden" en een
bedrag, en toont de openbare 2dehands-pagina iets anders, dan komt er een
opdracht (content_refresh met _verzending_bijwerken) in de wachtrij. De server
geeft die alleen aan extensie 1.0.354 of nieuwer, en houdt de rest vast zodra er
één mislukt (_bijwerken_2dh_staat_stil in jobs.py).

Gebruik:
  python3 scripts/verzendkosten_2dehands_bijwerken.py --user <user_id> [--titel patch] [--uitvoeren]

Zonder --uitvoeren wordt er alleen geteld. Rustig aan met Marktplaats: zestig
pagina's in vijftien seconden gaf 403 (26-09-2026).
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

TUSSENPOZE = 2.5  # seconden tussen twee zoekertjes


async def _op_2dehands(client: httpx.AsyncClient, nummer: str):
    from backend.services.mp_enrich import verzending_uit_html
    cijfers = re.sub(r"\D", "", nummer or "")
    r = await client.get(f"https://www.2dehands.be/m{cijfers}", headers={"Accept": "text/html"})
    if r.status_code in (404, 410):
        return "weg"
    if r.status_code != 200:
        return None
    return verzending_uit_html(r.text)


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--titel", default="", help="alleen titels met dit woord (hoofdletters maken niet uit)")
    p.add_argument("--uitvoeren", action="store_true")
    a = p.parse_args()
    load_dotenv()
    from backend.database import get_db, fetch_all, fetch_all_in
    from backend.services.mp_enrich import UA, verzending_van_advertentie

    db = get_db()
    items = {i["id"]: i["title"] or "" for i in fetch_all(
        lambda: db.table("items").select("id,title").eq("user_id", a.user))}
    if a.titel:
        items = {k: v for k, v in items.items() if a.titel.lower() in v.lower()}
    rijen = fetch_all_in(lambda: db.table("listings").select("item_id,platform,platform_listing_id,platform_listing_url")
                         .eq("status", "active").in_("platform", ["2dehands", "marktplaats"]),
                         "item_id", list(items))
    per_item: dict[str, dict] = collections.defaultdict(dict)
    for r in rijen:
        if r.get("platform_listing_id"):
            per_item[r["item_id"]][r["platform"]] = r
    al_bezig = {r["item_id"] for r in fetch_all(
        lambda: db.table("jobs").select("id,item_id").eq("user_id", a.user).eq("platform", "2dehands")
        .eq("action", "content_refresh").in_("status", ["pending", "claimed"]))}

    telling = collections.Counter()
    klaar = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": UA}) as client:
        for item_id, kanalen in per_item.items():
            dh, mp = kanalen.get("2dehands"), kanalen.get("marktplaats")
            if not dh:
                continue
            if not mp:
                telling["niet op Marktplaats"] += 1
                continue
            if item_id in al_bezig:
                telling["wacht al op een bijwerking"] += 1
                continue
            v = await verzending_van_advertentie(mp["platform_listing_id"], a.user)
            if v is None:
                telling["Marktplaats antwoordde niet (later opnieuw)"] += 1
                await asyncio.sleep(TUSSENPOZE * 4)
                continue
            if v.get("soort") != "zelf":
                telling[f"op Marktplaats: {v.get('soort') or 'weg'}"] += 1
                await asyncio.sleep(TUSSENPOZE)
                continue
            nu = await _op_2dehands(client, dh["platform_listing_id"])
            if nu is None:
                telling["2dehands antwoordde niet (later opnieuw)"] += 1
            elif nu == "weg":
                telling["staat niet meer op 2dehands"] += 1
            elif nu.get("soort") == "zelf" and nu.get("cents") == v["cents"]:
                telling["stond al goed"] += 1
            else:
                telling[f"bijwerken naar {v['cents'] / 100:.2f}".replace(".", ",")] += 1
                klaar.append({
                    "user_id": a.user, "item_id": item_id, "platform": "2dehands",
                    "action": "content_refresh", "status": "pending",
                    "payload": {"platform_listing_id": dh["platform_listing_id"],
                                "platform_listing_url": dh.get("platform_listing_url"),
                                "title": items.get(item_id), "_verzending_bijwerken": True,
                                "verzending": {"soort": "zelf", "cents": v["cents"]}},
                })
            await asyncio.sleep(TUSSENPOZE)

    for k, n in sorted(telling.items()):
        print(f"{n:5}  {k}")
    print(f"{len(klaar):5}  opdrachten {'klaargezet' if a.uitvoeren else 'die klaargezet zouden worden'}")
    if a.uitvoeren and klaar:
        for i in range(0, len(klaar), 50):
            db.table("jobs").insert(klaar[i:i + 50]).execute()


if __name__ == "__main__":
    asyncio.run(main())
