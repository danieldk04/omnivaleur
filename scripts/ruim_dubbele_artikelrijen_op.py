#!/usr/bin/env python3
"""Dubbel geimporteerde ARTIKELRIJEN opruimen, zonder een advertentie aan te raken.

WAAROM (05-09-2026, Lynn van De Juiste Toon). Een import die twee keer liep maakt
een tweede artikelrij die naar PRECIES dezelfde advertentie wijst: zelfde kanaal,
zelfde advertentienummer. Delist zou die advertentie echt van het platform halen,
dus dat mag hier niet. Wat wel mag is de overtollige RIJ weghalen: dat raakt
alleen dit dashboard.

Wat dit script doet, en niets anders:

  1. Groepeert advertenties op kanaal + advertentienummer.
  2. Houdt per advertentie de OUDSTE artikelrij aan — daar hangt de langste
     geschiedenis aan, en dat is dezelfde regel als bij samenvoegen.
  3. Verwijdert alleen een jongere rij waarvan ELKE advertentie ook aan de
     behouden rij hangt. Heeft een rij ook een eigen advertentie, dan blijft hij
     staan: anders raken we het spoor naar die advertentie kwijt.
  4. Slaat een rij met een verkochte advertentie over. Verkoopgeschiedenis
     gooien we niet weg.

Er gaat geen enkele opdracht naar de extensie of naar een platform.

Gebruik:
    python3 scripts/ruim_dubbele_artikelrijen_op.py --user <uuid>
    python3 scripts/ruim_dubbele_artikelrijen_op.py --user <uuid> --apply
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BROK = 200


def _alle(db, tabel, kolommen, **eq):
    uit, start = [], 0
    while True:
        q = db.table(tabel).select(kolommen)
        for k, v in eq.items():
            q = q.eq(k, v)
        rijen = q.range(start, start + 999).execute().data or []
        uit += rijen
        if len(rijen) < 1000:
            return uit
        start += 1000


def main(user_id: str, apply: bool) -> None:
    from backend.database import get_db

    db = get_db()
    items = _alle(db, "items", "id,title,created_at", user_id=user_id)
    if not items:
        print(f"Geen artikelen gevonden voor {user_id}.")
        return
    item_van = {it["id"]: it for it in items}
    ids = list(item_van)

    listings = []
    for s in range(0, len(ids), BROK):
        listings += (db.table("listings")
                     .select("id,item_id,platform,platform_listing_id,status")
                     .in_("item_id", ids[s:s + BROK]).execute().data or [])

    per_item = defaultdict(list)
    eigenaars = defaultdict(set)   # (kanaal, advertentienummer) -> {item_id}
    for l in listings:
        per_item[l["item_id"]].append(l)
        if l.get("platform_listing_id"):
            eigenaars[(l["platform"], l["platform_listing_id"])].add(l["item_id"])

    gedeeld = {k: v for k, v in eigenaars.items() if len(v) > 1}
    print(f"{len(items)} artikelen, {len(listings)} advertentieregels.")
    print(f"{len(gedeeld)} advertenties hangen aan meer dan één artikelrij.")

    # Per advertentie de oudste rij aanhouden; alles wat overblijft is kandidaat.
    behouden, kandidaten = set(), set()
    for _, item_ids in gedeeld.items():
        gesorteerd = sorted(item_ids, key=lambda i: (item_van[i].get("created_at") or "", i))
        behouden.add(gesorteerd[0])
        kandidaten.update(gesorteerd[1:])
    kandidaten -= behouden

    weg, overgeslagen = [], []
    for iid in sorted(kandidaten):
        rijen = per_item.get(iid, [])
        if any((r.get("status") or "").startswith("sold") for r in rijen):
            overgeslagen.append((iid, "heeft een verkochte advertentie"))
            continue
        eigen = [r for r in rijen
                 if not r.get("platform_listing_id")
                 or len(eigenaars[(r["platform"], r["platform_listing_id"])]) == 1]
        if eigen:
            kanalen = ", ".join(sorted({r["platform"] for r in eigen}))
            overgeslagen.append((iid, f"heeft ook een eigen advertentie op {kanalen}"))
            continue
        weg.append(iid)

    for iid in weg:
        titel = (item_van[iid].get("title") or "")[:60]
        kanalen = ", ".join(sorted({r["platform"] for r in per_item.get(iid, [])}))
        print(f"  WEG  {iid}  {titel}  ({kanalen})")
    for iid, reden in overgeslagen:
        titel = (item_van[iid].get("title") or "")[:60]
        print(f"  laat staan  {iid}  {titel}  — {reden}")

    print(f"\n{len(weg)} rijen te verwijderen, {len(overgeslagen)} overgeslagen.")
    if not apply:
        print("Proefdraai — er is niets veranderd. Voeg --apply toe om het echt te doen.")
        return

    for iid in weg:
        lids = [r["id"] for r in per_item.get(iid, [])]
        for lid in lids:
            db.table("sync_events").delete().eq("listing_id", lid).execute()
        db.table("listings").delete().eq("item_id", iid).execute()
        db.table("jobs").delete().eq("item_id", iid).execute()
        db.table("items").delete().eq("id", iid).execute()
    print(f"{len(weg)} rijen verwijderd. Er is geen advertentie aangeraakt.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    main(a.user, a.apply)
