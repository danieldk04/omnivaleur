"""Advertenties terugzetten die wél verwijderd zijn maar als mislukking werden geboekt.

WAAROM DIT ER IS (15-09-2026, Henriette van Zilverwebsite)
Extensie 1.0.329 eiste na een verwijdering twee bevestigingen: de statuscode van
Marktplaats én een tekst op de gerenderde pagina. Die tekst werd gezocht als
"verlopen advertentie", terwijl Marktplaats "Deze advertentie is helaas verlopen"
schrijft (en 2dehands "Dit zoekertje is helaas verlopen"). Dus: server geeft HTTP
410, advertentie is echt weg, en de extensie boekt "mislukt". De bijbehorende
nieuwe plaatsing wordt dan overgeslagen om geen dubbele te maken, en het artikel
staat nergens meer — niet online en niet in de wachtrij.

Gemeten op 15-09-2026: 83 van de 83 verwijderingen die deze controle bereikten
zijn zo gesneuveld, verdeeld over vier verkopers.

Dit script raadt niets. Het pakt alleen opdrachten waarbij ALLEBEI waar is:
  1. de diagnostiek van de opdracht bevat een fetch-controle met HTTP 404 of 410
     (de server van het kanaal zei zelf dat de advertentie er niet meer is), en
  2. het advertentienummer staat niet meer in de OPENBARE advertentielijst van
     die verkoper (los bewijs, buiten onze eigen administratie om).

Pas dan wordt de verwijderopdracht gecorrigeerd naar 'done' en gaat de
advertentierij op 'relisting'. De gewone opruimronde (herstel_vastgelopen_werk)
zet er daarna een nette plaatsopdracht achteraan, in de juiste taal en met de
slottekst van de verkoper. Zonder de tweede controle zou een advertentie die tóch
nog live staat een dubbele krijgen — dat is de enige echt dure uitkomst hier.

Gebruik:
    python3 scripts/herstel_valse_verwijderfout.py              # alleen kijken
    python3 scripts/herstel_valse_verwijderfout.py --schrijf     # echt herstellen
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SINDS = "2026-09-14"            # 1.0.329 kwam op 15-09 in omloop
STATUS_IN_DIAG = re.compile(r'status\\?":\s*4(?:04|10)')


async def openbare_advertenties(platform: str, titels: list[str]) -> set[str] | None:
    """Alle advertentienummers die deze verkoper nu openbaar online heeft staan.

    None betekent: niet vast te stellen. Dan herstellen we niets — een lege
    uitkomst mag hier nooit als "alles is weg" gelezen worden.
    """
    import httpx
    from backend.services.mp_enrich import UA, ZOEK_PER_PLATFORM, PAGINA, MAX_PAGINAS, zoek_verkoper_id, _json

    zoek_url, _basis = ZOEK_PER_PLATFORM.get(platform, ZOEK_PER_PLATFORM["marktplaats"])
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
        vid = await zoek_verkoper_id(c, titels, zoek_url=zoek_url)
        if not vid:
            return None
        uit: set[str] = set()
        totaal = 0
        for p in range(MAX_PAGINAS):
            d = await _json(c, zoek_url, {"sellerIds[]": vid, "limit": PAGINA, "offset": p * PAGINA})
            rijen = d.get("listings") or []
            for r in rijen:
                if r.get("itemId"):
                    uit.add(r["itemId"])
            totaal = d.get("totalResultCount") or totaal
            if not rijen or len(uit) >= totaal:
                break
            await asyncio.sleep(0.8)
        if not uit:
            return None                      # lege lijst = meting mislukt, niet "alles weg"
        return uit


async def main(schrijf: bool) -> int:
    from dotenv import load_dotenv
    load_dotenv()
    from backend.database import get_admin_db
    db = get_admin_db()

    klussen = []
    off = 0
    while True:
        r = (db.table("jobs")
             .select("id,user_id,item_id,platform,status,created_at,result")
             .eq("action", "delete").eq("status", "error").gte("created_at", SINDS)
             .range(off, off + 999).execute().data or [])
        klussen += r
        if len(r) < 1000:
            break
        off += 1000

    kandidaten = [j for j in klussen
                  if "dom-tegencontrole" in json.dumps(j.get("result") or {})
                  and STATUS_IN_DIAG.search(json.dumps(j.get("result") or {}))]
    print(f"{len(klussen)} mislukte verwijderingen sinds {SINDS}; "
          f"{len(kandidaten)} daarvan kregen 404/410 van het kanaal zelf")
    if not kandidaten:
        return 0

    hersteld = 0
    per_verkoper: dict[tuple[str, str], list[dict]] = {}
    for j in kandidaten:
        per_verkoper.setdefault((j["user_id"], j["platform"]), []).append(j)

    for (uid, platform), groep in per_verkoper.items():
        # Titels van advertenties die het gewoon doen, om het verkopersnummer mee
        # te vinden. Nooit de titels van de kapotte groep: die staan er per
        # definitie niet meer, en dan levert het zoeken niets op.
        gezond = (db.table("listings")
                  .select("platform_listing_id,items!inner(title,user_id)")
                  .eq("platform", platform).eq("status", "active")
                  .eq("items.user_id", uid).limit(40).execute().data or [])
        stuk_ids = set()
        for j in groep:
            rij = (db.table("listings").select("id,platform_listing_id")
                   .eq("item_id", j["item_id"]).eq("platform", platform)
                   .limit(3).execute().data or [])
            for x in rij:
                stuk_ids.add(x.get("platform_listing_id"))
        titels = [g["items"]["title"] for g in gezond
                  if g.get("platform_listing_id") not in stuk_ids][:14]
        online = await openbare_advertenties(platform, titels) if titels else None
        if online is None:
            print(f"  {uid[:8]} {platform}: openbare lijst niet te lezen — "
                  f"{len(groep)} opdracht(en) met rust gelaten")
            continue
        print(f"  {uid[:8]} {platform}: {len(online)} advertenties openbaar online")

        for j in groep:
            rijen = (db.table("listings").select("id,platform_listing_id,status")
                     .eq("item_id", j["item_id"]).eq("platform", platform)
                     .in_("status", ["active", "relisting"]).limit(3).execute().data or [])
            if not rijen:
                continue
            rij = rijen[0]
            nummer = rij.get("platform_listing_id")
            if nummer in online:
                print(f"     OVERGESLAGEN {nummer}: staat nog gewoon online")
                continue
            if not schrijf:
                hersteld += 1
                continue
            oude = (j.get("result") or {}).get("error")
            db.table("jobs").update({
                "status": "done",
                "result": {
                    "note": "already_absent",
                    "correctie": ("15-09-2026: de verwijdering was gelukt (het kanaal gaf 404/410 "
                                  "en de advertentie staat niet meer in de openbare lijst van deze "
                                  "verkoper). Extensie 1.0.329 herkende de tekst op de verlopen "
                                  "pagina niet en boekte het als mislukt."),
                    "oorspronkelijke_fout": oude,
                },
            }).eq("id", j["id"]).eq("status", "error").execute()
            db.table("listings").update({
                "status": "relisting",
                "error_message": None,
            }).eq("id", rij["id"]).execute()
            hersteld += 1

    if not schrijf:
        print(f"\n{hersteld} advertentie(s) kunnen terug. "
              f"Draai opnieuw met --schrijf om het te doen.")
        return 0

    print(f"\n{hersteld} advertentie(s) gecorrigeerd en op 'relisting' gezet.")
    from backend.services.relist import herstel_vastgelopen_werk
    uitkomst = await herstel_vastgelopen_werk()
    print(f"Opruimronde: {uitkomst}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--schrijf", action="store_true")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main(a.schrijf)))
