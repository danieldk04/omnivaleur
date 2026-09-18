#!/usr/bin/env python3
"""Artikelen terughalen die "Merge into one" in een verkochte rij liet verdwijnen.

WAAROM (18-09-2026, Daniels eigen account dkresellacademy@gmail.com).

Een artikel dat opnieuw is ingekocht krijgt van de verkoper hetzelfde nummer:
"(987)". Het dashboard bood die nieuwe rij aan als dubbele rij naast de oude, al
maanden verkochte rij. "Merge into one" houdt de OUDSTE rij aan en verwijdert de
rest — dus verdween de nieuwe voorraad in de verkochte rij, kwam het artikel
onder "Sold" te staan en was het niet meer te publiceren.

De oorzaak is gerepareerd (backend/api/items.py en backend/api/jobs.py), maar de
verwijderde artikelen komen daar niet vanzelf van terug.

HOE DIT KAN. Elke publicatieopdracht draagt een volledige momentopname van het
artikel in `payload` — alle kolommen van de items-tabel, inclusief de foto's. Bij
het samenvoegen verhuizen de opdrachten mee naar de overgebleven rij, dus die
momentopname staat er nog. Daaruit bouwen we het artikel opnieuw op, met zijn
eigen id, zodat zijn opdrachten er weer bij horen.

WAT DIT SCRIPT NIET DOET. Alleen het schadelijke geval komt terug: een artikel
dat is aangemaakt NA de verkoop van de rij die het opslokte. Dat is per definitie
een ander voorwerp. Een gewone tweelingsamenvoeging (twee importrijen van één
trui) blijft samengevoegd — die hoort zo.

Zonder --apply verandert er niets; dan vertelt hij alleen wat hij zou doen.

Gebruik:
    python3 scripts/herstel_opgeslokte_artikelen.py --user <uuid>
    python3 scripts/herstel_opgeslokte_artikelen.py --user <uuid> --apply
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Velden die de opdracht meestuurt maar die geen kolom van items zijn.
GEEN_KOLOM = {"_taal"}


def _tijd(waarde):
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def _alle(db, tabel, kolommen, stap=200, **eq):
    """Serieel lezen in kleine brokken.

    Opdrachten dragen een volledige momentopname in `payload` plus een `result`;
    duizend van die rijen tegelijk opvragen liep op de echte database in een
    statement timeout (57014). Tweehonderd gaat goed.
    """
    uit, start = [], 0
    while True:
        q = db.table(tabel).select(kolommen)
        for k, v in eq.items():
            q = q.eq(k, v)
        rijen = q.order("created_at").range(start, start + stap - 1).execute().data or []
        uit += rijen
        if len(rijen) < stap:
            return uit
        start += stap


def main(user_id: str, apply: bool) -> None:
    from backend.database import get_db

    db = get_db()
    jobs = _alle(db, "jobs", "id,item_id,platform,action,status,created_at,payload,result",
                 user_id=user_id)
    print(f"{len(jobs)} opdrachten gelezen voor {user_id}")

    bestaande = {r["id"] for r in _alle(db, "items", "id", user_id=user_id)}

    # Opdrachten waarvan de momentopname een ANDER artikel noemt dan waar de
    # opdracht nu onder hangt: dat is het handschrift van een samenvoeging.
    slachtoffers: dict[str, dict] = {}
    for j in jobs:
        p = j.get("payload") if isinstance(j.get("payload"), dict) else {}
        pid = p.get("id")
        if not pid or pid == j.get("item_id") or pid in bestaande:
            continue
        s = slachtoffers.setdefault(pid, {"payload": p, "keep": j["item_id"], "jobs": []})
        s["jobs"].append(j)

    if not slachtoffers:
        print("Geen opgeslokte artikelen gevonden.")
        return

    print(f"{len(slachtoffers)} verdwenen artikel(en) gevonden; nu de schadelijke eruit.")

    keeps = sorted({s["keep"] for s in slachtoffers.values()})
    verkocht_van: dict[str, list[dict]] = {}
    for start in range(0, len(keeps), 100):
        brok = keeps[start:start + 100]
        for r in (db.table("listings")
                  .select("item_id,platform,status,sold_at,platform_listing_id")
                  .in_("item_id", brok).execute().data or []):
            verkocht_van.setdefault(r["item_id"], []).append(r)

    te_herstellen = []
    for pid, s in slachtoffers.items():
        gemaakt = _tijd((s["payload"] or {}).get("created_at"))
        titel = (s["payload"] or {}).get("title") or "?"

        # TWEE BEWIJZEN, EN ÉÉN IS GENOEG.
        #
        # 1. De verkoop-rem heeft dit artikel zelf tegengehouden omdat een rij
        #    met hetzelfde nummer al verkocht was. Dat is precies het geval:
        #    het systeem zag het als dubbel, hield het tegen, en daarna is het
        #    in die verkochte rij verdwenen.
        geremd = [j for j in s["jobs"]
                  if j.get("action") == "create" and j.get("status") == "cancelled"
                  and "already sold" in str(((j.get("result") or {})
                                             if isinstance(j.get("result"), dict) else {})
                                            .get("cancelled", "")).lower()]
        # 2. Of: de rij die het opslokte was al verkocht vóórdat dit artikel
        #    bestond. Dan is het per definitie een ander voorwerp.
        verkopen = [r for r in verkocht_van.get(s["keep"], []) if r["status"] == "sold"]
        na_de_verkoop = [r for r in verkopen
                         if gemaakt and _tijd(r.get("sold_at"))
                         and gemaakt > _tijd(r["sold_at"])]

        if not geremd and not na_de_verkoop:
            print(f"  overslaan  {pid[:8]}  {titel[:50]!r} — gewone tweeling, blijft samengevoegd")
            continue
        reden = ("de verkoop-rem hield dit artikel zelf tegen" if geremd else
                 "de opslokkende rij was al verkocht: "
                 + ", ".join(sorted({r["platform"] for r in na_de_verkoop})))
        print(f"  HERSTELLEN {pid[:8]}  {titel[:50]!r}")
        print(f"               aangemaakt {gemaakt}, opgeslokt door {s['keep'][:8]} — {reden}")
        te_herstellen.append((pid, s))

    if not te_herstellen:
        print("Niets schadelijks gevonden.")
        return

    # Dode wachtrijen: rijen die het publiceren klaarzette en die daarna zijn
    # geannuleerd of mislukt. Zonder advertentienummer hebben ze nooit een
    # advertentie gehad; ze laten het dashboard eeuwig "Publishing…" zeggen.
    dood = []
    for pid, s in te_herstellen:
        for r in verkocht_van.get(s["keep"], []):
            if r["status"] != "pending" or r.get("platform_listing_id"):
                continue
            laatste = [j for j in s["jobs"] if j["platform"] == r["platform"]]
            if laatste and all(j["status"] in ("cancelled", "error") for j in laatste):
                dood.append((s["keep"], r["platform"]))
    if dood:
        print(f"\n{len(dood)} vastgelopen 'Publishing…'-rij(en) worden opgeruimd: "
              + ", ".join(f"{k[:8]}/{p}" for k, p in dood))

    if not apply:
        print("\nProefronde. Draai met --apply om dit echt te doen.")
        return

    for pid, s in te_herstellen:
        rij = {k: v for k, v in (s["payload"] or {}).items() if k not in GEEN_KOLOM}
        rij["id"] = pid
        rij["user_id"] = user_id
        db.table("items").insert(rij).execute()
        for j in s["jobs"]:
            db.table("jobs").update({"item_id": pid}).eq("id", j["id"]).execute()
        print(f"terug: {pid[:8]} {rij.get('title')!r} ({len(s['jobs'])} opdracht(en) mee)")

    for keep, platform in dood:
        db.table("listings").delete().eq("item_id", keep).eq("platform", platform) \
          .eq("status", "pending").is_("platform_listing_id", "null").execute()
        print(f"opgeruimd: wachtende {platform}-rij van {keep[:8]}")

    print("\nKlaar.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    main(a.user, a.apply)
