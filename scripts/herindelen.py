"""
Items zonder categorie alsnog indelen.

Waarom dit bestaat: een import kan een item aanmaken zonder categorie — omdat de
bron er geen meelevert (Admarkt) of omdat de taxonomie destijds geen passende
tak had. Zo'n item toont in het dashboard bij elk veld een uitroepteken, vraagt
om maat en merk die nergens op slaan, en is niet te publiceren. Met honderden
items is ze langslopen geen optie.

VEILIGHEID, en dit is het belangrijkste aan dit script:
  - het raakt ALLEEN items aan waar de categorie leeg is. Een categorie die de
    verkoper zelf heeft gezet wordt nooit overschreven;
  - standaard is het een droge proef. Pas met --schrijf gaat er iets naar de
    database;
  - het draait per gebruiker, nooit over alle accounts tegelijk.

Gebruik:
    python3 scripts/herindelen.py --user <uuid>            # droge proef
    python3 scripts/herindelen.py --user <uuid> --schrijf  # echt doorvoeren
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.imports import _infer_attributes_smart  # noqa: E402
from backend.database import get_db  # noqa: E402

# Niet honderden gelijktijdige aanroepen: dat loopt tegen de snelheidslimiet en
# maakt de fouten onnavolgbaar. Tien tegelijk is snel zat.
TEGELIJK = 10


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="user_id van de gebruiker")
    ap.add_argument("--schrijf", action="store_true", help="echt doorvoeren")
    ap.add_argument("--max", type=int, default=0, help="hooguit zoveel items")
    ap.add_argument("--overschrijf", default="",
                    help="komma-lijst met categorie-voorvoegsels die OOK opnieuw "
                         "ingedeeld mogen worden, bijvoorbeeld: unisex,muziek. "
                         "Gebruik dit alleen voor categorieen die aantoonbaar uit "
                         "een kapotte indeling komen; een keuze van de verkoper "
                         "zelf hoor je nooit te overschrijven.")
    args = ap.parse_args()

    db = get_db()
    rijen = (db.table("items")
             .select("id,title,description,brand,category,gender,color")
             .eq("user_id", args.user)
             .limit(5000).execute().data or [])
    voorvoegsels = tuple(v.strip().lower() for v in args.overschrijf.split(",") if v.strip())
    def opnieuw(r):
        cat = str(r.get("category") or "").strip().lower()
        if not cat:
            return True                      # leeg: altijd
        return bool(voorvoegsels) and cat.startswith(voorvoegsels)
    leeg = [r for r in rijen if opnieuw(r)]
    if args.max:
        leeg = leeg[:args.max]
    zonder = sum(1 for r in rijen if not str(r.get("category") or "").strip())
    print(f"{len(rijen)} items: {zonder} zonder categorie"
          + (f", {len(leeg) - zonder} met een categorie die opnieuw mag "
             f"({', '.join(voorvoegsels)})" if voorvoegsels else "") + "\n")
    if not leeg:
        return

    hek = asyncio.Semaphore(TEGELIJK)

    async def een(item):
        async with hek:
            try:
                gok = await _infer_attributes_smart(
                    item.get("title"), item.get("description"), item.get("brand"))
            except Exception as e:  # noqa: BLE001
                print(f"  ! {str(item.get('title'))[:40]}: {e}")
                gok = {}
            return item, gok

    uitkomst = await asyncio.gather(*(een(i) for i in leeg))

    tellers = collections.Counter()
    doorvoeren = []
    for item, gok in uitkomst:
        cat, geslacht = gok.get("category"), gok.get("gender")
        if not cat:
            tellers["geen resultaat"] += 1
            continue
        tellers[cat.split()[0]] += 1
        patch = {"category": cat}
        # Bij een item dat opnieuw wordt ingedeeld hoort het geslacht mee te gaan:
        # anders blijft er "unisex" staan bij iets wat nu "antiek" is, en dan
        # klopt het scherm nog steeds niet.
        if geslacht and (not str(item.get("gender") or "").strip()
                         or not str(item.get("category") or "").strip() == ""):
            patch["gender"] = geslacht
        # Kleur alleen invullen als hij leeg is; nooit overschrijven.
        if gok.get("color") and not str(item.get("color") or "").strip():
            patch["color"] = gok["color"]
        doorvoeren.append((item, patch))

    print("VERDELING")
    for tak, n in tellers.most_common():
        print(f"  {tak:16s} {n:4d}")
    print("\nEERSTE TWINTIG")
    for item, patch in doorvoeren[:20]:
        print(f"  {str(item.get('title'))[:44]:46s} → {patch['category']}")

    if not args.schrijf:
        print(f"\nDROGE PROEF — er is niets gewijzigd. "
              f"Draai met --schrijf om {len(doorvoeren)} items bij te werken.")
        return

    goed = 0
    for item, patch in doorvoeren:
        try:
            db.table("items").update(patch).eq("id", item["id"]).execute()
            goed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ! {item['id']}: {e}")
    print(f"\n{goed} van {len(doorvoeren)} items bijgewerkt.")


if __name__ == "__main__":
    asyncio.run(main())
