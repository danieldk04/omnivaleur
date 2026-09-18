#!/usr/bin/env python3
"""Zet de wachtrij terug die op één betaalpagina ten onrechte is weggenomen.

WAT ER MIS WAS (18-09-2026, De Juiste Toon)

Om 06:41 UTC kwam één advertentie ("Wandkleed geborduurd 89/69 cm", rubriek
wonen wanddecoraties) op de betaalpagina van 2dehands uit. Twaalf minuten
eerder, om 06:29, ging er nog een advertentie van hem gratis online; de dag
ervoor 200, in totaal 219. Toch ging op die ene waarneming het hele kanaal
dicht, werden zijn 36 wachtende opdrachten teruggenomen en las hij:
"That is why nothing has ever gone online there."

De code is gerepareerd (zie `_kanaal_hard_dicht`): een betaalpagina sluit het
hele kanaal alleen nog als daar nooit iets gratis online is gegaan. Maar de
teruggenomen opdrachten staan op 'cancelled' en de advertentierijen op 'error'
met een melding die niet klopt. Zonder deze ronde blijft dat staan tot iemand
ze met de hand opnieuw aanklikt.

Lezen is gratis, schrijven alleen met --apply:
    python3 scripts/herstel_betaalmuur_valse_afsluiting.py
    python3 scripts/herstel_betaalmuur_valse_afsluiting.py --apply
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# De zin die alleen in de kanaalbrede betaalmuur-melding staat.
HERKENBAAR = "place adverts for free"


def _eerlijke_tekst(platform: str) -> str:
    """Wat er op een advertentierij komt waar de onware melding op stond."""
    site = {"marktplaats": "Marktplaats (marktplaats.nl)",
            "2dehands": "2dehands (2dehands.be)"}.get(platform, platform)
    return (
        f"This did not go online, and the message that stood here before was wrong: it said "
        f"{site} never lets your account place adverts for free. It does, and it did on the same "
        f"day. One single advert of yours was put on an order to be paid instead of published, "
        f"and we switched off the whole channel on that one observation. That was our mistake.\n\n"
        f"{site} is back on and nothing has been paid. Press publish again for this item."
    )


def main(apply: bool) -> None:
    from backend.database import get_db, fetch_all
    from backend.api.jobs import _kanaal_hard_dicht

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    for platform in ("2dehands", "marktplaats"):
        rijen = (db.table("jobs")
                 .select("id,user_id,item_id,payload,created_at,result")
                 .eq("platform", platform).eq("action", "create").eq("status", "cancelled")
                 .filter("result->>error", "ilike", f"%{HERKENBAAR}%")
                 .limit(2000).execute().data or [])
        # Alleen wat de wachtrij-stop zelf heeft weggezet. De opdracht die de
        # betaalpagina ECHT zag is een waarneming en blijft staan.
        rijen = [j for j in rijen
                 if str((j.get("result") or {}).get("cancelled") or "") == "queue stopped"]
        per_klant: dict[str, list] = {}
        for j in rijen:
            per_klant.setdefault(j["user_id"], []).append(j)
        # Ook de klanten die alleen een rode balk met die tekst hebben en geen
        # teruggenomen opdracht. Bij de tweede klant van 18-09 was dat precies
        # zo: één advertentierij, geen wachtrij.
        for r in fetch_all(lambda: db.table("listings")
                           .select("id,items!inner(user_id)").eq("platform", platform)
                           .eq("status", "error")
                           .ilike("error_message", f"%{HERKENBAAR}%"), page_size=500):
            eigenaar = (r.get("items") or {}).get("user_id")
            if eigenaar:
                per_klant.setdefault(eigenaar, [])
        for user_id, werk in per_klant.items():
            if _kanaal_hard_dicht(db, user_id, platform):
                print(f"{platform} {user_id[:8]}: kanaal is aantoonbaar dicht, met rust gelaten")
                continue
            # Een herplaatsing heeft haar teller al teruggekregen; die opnieuw
            # uitdelen zou hem twee keer laten lenen. Die laat de herplaatser zelf.
            werk = [j for j in werk if not (j.get("payload") or {}).get("_refresh_rollback")]
            ids = [j["item_id"] for j in werk if j.get("item_id")]
            # Al een levende advertentie op dit kanaal? Dan zou dit een dubbele worden.
            live: set = set()
            lopend: set = set()
            for i in range(0, len(ids), 200):
                brok = ids[i:i + 200]
                live |= {r["item_id"] for r in (db.table("listings")
                         .select("item_id,platform_listing_id").in_("item_id", brok)
                         .eq("platform", platform).execute().data or [])
                         if r.get("platform_listing_id")}
                lopend |= {r["item_id"] for r in (db.table("jobs").select("item_id")
                           .eq("user_id", user_id).eq("platform", platform)
                           .in_("status", ["pending", "claimed"]).in_("item_id", brok)
                           .execute().data or [])}
            terug = [j for j in werk if j.get("item_id")
                     and j["item_id"] not in live and j["item_id"] not in lopend]
            overgeslagen = len(werk) - len(terug)
            print(f"{platform} {user_id[:8]}: {len(terug)} opdrachten terug in de rij"
                  f"{f', {overgeslagen} overgeslagen (staat al online of loopt al)' if overgeslagen else ''}")
            if apply and terug:
                for i in range(0, len(terug), 200):
                    brok = [j["id"] for j in terug[i:i + 200]]
                    # Verse plek in de rij: met de oude created_at ruimt de
                    # driedagenveger ze diezelfde nacht alsnog op.
                    db.table("jobs").update({
                        "status": "pending", "result": None, "done_at": None,
                        "created_at": now,
                    }).in_("id", brok).execute()
                item_ids = sorted({j["item_id"] for j in terug})
                for i in range(0, len(item_ids), 200):
                    db.table("listings").update({
                        "status": "pending", "error_message": None,
                    }).in_("item_id", item_ids[i:i + 200]).eq("platform", platform).eq(
                        "status", "error").execute()

            # De rode balken die de onware melding dragen en NIET terug de rij in
            # gaan: die krijgen de tekst die wel klopt.
            staan = fetch_all(lambda: db.table("listings")
                              .select("id,item_id,status,items!inner(user_id)")
                              .eq("items.user_id", user_id).eq("platform", platform)
                              .eq("status", "error")
                              .ilike("error_message", f"%{HERKENBAAR}%"), page_size=500)
            print(f"{platform} {user_id[:8]}: {len(staan)} advertentierijen dragen nog de onware melding")
            if apply and staan:
                tekst = _eerlijke_tekst(platform)
                rij_ids = [r["id"] for r in staan]
                for i in range(0, len(rij_ids), 200):
                    db.table("listings").update({"error_message": tekst}).in_(
                        "id", rij_ids[i:i + 200]).execute()
    print("\nklaar." if apply else "\nniets geschreven (draai met --apply).")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    main(p.parse_args().apply)
