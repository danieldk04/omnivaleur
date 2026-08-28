"""Advertenties terugzetten die bij een herplaatsing wél weg zijn maar niet terug kwamen.

WAAROM DIT ER IS (28-08-2026, Jaap van zilverwebsite.nl)
Herplaatsen is twee stappen: eerst weg bij Marktplaats, dan opnieuw plaatsen.
Struikelde de tweede stap — bij hem: items zonder omschrijving, die het
plaatsformulier weigert — dan is de advertentie weg en komt hij nergens meer
terug. De advertentie staat dan op 'delisted', en de opruimronde
(herstel_vastgelopen_werk) kijkt alleen naar 'relisting'.

Dit script zoekt precies die gevallen op: vandaag (of de laatste N dagen) een
geslaagde verwijdering, een mislukte plaatsing, en een advertentie die nu op
'delisted' staat. Wat inmiddels wél een omschrijving en foto's heeft, wordt op
'relisting' gezet — dan zet de gewone opruimronde er vanzelf een plaatsopdracht
achteraan. Wat nog steeds geen tekst heeft blijft met rust: dat zou opnieuw
mislukken.

Gebruik:
    python scripts/herstel_verwijderde_advertenties.py --email info@zilverwebsite.nl
    python scripts/herstel_verwijderde_advertenties.py --email ... --schrijf
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--platform", default="marktplaats")
    ap.add_argument("--dagen", type=int, default=1)
    ap.add_argument("--schrijf", action="store_true", help="zonder deze vlag: alleen tellen")
    args = ap.parse_args()

    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    gebruiker = next((u for u in db.auth.admin.list_users()
                      if (u.email or "").lower() == args.email.lower()), None)
    if not gebruiker:
        print(f"Geen gebruiker met e-mailadres {args.email}")
        return 1

    sinds = (datetime.now(timezone.utc) - timedelta(days=args.dagen)).date().isoformat()
    weg = {j["item_id"] for j in (db.table("jobs").select("item_id")
           .eq("user_id", gebruiker.id).eq("platform", args.platform)
           .eq("action", "delete").eq("status", "done")
           .gte("created_at", sinds).execute().data or [])}
    mislukt = {j["item_id"] for j in (db.table("jobs").select("item_id")
               .eq("user_id", gebruiker.id).eq("platform", args.platform)
               .eq("action", "create").eq("status", "error")
               .gte("created_at", sinds).execute().data or [])}
    kandidaten = weg & mislukt
    print(f"{len(weg)} verwijderd sinds {sinds}, {len(mislukt)} plaatsingen mislukt, "
          f"{len(kandidaten)} advertenties zijn dus weg zonder vervanger")
    if not kandidaten:
        return 0

    ids = list(kandidaten)
    items = {}
    for i in range(0, len(ids), 100):
        for r in (db.table("items").select("id,title,description,photo_urls")
                  .in_("id", ids[i:i + 100]).execute().data or []):
            items[r["id"]] = r

    klaar, zonder_tekst = [], []
    for iid in ids:
        it = items.get(iid) or {}
        if str(it.get("description") or "").strip() and (it.get("photo_urls") or []):
            klaar.append(iid)
        else:
            zonder_tekst.append(it.get("title") or iid)

    print(f"\nKan terug: {len(klaar)}")
    print(f"Kan (nog) niet terug — geen omschrijving of foto's: {len(zonder_tekst)}")
    for t in zonder_tekst[:20]:
        print(f"  - {t}")

    if not args.schrijf:
        print("\n(proefdraai — draai opnieuw met --schrijf om ze in te plannen)")
        return 0

    gezet = 0
    for iid in klaar:
        r = (db.table("listings").update({"status": "relisting"})
             .eq("item_id", iid).eq("platform", args.platform)
             .eq("status", "delisted").execute())
        gezet += len(r.data or [])
    print(f"\n{gezet} advertentie(s) ingepland om terug te komen. De opruimronde "
          f"(elke 6 uur) zet er een plaatsopdracht achteraan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
