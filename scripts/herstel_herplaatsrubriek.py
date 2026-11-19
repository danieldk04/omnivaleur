"""Wachtende herplaatsingen alsnog hun eigen Marktplaats/2dehands-rubriek meegeven.

WAAROM (19-11-2026, Esther, hetisvintastisch)
Sinds 14-11-2026 zet Marktplaats de rubriek niet meer als "l1CategoryId" op de
advertentiepagina. mp_enrich.categorie_uit_html gaf daardoor bij elke
advertentie een leeg blok, en elke herplaatsing (refresh_listing) viel terug op
onze eigen geraden rubriek. Gemeten: van 14 t/m 19-11 kreeg geen enkele van de
~800 herplaatsingen nog zijn eigen rubriek mee. De lezer is gerepareerd, maar de
opdrachten die al klaarstaan hebben hun payload al: die gaan anders alsnog fout.

Dit script loopt de wachtende 'create'-opdrachten met _vervangt_listing_id en
zonder mp_category langs, leest de oude advertentie (die nog online staat zolang
de bijbehorende verwijderopdracht wacht) en zet mp_category in de payload.
Alleen opdrachten op 'pending'; de update eist dat ze nog op 'pending' staan.

    python3 scripts/herstel_herplaatsrubriek.py            # droog: alleen tellen
    python3 scripts/herstel_herplaatsrubriek.py --schrijf
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schrijf", action="store_true")
    ap.add_argument("--user-id")
    a = ap.parse_args()
    from backend.database import get_db
    from backend.services.mp_enrich import advertentie_kenmerken
    db = get_db()
    users = [a.user_id] if a.user_id else [
        h["user_id"] for h in db.table("extension_heartbeat").select("user_id").execute().data]
    logpad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                          f"herstel_herplaatsrubriek_{datetime.now():%Y%m%d_%H%M}.jsonl")
    os.makedirs(os.path.dirname(logpad), exist_ok=True)
    gezet = leeg = mis = 0
    with open(logpad, "a", encoding="utf-8") as log:
        for u in users:
            jobs = (db.table("jobs").select("id,item_id,platform,payload")
                    .eq("user_id", u).eq("action", "create").eq("status", "pending")
                    .in_("platform", ["marktplaats", "2dehands"]).limit(5000).execute().data or [])
            for j in jobs:
                pl = j.get("payload") or {}
                if not pl.get("_vervangt_listing_id") or (pl.get("mp_category") or {}).get("l1"):
                    continue
                rij = (db.table("listings").select("platform_listing_url,status")
                       .eq("id", pl["_vervangt_listing_id"]).execute().data or [None])[0]
                url = (rij or {}).get("platform_listing_url")
                k = await advertentie_kenmerken(url) if url else {}
                cat = k.get("mp_category") or {}
                await asyncio.sleep(1.0)   # beleefd: zie de 403-rem in mp_enrich
                if not cat.get("l1"):
                    leeg += 1
                    log.write(json.dumps({"job": j["id"], "url": url, "uitkomst": "geen rubriek"}) + "\n")
                    continue
                log.write(json.dumps({"job": j["id"], "url": url, "mp_category": cat,
                                      "oude_payload_had": None}) + "\n")
                if a.schrijf:
                    r = (db.table("jobs").update({"payload": {**pl, "mp_category": cat}})
                         .eq("id", j["id"]).eq("status", "pending").execute().data)
                    if r:
                        gezet += 1
                    else:
                        mis += 1   # intussen opgepakt door de extensie
                else:
                    gezet += 1
    print(f"{'gezet' if a.schrijf else 'zou zetten'}: {gezet}, geen rubriek te lezen: {leeg}, "
          f"intussen opgepakt: {mis}. Logboek: {logpad}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
