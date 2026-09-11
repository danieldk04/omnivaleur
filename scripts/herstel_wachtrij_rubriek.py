"""Wachtende Marktplaats/2dehands-opdrachten alsnog de ECHTE rubriek meegeven.

WAAROM DIT BESTAAT (11-09-2026, Egbert Brouwer / Papa's Plectrums).

Sinds vandaag zoekt het publiceerpad vóór het klaarzetten van een opdracht op in
welke categorie de advertentie van de verkoper zelf staat, en zet die als
`mp_category` in de opdracht (zie `rubriek_van_de_bronadvertentie` in
backend/services/crosslist.py). Dat werkt voor élke nieuwe opdracht.

Maar een opdracht die AL in de wachtrij stond draagt nog de kopie van het moment
van klikken, en `get_pending_jobs` ververst bewust alleen condition, brand, size,
color en material — niet de categorie (zie de kennisbank,
"wachtrij-draagt-een-oude-kopie"). Zonder deze ronde zou de verkoper dus ALSNOG
moeten wachten tot die oude opdrachten stuk voor stuk in de verkeerde, soms
betalende rubriek stranden, of alles met de hand opnieuw moeten publiceren.

Dit script haalt dat in:

  1. per wachtende `create`-opdracht voor Marktplaats/2dehands zonder
     `mp_category` wordt de echte rubriek opgezocht en in de opdracht gezet;
  2. daarna wordt alles teruggenomen wat in een rubriek staat die bij DEZE
     verkoper al eens om geld heeft gevraagd — dezelfde rem als op de server
     (`_stop_wachtrij(..., rubriek=)`), maar dan vóór de eerste mislukking.

VEILIGHEID:
  - standaard een DROGE PROEF; pas met --schrijf verandert er iets;
  - het vult alleen wat leeg is: een opdracht die al een `mp_category` draagt
    blijft met rust;
  - het raakt alleen `pending`-opdrachten; wat al loopt of klaar is blijft;
  - lukt het opzoeken niet, dan blijft die opdracht onveranderd — precies zoals
    het publiceerpad zelf: een gemiste categorie mag nooit een advertentie kosten.

Gebruik:
    python3 scripts/herstel_wachtrij_rubriek.py --user <uuid>
    python3 scripts/herstel_wachtrij_rubriek.py --user <uuid> --schrijf
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_db  # noqa: E402

KANALEN = ("marktplaats", "2dehands")
# Niet honderden tegelijk: elke opzoeking is een verzoek aan Marktplaats, en dat
# throttelt. Vijf tegelijk is snel zat en blijft beleefd.
TEGELIJK = 5


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="user_id van de verkoper")
    ap.add_argument("--schrijf", action="store_true", help="echt doorvoeren")
    ap.add_argument("--max", type=int, default=0, help="hooguit zoveel opdrachten")
    args = ap.parse_args()

    from backend.api.jobs import (betaalde_rubrieken, rubriek_sleutel,
                                  _melding_rubriek_vraagt_geld, _stop_wachtrij)
    from backend.services.crosslist import rubriek_van_de_bronadvertentie

    db = get_db()
    opdrachten = (db.table("jobs").select("id,item_id,platform,payload")
                  .eq("user_id", args.user).eq("status", "pending")
                  .eq("action", "create").in_("platform", list(KANALEN))
                  .limit(args.max or 5000).execute().data or [])
    teVullen = [j for j in opdrachten if not (j.get("payload") or {}).get("mp_category")]
    print(f"{len(opdrachten)} wachtende opdrachten, {len(teVullen)} zonder echte rubriek")
    if not teVullen:
        print("Niets te vullen.")

    # De artikelen erbij: het opzoeken heeft titel en id nodig.
    item_ids = sorted({j["item_id"] for j in teVullen if j.get("item_id")})
    artikelen: dict[str, dict] = {}
    for i in range(0, len(item_ids), 200):
        rijen = (db.table("items").select("id,title")
                 .in_("id", item_ids[i:i + 200]).execute().data or [])
        artikelen.update({r["id"]: r for r in rijen})

    poort = asyncio.Semaphore(TEGELIJK)
    gevuld = leeg = 0

    async def een(job: dict) -> None:
        nonlocal gevuld, leeg
        item = artikelen.get(job.get("item_id") or "")
        if not item:
            return
        async with poort:
            try:
                rubriek = await rubriek_van_de_bronadvertentie(db, item, args.user)
            except Exception as e:  # noqa: BLE001
                print(f"  ! {job['id'][:8]} opzoeken mislukt: {e}")
                return
        if not rubriek:
            leeg += 1
            return
        gevuld += 1
        naam = rubriek.get("l2_naam") or f"{rubriek.get('l1')}/{rubriek.get('l2')}"
        oud = (job.get("payload") or {}).get("category") or "(geen)"
        print(f"  {job['platform']:11} {item.get('title', '')[:44]:44} {oud} -> {naam}")
        if args.schrijf:
            payload = {**(job.get("payload") or {}), "mp_category": rubriek}
            db.table("jobs").update({"payload": payload}).eq("id", job["id"]).execute()

    for i in range(0, len(teVullen), 50):
        await asyncio.gather(*(een(j) for j in teVullen[i:i + 50]))

    print(f"\n{gevuld} opdrachten krijgen hun echte rubriek, "
          f"{leeg} konden niet opgezocht worden (die blijven zoals ze waren)")

    # ── En nu de rem: wat staat er nog in een rubriek die geld vraagt? ──────
    for platform in KANALEN:
        duur = betaalde_rubrieken(db, args.user, platform)
        if not duur:
            continue
        wachtend = (db.table("jobs").select("id,payload")
                    .eq("user_id", args.user).eq("platform", platform)
                    .eq("status", "pending").limit(5000).execute().data or [])
        for sleutel, naam in duur.items():
            raak = [j for j in wachtend if rubriek_sleutel(j.get("payload")) == sleutel]
            if not raak:
                continue
            print(f"\n{platform}: {len(raak)} opdrachten staan in {naam!r}, "
                  f"en die rubriek vroeg hier al eens om geld")
            if args.schrijf:
                aantal = _stop_wachtrij(db, args.user, platform,
                                        _melding_rubriek_vraagt_geld(platform, naam),
                                        rubriek=sleutel)
                print(f"  {aantal} teruggenomen")

    if not args.schrijf:
        print("\nDROGE PROEF — er is niets gewijzigd. Draai opnieuw met --schrijf.")


if __name__ == "__main__":
    asyncio.run(main())
