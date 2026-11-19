"""Nacontrole: klopt wat er LIVE op Marktplaats of 2dehands staat met wat de klant opgaf?

WAAROM DIT ER IS (19-11-2026, Esther, hetisvintastisch, 3eeceb51)
De klantfoutenronde keek alleen naar opdrachten met status 'error'. Esther mailde
die avond dat er "vaak dingen niet goed ingevuld" zijn, terwijl de ronde van die
ochtend "rustig, geen fouten" meldde. Alles stond op 'done', dus de ronde zag
niets. Een gelukte plaatsing met de verkeerde rubriek, prijs of titel is voor de
klant net zo erg als een mislukte, en hij ziet het pas als hij zelf gaat kijken.

Dit script legt per klant elke advertentie die wij 'active' noemen naast de
openbare advertentie (zoek-API van het kanaal, geen login nodig) en meldt:
  - weg          : wij noemen hem live, hij staat niet op de openbare lijst
  - rubriek      : de rubriek op het kanaal is niet de rubriek die bij het artikel hoort
  - prijs        : de prijs op het kanaal wijkt af van de prijs voor dat kanaal
  - titel        : de titel op het kanaal is niet (het begin van) onze titel
  - omschrijving : de omschrijving op het kanaal begint niet met onze omschrijving
  - fotos        : minder foto's op het kanaal dan in het artikel (max 24 op MP)
  - verkocht_elders : het artikel is op een ander kanaal als verkocht geboekt
                   maar staat hier nog live

DIT SCRIPT SCHRIJFT NIETS. Het meldt alleen.

Gebruik:
    python3 scripts/nacontrole_advertenties.py --user-id <uuid>
    python3 scripts/nacontrole_advertenties.py --uren 24      # alle klanten met een
                                                              # plaatsing in 24 uur
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_FOTOS = {"marktplaats": 24, "2dehands": 24}


def rubriek_nummers() -> dict[str, set[int]]:
    """Onze rubriek -> de Marktplaats-rubrieknummers (cat3) die erbij horen.

    Gelezen uit de extensie zelf (CATEGORY_MAP in background.js) plus de nummers
    die de server meestuurt (_MP_NUMMERS_VAN_DE_SERVER in jobs.py), zodat deze
    controle nooit een eigen, verouderde kopie van de tabel heeft.
    """
    uit: dict[str, set[int]] = collections.defaultdict(set)
    bg = open(os.path.join(REPO, "extension", "background.js"), encoding="utf-8").read()
    for naam, cat3 in re.findall(r'"([a-z0-9 &\'-]+)":\s*\{\s*cat1:\s*\d+,\s*cat3:\s*(\d+)', bg):
        uit[naam].add(int(cat3))
    jobs = open(os.path.join(REPO, "backend", "api", "jobs.py"), encoding="utf-8").read()
    for naam, l2 in re.findall(r'"([a-z0-9 &\'-]+)":\s*\{"l1":\s*\d+,\s*"l2":\s*(\d+)', jobs):
        uit[naam].add(int(l2))
    return uit


def _norm(t: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def vergelijk_een(item: dict, rij: dict | None, platform: str,
                  nummers: dict[str, set[int]], verkocht_op: set[str]) -> list[tuple[str, str]]:
    """Alle verschillen tussen ons artikel en zijn openbare advertentie.

    Los van netwerk en database, zodat de vergelijking zelf te beproeven is.
    """
    if rij is None:
        return [("weg", "staat niet op de openbare lijst van de verkoper")]
    fout: list[tuple[str, str]] = []
    andere = sorted(p for p in verkocht_op if p != platform)
    if andere:
        fout.append(("verkocht_elders", f"verkocht op {', '.join(andere)}, staat hier nog live"))
    verwacht = nummers.get(item.get("category") or "")
    if verwacht and rij.get("categoryId") not in verwacht:
        fout.append(("rubriek", f"artikel '{item.get('category')}' hoort in {sorted(verwacht)}, "
                                f"staat in {rij.get('categoryId')}"))
    prijs = item.get(f"price_{platform}") or item.get("price")
    cents = (rij.get("priceInfo") or {}).get("priceCents")
    soort = (rij.get("priceInfo") or {}).get("priceType")
    if prijs and soort == "FIXED" and cents is not None and abs(float(prijs) * 100 - cents) > 1:
        fout.append(("prijs", f"bij ons {float(prijs):.2f}, live {cents / 100:.2f}"))
    ons, live = _norm(item.get("title")), _norm(rij.get("title"))
    if ons and live and not (ons.startswith(live) or live.startswith(ons)):
        fout.append(("titel", f"bij ons '{item.get('title')}', live '{rij.get('title')}'"))
    oms = _norm(item.get("description"))[:60]
    live_oms = _norm(rij.get("categorySpecificDescription") or rij.get("description"))
    if oms and live_oms and not live_oms.startswith(oms[: min(len(oms), len(live_oms))]):
        fout.append(("omschrijving", "live omschrijving begint anders dan de onze"))
    if oms and not live_oms:
        fout.append(("omschrijving", "live omschrijving is leeg"))
    n_ons = min(len(item.get("photo_urls") or []), MAX_FOTOS.get(platform, 24))
    n_live = len(rij.get("pictures") or rij.get("imageUrls") or [])
    if n_live and n_live < n_ons:
        fout.append(("fotos", f"bij ons {n_ons}, live {n_live}"))
    return fout


async def openbare_rijen(platform: str, verkoper_id: int) -> dict[str, dict]:
    from backend.services.mp_enrich import (MAX_PAGINAS, PAGINA, UA, ZOEK_PER_PLATFORM,
                                            _json)
    zoek, basis = ZOEK_PER_PLATFORM[platform]
    uit: dict[str, dict] = {}
    async with httpx.AsyncClient(base_url=basis, headers={"User-Agent": UA},
                                 timeout=30, follow_redirects=True) as c:
        for pagina in range(MAX_PAGINAS):
            d = await _json(c, zoek, {"sellerIds[]": verkoper_id, "limit": PAGINA,
                                      "offset": pagina * PAGINA})
            rijen = d.get("listings") or []
            for r in rijen:
                if r.get("itemId"):
                    uit[r["itemId"]] = r
            if not rijen or len(uit) >= (d.get("totalResultCount") or 0):
                break
            await asyncio.sleep(1.0)
    return uit


async def verkoper_van(platform: str, titels: list[str]) -> int | None:
    from backend.services.mp_enrich import UA, ZOEK_PER_PLATFORM, zoek_verkoper_id
    zoek, basis = ZOEK_PER_PLATFORM[platform]
    async with httpx.AsyncClient(base_url=basis, headers={"User-Agent": UA},
                                 timeout=30, follow_redirects=True) as c:
        return await zoek_verkoper_id(c, titels[:40], zoek_url=zoek)


async def controleer_klant(db, uid: str, platform: str, nummers) -> dict:
    from backend.database import fetch_all, fetch_all_in
    items = fetch_all(lambda: db.table("items").select(
        "id,title,description,category,price,price_marktplaats,price_2dehands,photo_urls")
        .eq("user_id", uid))
    per_id = {i["id"]: i for i in items}
    rijen = fetch_all_in(lambda ids: db.table("listings").select(
        "item_id,platform,status,platform_listing_id").in_("item_id", ids), list(per_id))
    verkocht = collections.defaultdict(set)
    for r in rijen:
        if r.get("status") == "sold":
            verkocht[r["item_id"]].add(r["platform"])
    live = [r for r in rijen if r["platform"] == platform and r["status"] == "active"
            and r.get("platform_listing_id")]
    if not live:
        return {"user_id": uid, "live": 0, "fouten": []}
    titels = [per_id[r["item_id"]]["title"] for r in live if per_id.get(r["item_id"])]
    vid = await verkoper_van(platform, titels)
    if not vid:
        return {"user_id": uid, "live": len(live), "fouten": [],
                "meting_mislukt": "verkopersnummer niet te vinden op de openbare zoekpagina"}
    openbaar = await openbare_rijen(platform, vid)
    if not openbaar:
        return {"user_id": uid, "live": len(live), "fouten": [],
                "meting_mislukt": "openbare lijst leeg; niet als 'alles weg' lezen"}
    fouten = []
    for r in live:
        it = per_id.get(r["item_id"])
        if not it:
            continue
        for soort, wat in vergelijk_een(it, openbaar.get(r["platform_listing_id"]), platform,
                                        nummers, verkocht.get(r["item_id"], set())):
            fouten.append({"soort": soort, "wat": wat, "item_id": it["id"],
                           "titel": it["title"], "advertentie": r["platform_listing_id"]})
    return {"user_id": uid, "live": len(live), "openbaar": len(openbaar), "fouten": fouten}


def klanten_met_plaatsingen(db, uren: int, platform: str) -> list[str]:
    sinds = (datetime.now(timezone.utc) - timedelta(hours=uren)).isoformat()
    uids, off = set(), 0
    while True:
        blok = (db.table("jobs").select("user_id").eq("platform", platform)
                .eq("action", "create").eq("status", "done").gte("done_at", sinds)
                .order("done_at").range(off, off + 999).execute().data or [])
        uids |= {b["user_id"] for b in blok}
        if len(blok) < 1000:
            break
        off += 1000
    return sorted(uids)


async def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id")
    ap.add_argument("--uren", type=int, default=24)
    ap.add_argument("--platform", default="marktplaats", choices=["marktplaats", "2dehands"])
    ap.add_argument("--alles", action="store_true", help="elke fout tonen, niet alleen de telling")
    a = ap.parse_args()
    from backend.database import get_db
    db = get_db()
    nummers = rubriek_nummers()
    uids = [a.user_id] if a.user_id else klanten_met_plaatsingen(db, a.uren, a.platform)
    print(f"{a.platform}: {len(uids)} klant(en) na te kijken")
    for uid in uids:
        u = await controleer_klant(db, uid, a.platform, nummers)
        if u.get("meting_mislukt"):
            print(f"- {uid[:8]}: {u['live']} live, METING MISLUKT: {u['meting_mislukt']}")
            continue
        telling = collections.Counter(f["soort"] for f in u["fouten"])
        print(f"- {uid[:8]}: {u['live']} live bij ons, {u.get('openbaar', 0)} openbaar, "
              f"verschillen: {dict(telling) or 'geen'}")
        for f in u["fouten"] if a.alles else []:
            print(f"    [{f['soort']}] {f['titel'][:60]} ({f['advertentie']}): {f['wat']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
