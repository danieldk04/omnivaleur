#!/usr/bin/env python3
"""Zet zoekertjes terug in de rij die ten onrechte op "betalende rubriek" sneuvelden.

WAT ER MIS WAS (14-09-2026, Egbert Brouwer / Papa's Plectrums)

Hij zette om 17:04 vijftig artikelen klaar voor 2dehands. Binnen een minuut waren
ze alle vijftig geannuleerd met "2dehands charges for adverts in Muziek
snaarinstrumenten gitaren". De dag ervoor lukte precies dezelfde ronde 127 keer
achter elkaar wel.

De oorzaak zat niet bij 2dehands. Vlak voor uitgifte halen we bij Marktplaats de
rubriek op die hij daar zelf koos (Verzamelen | Muziek, Artiesten en
Beroemdheden, gratis op 2dehands). Die opzoeking gaf die minuut geen antwoord, en
"geen antwoord" werd gelezen als "dit artikel staat niet op Marktplaats". Daarna
gold de uit de titel geraden rubriek — gitaren, en die kost op 2dehands geld.

De code is gerepareerd, maar de vijftig opdrachten staan op "cancelled" en de
vijftig advertentierijen op "error" met een melding die niet klopt. Zonder deze
ronde blijft dat staan tot hij ze met de hand opnieuw aanklikt.

Lezen is gratis, schrijven alleen met --apply:
    python3 scripts/herstel_betalende_rubriek.py
    python3 scripts/herstel_betalende_rubriek.py --apply
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

EGBERT = "bcdf9aa4-314d-49a2-9573-8818ad61073d"


async def _rubrieken(db, user_id: str, werk: list[dict]) -> dict:
    """De echte Marktplaats-rubriek per artikel. Netjes één voor één."""
    import httpx
    from backend.services import mp_enrich as M

    gevonden: dict[str, dict] = {}
    zoek_url, _ = M.ZOEK_PER_PLATFORM["marktplaats"]
    async with httpx.AsyncClient(timeout=25, follow_redirects=True,
                                 headers={"User-Agent": M.UA}) as client:
        verkoper = await M._verkopersnummer(db, user_id, "marktplaats", client, zoek_url)
        if not verkoper:
            print("verkopersnummer op Marktplaats niet gevonden — niets te doen")
            return gevonden
        print(f"verkopersnummer: {verkoper}")
        for w in werk:
            rubriek = await M.rubriek_op_advertentienummer(
                client, verkoper, w["titel"], w["nummer"], zoek_url)
            if rubriek:
                gevonden[w["item_id"]] = rubriek
            else:
                print(f"  geen rubriek: {w['titel'][:50]} ({w['nummer']})")
            await asyncio.sleep(0.4)
    return gevonden


def main(apply: bool, user_id: str, dagen: int, gestopt: bool = False) -> None:
    from backend.database import get_db
    from backend.api.jobs import _BETAALDE_RUBRIEK

    db = get_db()
    grens = (datetime.now(timezone.utc) - timedelta(days=dagen)).isoformat()
    jobs = (db.table("jobs").select("id,item_id,payload,status,result,created_at")
            .eq("user_id", user_id).eq("platform", "2dehands").eq("action", "create")
            .in_("status", ["cancelled", "error"]).gte("created_at", grens)
            .order("created_at", desc=True).limit(1000).execute().data or [])
    # Alleen wat op de betalende rubriek sneuvelde, en alleen als er geen echte
    # rubriek in stond: met een eigen Marktplaats-rubriek was het geen vergissing.
    sneuvelde, hervat = [], []
    for j in jobs:
        res = j.get("result") if isinstance(j.get("result"), dict) else {}
        tekst = f"{res.get('error') or ''} {res.get('error_oorspronkelijk') or ''}"
        pl = j.get("payload") if isinstance(j.get("payload"), dict) else {}
        if _BETAALDE_RUBRIEK.search(tekst) and not pl.get("mp_category"):
            sneuvelde.append(j)
        elif gestopt and pl.get("mp_category") and res.get("cancelled") == "queue stopped":
            # Al een keer teruggezet, en daarna meegesleept toen het hele kanaal
            # werd stilgezet. De rubriek staat er al in, dus hier hoeft niets
            # opgezocht te worden: gewoon terug in de rij.
            hervat.append(j)
    print(f"opdrachten die op een betalende rubriek sneuvelden: {len(sneuvelde)}")
    if hervat:
        print(f"opdrachten die daarna met het hele kanaal zijn stilgezet: {len(hervat)}")
        if apply:
            terug = 0
            for j in hervat:
                db.table("jobs").update({
                    "status": "pending", "result": None, "done_at": None, "claimed_at": None,
                }).eq("id", j["id"]).execute()
                db.table("listings").update({"status": "pending", "error_message": None}).eq(
                    "item_id", j["item_id"]).eq("platform", "2dehands").execute()
                terug += 1
            print(f"  hervat: {terug}")
    if not sneuvelde:
        return

    ids = sorted({j["item_id"] for j in sneuvelde if j.get("item_id")})
    op_mp, al_bezig, al_online = {}, set(), set()
    for i in range(0, len(ids), 200):
        brok = ids[i:i + 200]
        for r in (db.table("listings").select("item_id,platform_listing_id,items(title)")
                  .in_("item_id", brok).eq("platform", "marktplaats").eq("status", "active")
                  .not_.is_("platform_listing_id", "null").execute().data or []):
            op_mp[r["item_id"]] = (r["platform_listing_id"], (r.get("items") or {}).get("title") or "")
        for r in (db.table("listings").select("item_id,status")
                  .in_("item_id", brok).eq("platform", "2dehands").execute().data or []):
            if r["status"] == "active":
                al_online.add(r["item_id"])
        for r in (db.table("jobs").select("item_id")
                  .eq("user_id", user_id).eq("platform", "2dehands").eq("action", "create")
                  .in_("item_id", brok).in_("status", ["pending", "claimed"])
                  .execute().data or []):
            al_bezig.add(r["item_id"])

    werk, over = [], []
    for j in sneuvelde:
        it = j.get("item_id")
        if it in al_online:
            over.append((j, "staat al op 2dehands"))
        elif it in al_bezig:
            over.append((j, "er staat al een opdracht klaar"))
        elif it not in op_mp:
            over.append((j, "geen actieve Marktplaats-advertentie"))
        else:
            nummer, titel = op_mp[it]
            werk.append({"job": j, "item_id": it, "nummer": nummer,
                         "titel": titel or (j["payload"] or {}).get("title") or ""})
    for j, reden in over:
        print(f"  overgeslagen ({reden}): {(j.get('payload') or {}).get('title', '')[:50]}")
    print(f"op te halen rubrieken: {len(werk)}")
    if not werk:
        return

    gevonden = asyncio.run(_rubrieken(db, user_id, werk))
    print(f"rubriek gevonden voor {len(gevonden)} van de {len(werk)}")

    # Een echte rubriek die zelf ook geld bleek te kosten, zetten we niet terug:
    # dan zou dezelfde melding gewoon opnieuw komen. Zie _betaalde_rubriek_bekend.
    from backend.api.jobs import _betaalde_rubriek_bekend
    duur = set()
    for sleutel in {f"mp:{r['l1']}/{r['l2']}" for r in gevonden.values()}:
        if _betaalde_rubriek_bekend(db, user_id, "2dehands", sleutel):
            duur.add(sleutel)
    if duur:
        print(f"rubrieken die zelf ook geld kosten, blijven staan: {sorted(duur)}")
    gevonden = {k: r for k, r in gevonden.items() if f"mp:{r['l1']}/{r['l2']}" not in duur}
    print(f"terug te zetten: {len(gevonden)}")
    if not apply:
        for w in werk[:5]:
            r = gevonden.get(w["item_id"])
            print(f"  ZOU terugzetten: {w['titel'][:50]} -> {r.get('l1_naam') if r else '-'} | "
                  f"{r.get('l2_naam') if r else '-'}")
        print("\nProefronde. Draai met --apply om het echt te doen.")
        return

    terug = 0
    for w in werk:
        rubriek = gevonden.get(w["item_id"])
        if not rubriek:
            continue
        j = w["job"]
        pl = dict(j.get("payload") or {})
        pl["mp_category"] = rubriek
        pl.pop("_rubriek_niet_op_marktplaats", None)
        pl.pop("_rubriek_zoeken_sinds", None)
        db.table("jobs").update({
            "payload": pl, "status": "pending", "result": None,
            "done_at": None, "claimed_at": None,
        }).eq("id", j["id"]).execute()
        db.table("listings").update({"status": "pending", "error_message": None}).eq(
            "item_id", w["item_id"]).eq("platform", "2dehands").execute()
        terug += 1
    print(f"teruggezet in de wachtrij: {terug}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--user", default=EGBERT)
    p.add_argument("--dagen", type=int, default=7)
    p.add_argument("--gestopte-wachtrij", action="store_true",
                   help="ook opdrachten hervatten die met het hele kanaal zijn stilgezet")
    a = p.parse_args()
    main(a.apply, a.user, a.dagen, a.gestopte_wachtrij)
