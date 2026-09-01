#!/usr/bin/env python3
"""Advertenties uit de herplaatslus halen die er nu nog in zitten.

WAAROM DIT ER IS (01-09-2026)
De lus zelf is dichtgezet in backend/api/jobs.py: een advertentie die al weg was
toen wij hem kwamen weghalen, en die te jong was om vanzelf te verlopen, wordt
sindsdien een verkoopvraag in plaats van een nieuwe advertentie. Maar de
artikelen die er op dat moment al in zaten blijven waar ze zijn: hun oude
advertentie is verdwenen, er staat een verse advertentie voor in de plaats, en er
staat vaak alweer een plaatsing klaar in de wachtrij.

Dit script past dezelfde regel met terugwerkende kracht toe:

  Zoek elke verwijdering van de laatste 30 dagen die meldde dat de advertentie er
  al niet meer was ("already_absent"), terwijl die advertentie jonger was dan 28
  dagen. Dat kan geen verlopen advertentie zijn geweest.

Voor die artikelen:
  1. wachtende plaatsingen worden geannuleerd (anders komt er alsnog een nieuwe
     advertentie voor iets wat waarschijnlijk verkocht is);
  2. de nog levende advertentie op dat kanaal krijgt de status 'mogelijk
     verkocht', zodat de verkoper hem in het dashboard met één klik bevestigt —
     en het artikel dan ook van de andere kanalen af gaat.

Er wordt niets als verkocht geboekt en er wordt niets verwijderd. De verkoper
beslist.

Gebruik:
    python3 scripts/stop_herplaatslus.py                    # laat zien wat het zou doen
    python3 scripts/stop_herplaatslus.py --apply            # voer het uit
    python3 scripts/stop_herplaatslus.py --user <id>        # beperk tot één verkoper

Zonder --user raakt dit ook de advertenties van klanten. Dat is geen technische
grens maar een keuze: bij een klant verschijnt de vraag "is dit verkocht?" in
zíjn dashboard, en dat hoort niet ongevraagd te gebeuren. De gerepareerde code
stelt die vraag bij hen vanzelf zodra hun eerstvolgende herplaatsing erop stuit.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

TERUGKIJKEN_DAGEN = 30
KANALEN = ("marktplaats", "2dehands")


def main(apply: bool, alleen_user: str | None = None) -> None:
    from backend.database import get_db, fetch_all
    from backend.api.jobs import ZELF_VERLOPEN_NA_DAGEN, _verwijderdoelen
    from backend.api.listings import VERDENKING_REDENEN

    db = get_db()
    nu = datetime.now(timezone.utc)
    grens = (nu - timedelta(days=TERUGKIJKEN_DAGEN)).isoformat()

    verwijderingen = fetch_all(lambda: db.table("jobs")
                               .select("id,user_id,item_id,platform,payload,result,created_at")
                               .eq("action", "delete").eq("status", "done")
                               .gte("created_at", grens))
    verdacht: dict[tuple[str, str], dict] = {}
    for baan in verwijderingen or []:
        if baan["platform"] not in KANALEN:
            continue
        if alleen_user and baan["user_id"] != alleen_user:
            continue
        if ((baan.get("result") or {}).get("note")) != "already_absent":
            continue
        for rij in _verwijderdoelen(db, baan):
            geplaatst = rij.get("listed_at")
            if not geplaatst:
                continue
            try:
                leeftijd = datetime.fromisoformat(baan["created_at"]) - datetime.fromisoformat(geplaatst)
            except (TypeError, ValueError):
                continue
            if leeftijd < timedelta(days=ZELF_VERLOPEN_NA_DAGEN):
                verdacht[(baan["item_id"], baan["platform"])] = baan
                break

    if not verdacht:
        print("Niets gevonden — geen enkele verwijdering trof een te jonge, al verdwenen advertentie.")
        return

    print(f"{len(verdacht)} artikel/kanaal-combinatie(s) zaten in de lus:\n")
    reden = VERDENKING_REDENEN["verdwenen_te_jong"]
    for (item_id, platform), baan in sorted(verdacht.items()):
        item = (db.table("items").select("title").eq("id", item_id).limit(1).execute().data or [{}])[0]
        titel = (item.get("title") or "?")[:60]

        wachtend = (db.table("jobs").select("id")
                    .eq("item_id", item_id).eq("platform", platform)
                    .eq("action", "create").in_("status", ["pending", "claimed"])
                    .execute().data or [])
        levend = (db.table("listings").select("id,platform_listing_id,status,listed_at")
                  .eq("item_id", item_id).eq("platform", platform)
                  .in_("status", ["active", "relisting"]).execute().data or [])

        print(f"  {titel} — {platform}")
        print(f"      {len(wachtend)} wachtende plaatsing(en) → annuleren")
        for l in levend:
            print(f"      advertentie {l.get('platform_listing_id')} ({l['status']}) → 'mogelijk verkocht'")
        if not levend:
            print("      geen levende advertentie meer — alleen de wachtrij opruimen")

        if not apply:
            continue

        for j in wachtend:
            db.table("jobs").update({
                "status": "cancelled",
                "done_at": nu.isoformat(),
                "result": {"cancelled": (
                    "De oude advertentie was al van het platform af voordat wij hem weghaalden, "
                    "en daarvoor was hij te jong om vanzelf te verlopen. Bevestig eerst in het "
                    "dashboard of dit artikel verkocht is.")},
            }).eq("id", j["id"]).execute()
        for l in levend:
            db.table("listings").update({
                "status": "sold_unconfirmed",
                "error_message": reden,
                "last_checked": nu.isoformat(),
            }).eq("id", l["id"]).execute()

    print("\n" + ("Uitgevoerd." if apply else "Proefdraai — niets gewijzigd. Draai met --apply om het door te voeren."))


if __name__ == "__main__":
    argv = sys.argv[1:]
    user = argv[argv.index("--user") + 1] if "--user" in argv else None
    main("--apply" in argv, user)
