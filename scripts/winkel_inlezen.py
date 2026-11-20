#!/usr/bin/env python3
"""Een webshop zonder koppeling (JouwWeb e.d.) inlezen als service voor één klant.

  lijst ADRES                      toont wat er gelezen wordt, schrijft niets
  importeer ADRES --user-id UUID   zelfde, en zet de artikelen in dat account
                                   (alleen met --uitvoeren; zonder is het een proef)

Alleen voor een klant die erom gevraagd heeft en alleen NA zijn aanmelding. Wat al
in het account staat (zelfde artikelnummer) wordt nooit overschreven of dubbel gemaakt.
Verkochte producten (uitverkocht in de winkel) worden niet meegenomen.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import ItemCreate  # noqa: E402
from backend.platforms.webshop_lezer import WinkelFout, lees_winkel  # noqa: E402


def naar_artikel(p: dict) -> dict:
    """Een gelezen product in de vorm van een Omnivaleur-artikel.

    Staat en rubriek weten we niet uit de winkel; de staat blijft de standaard
    ("good") en de rubriek bepaalt de plaatsing zelf, zoals bij elk ander artikel."""
    return ItemCreate(
        title=(p["title"] or "")[:100],
        description=p.get("description"),
        price=p["price"],
        sku=p.get("sku") or p["platform_listing_id"],
        photo_urls=p.get("photo_urls") or [],
    ).model_dump()


def lees(adres: str) -> tuple[list[dict], list[dict]]:
    producten, mislukt = lees_winkel(adres)
    if mislukt:
        print(f"LET OP: {len(mislukt)} pagina's niet gelezen, bijvoorbeeld {mislukt[0]}")
    te_koop = [p for p in producten if not p["is_closed"] and p.get("price")]
    overgeslagen = [p for p in producten if p not in te_koop]
    return te_koop, overgeslagen


def rapport(te_koop: list[dict], overgeslagen: list[dict]) -> list[dict]:
    artikelen = [naar_artikel(p) for p in te_koop]
    # Twee producten met hetzelfde artikelnummer (haar eigen vergissing, 2 van 154):
    # een nummer is per account uniek, dus het tweede krijgt het productnummer erachter.
    gezien: set[str] = set()
    dubbel = 0
    for a, p in zip(artikelen, te_koop):
        if a["sku"] in gezien:
            a["sku"] = f"{a['sku']}-{p['platform_listing_id']}"
            dubbel += 1
        gezien.add(a["sku"])
    print(f"{len(artikelen)} artikelen klaar, {len(overgeslagen)} overgeslagen (uitverkocht of zonder prijs)")
    print(f"foto's: {sum(len(a['photo_urls']) for a in artikelen)} in totaal, "
          f"min {min(len(a['photo_urls']) for a in artikelen)} per artikel")
    print(f"dubbele artikelnummers hernoemd: {dubbel}; unieke nummers: {len({a['sku'] for a in artikelen})}")
    return artikelen


async def zet_in_account(artikelen: list[dict], user_id: str) -> None:
    from backend.database import get_db
    from backend.services.photo_mirror import mirror_photos_bulk

    db = get_db()
    bestaand = {r["sku"] for r in (db.table("items").select("sku").eq("user_id", user_id).execute().data or [])}
    nieuw = [a for a in artikelen if a["sku"] not in bestaand]
    print(f"{len(artikelen) - len(nieuw)} staan er al (zelfde artikelnummer), {len(nieuw)} komen erbij")
    fotos = await mirror_photos_bulk([a["photo_urls"] for a in nieuw], user_id)
    for a, f in zip(nieuw, fotos):
        a["photo_urls"] = f or a["photo_urls"]
        a["id"] = str(uuid.uuid4())
        a["user_id"] = user_id
    for i in range(0, len(nieuw), 50):
        db.table("items").insert(nieuw[i:i + 50]).execute()
    print(f"klaar: {len(nieuw)} artikelen aangemaakt")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("opdracht", choices=["lijst", "importeer"])
    ap.add_argument("adres")
    ap.add_argument("--user-id")
    ap.add_argument("--uitvoeren", action="store_true")
    a = ap.parse_args()
    try:
        te_koop, overgeslagen = lees(a.adres)
    except WinkelFout as e:
        sys.exit(f"Mislukt: {e}")
    artikelen = rapport(te_koop, overgeslagen)
    if a.opdracht == "importeer":
        if not a.user_id:
            sys.exit("--user-id ontbreekt")
        if not a.uitvoeren:
            print("PROEF: niets geschreven. Voeg --uitvoeren toe om echt te importeren.")
            return
        asyncio.run(zet_in_account(artikelen, a.user_id))


if __name__ == "__main__":
    main()
