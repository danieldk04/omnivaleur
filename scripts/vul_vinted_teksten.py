#!/usr/bin/env python3
"""Ontbrekende Vinted-advertentieteksten alsnog ophalen, voor één verkoper.

WAAROM DIT ER IS (02-09-2026)
Toon (dejuistetoon) hield na het importeren 244 artikelen zonder omschrijving
over. Zonder omschrijving weigert het dashboard te publiceren naar Marktplaats,
2dehands en Facebook, dus stond zijn publiceervenster vol grijze vakjes zonder
één knop die iets deed. De tekst stond gewoon nog op zijn Vinted-advertenties.

De oorzaak is gerepareerd (de scan slaat over wat we al hebben, en een
afgeknepen scan wist niets meer). Dit script haalt in wat er al scheefstond,
zonder dat de verkoper er iets voor hoeft te doen.

Vinted laat gemeten ongeveer vijftien pagina's per minuut door, dus 244
advertenties duren een minuut of twintig. Dat is geen instelling die sneller kan.

Gebruik:
    python3 scripts/vul_vinted_teksten.py --user <id>            # laat zien wat het zou doen
    python3 scripts/vul_vinted_teksten.py --user <id> --apply    # voer het uit
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _draai(user_id: str, apply: bool) -> None:
    from backend.database import get_db, fetch_all, fetch_all_in
    from backend.services.vinted_enrich import verrijk

    db = get_db()
    zonder = {r["id"] for r in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", user_id)
        .or_("description.is.null,description.eq."))}
    if not zonder:
        print("Niets te doen: elk artikel heeft al tekst.")
        return
    levend = {l["item_id"] for l in fetch_all_in(
        lambda: db.table("listings").select("item_id")
        .eq("platform", "vinted").eq("status", "active"),
        "item_id", sorted(zonder)) if l.get("item_id")}
    haalbaar = zonder & levend
    print(f"{len(zonder)} artikelen zonder tekst, "
          f"{len(haalbaar)} daarvan staan nog op Vinted en zijn dus op te halen.")
    print(f"{len(zonder) - len(haalbaar)} moeten met de hand, die advertentie bestaat niet meer.")
    if not apply:
        print("\nProefdraai. Met --apply wordt het echt gedaan.")
        return

    start = time.monotonic()
    gevuld_totaal = 0
    for ronde in range(1, 200):
        uit = await verrijk(db, user_id)
        gevuld_totaal += uit["gevuld"]
        print(f"  ronde {ronde:>3}: +{uit['gevuld']} gevuld "
              f"(totaal {gevuld_totaal}/{len(haalbaar)}), "
              f"nog {uit['te_doen']} open, {uit['reden']}")
        if not uit["te_doen"]:
            break
        if uit["geknepen"]:
            print("      Vinted knijpt af — een minuut wachten.")
            await asyncio.sleep(60)
        elif not uit["gevuld"]:
            print("      niets meer op te halen, gestopt.")
            break
    print(f"\nKlaar: {gevuld_totaal} teksten opgehaald in "
          f"{int(time.monotonic() - start)} seconden.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    asyncio.run(_draai(a.user, a.apply))


if __name__ == "__main__":
    main()
