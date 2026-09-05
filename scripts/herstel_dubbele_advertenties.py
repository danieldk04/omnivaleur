#!/usr/bin/env python3
"""De dubbele Marktplaats-advertenties opruimen die de herplaatslus maakte.

WAAROM (05-09-2026, Amanda Haas). Een geslaagde herplaatsing liet de oude rij op
'relisting' staan, en de reddingsronde las dat als "halverwege blijven steken":
elke zes uur zette hij er nog een advertentie voor klaar. Gevolg: hetzelfde
artikel stond met drie of vier identieke advertenties tegelijk op Marktplaats.
De oorzaak is gerepareerd (backend/api/jobs.py + backend/services/relist.py),
maar de advertenties die er al staan gaan daar niet vanzelf van weg.

Wat dit script doet, en niets anders:

  1. Zoekt artikelen met meer dan één ACTIEVE advertentie op hetzelfde kanaal.
  2. Houdt de NIEUWSTE aan — die staat het hoogst in de zoekresultaten — en zet
     voor elke oudere kopie een verwijderopdracht klaar, op advertentienummer.
     De extensie zoekt eerst op dat nummer en weigert te gokken als hij twijfelt,
     dus er kan nooit de verkeerde weg.
  3. Zet import-kandidaten die allang aan een artikel hangen op 'linked', zodat
     de te-beoordelen lijst weer laat zien wat de verkoper ECHT zelf plaatste.

Zonder --apply verandert er niets; dan vertelt hij alleen wat hij zou doen.

Gebruik:
    python3 scripts/herstel_dubbele_advertenties.py --user <uuid>
    python3 scripts/herstel_dubbele_advertenties.py --user <uuid> --apply
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
    from backend.services.crosslist import _last_listed_title

    db = get_db()
    items = _alle(db, "items", "id,title", user_id=user_id)
    if not items:
        print(f"Geen artikelen gevonden voor {user_id}.")
        return
    titel_van = {it["id"]: it.get("title") for it in items}
    ids = [it["id"] for it in items]

    listings = []
    for i in range(0, len(ids), BROK):
        listings += (db.table("listings").select("*")
                     .in_("item_id", ids[i:i + BROK]).execute().data or [])

    # ── 1. Dubbele actieve advertenties ──────────────────────────────────────
    per_kanaal = defaultdict(list)
    for l in listings:
        if l.get("status") == "active" and l.get("platform_listing_id"):
            per_kanaal[(l["item_id"], l["platform"])].append(l)

    def _jongste_eerst(rij):
        return str(rij.get("listed_at") or rij.get("created_at") or "")

    # Alleen kanalen die de extensie bedient. Een verwijderopdracht voor eBay of
    # Shopify wordt door niemand opgepakt: die lopen via hun eigen API. Zo'n rij
    # blijft dan eeuwig in de wachtrij staan en telt mee in de teller op het
    # dashboard (05-09-2026 gebeurd op Daniels eigen account, Shopify).
    from backend.services.crosslist import EXTENSION_PLATFORMS

    te_verwijderen, buiten_bereik = [], []
    for (item_id, platform), rijen in per_kanaal.items():
        if len(rijen) < 2:
            continue
        if platform not in EXTENSION_PLATFORMS:
            buiten_bereik.append((titel_van.get(item_id), platform, len(rijen)))
            continue
        rijen.sort(key=_jongste_eerst, reverse=True)
        houden, weg = rijen[0], rijen[1:]
        print(f"\n{titel_van.get(item_id)!r} op {platform}: {len(rijen)} advertenties")
        print(f"   blijft staan: {houden['platform_listing_id']} "
              f"({str(houden.get('listed_at'))[:19]})")
        for r in weg:
            print(f"   weghalen    : {r['platform_listing_id']} "
                  f"({str(r.get('listed_at'))[:19]})")
            te_verwijderen.append((item_id, platform, r))

    for titel, platform, aantal in buiten_bereik:
        print(f"\n{titel!r} op {platform}: {aantal} advertenties — NIET automatisch op te "
              f"ruimen, dat kanaal loopt via zijn eigen API en niet via de extensie.")

    # ── 2. Kandidaten die allang gekoppeld zijn ──────────────────────────────
    nummers_in_gebruik = {(l["platform"], str(l["platform_listing_id"]))
                          for l in listings if l.get("platform_listing_id")}
    kandidaten = _alle(db, "import_candidates",
                       "id,platform,platform_listing_id,status,title", user_id=user_id)
    opschonen = [c for c in kandidaten
                 if c.get("status") == "pending"
                 and (c["platform"], str(c["platform_listing_id"])) in nummers_in_gebruik]
    echt_nieuw = [c for c in kandidaten
                  if c.get("status") == "pending"
                  and (c["platform"], str(c["platform_listing_id"])) not in nummers_in_gebruik]

    print(f"\nTe beoordelen lijst: {len(opschonen)} advertenties staan er onterecht op "
          f"(hangen al aan een artikel), {len(echt_nieuw)} zijn echt nieuw:")
    for c in echt_nieuw[:20]:
        print(f"   {c['platform']} {c['platform_listing_id']}  {(c.get('title') or '')[:60]}")

    # ── 3. Vastgelopen herplaatsingen ────────────────────────────────────────
    vast = [l for l in listings if l.get("status") == "relisting"]
    met_vervanger = [l for l in vast
                     if any(o.get("status") == "active" and o["item_id"] == l["item_id"]
                            and o["platform"] == l["platform"]
                            and str(o.get("platform_listing_id")) != str(l.get("platform_listing_id"))
                            for o in listings)]
    print(f"\nRijen op 'relisting': {len(vast)}, waarvan {len(met_vervanger)} "
          f"met een vervanger die al live staat (die sluit de reddingsronde nu zelf af).")

    if not apply:
        print("\n(Proefdraai — er is niets gewijzigd. Draai met --apply om het echt te doen.)")
        return

    gezet = 0
    for item_id, platform, rij in te_verwijderen:
        item = db.table("items").select("*").eq("id", item_id).single().execute().data
        payload = {
            **item,
            "title": _last_listed_title(db, item_id, platform, item.get("title", "")),
            "platform_listing_id": rij["platform_listing_id"],
            "platform_listing_url": rij.get("platform_listing_url"),
        }
        db.table("jobs").insert({
            "user_id": user_id,
            "item_id": item_id,
            "platform": platform,
            "action": "delete",
            "status": "pending",
            "payload": payload,
        }).execute()
        gezet += 1

    for c in opschonen:
        db.table("import_candidates").update({"status": "linked"}).eq("id", c["id"]).execute()

    print(f"\nKlaar: {gezet} verwijderopdracht(en) klaargezet, "
          f"{len(opschonen)} kandidaat(en) op 'linked'.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    main(a.user, a.apply)
