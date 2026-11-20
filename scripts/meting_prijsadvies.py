"""Backtest van prijsadvies uit eigen verkopen (alleen lezen). 20-11-2026.

Voor elk verkocht artikel met bekende verkoopprijs: voorspel de verkoopprijs uit de
ANDERE verkochte artikelen van dezelfde klant (leave-one-out) en vergelijk met wat het
werkelijk opbracht. Variant 'markt': ook artikelen van andere klanten (alleen om te
meten hoeveel dat zou uitmaken; gebruik ervan is een privacybesluit van Daniel).

Uitvoer: dekking (hoe vaak er een advies komt) en nauwkeurigheid (binnen 20%/30%)
tegen twee vergelijkingen: de vraagprijs zelf en de mediaan van de klant.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db, fetch_all, fetch_all_in  # noqa: E402

STOP = set("de het een en van met in op voor maat size nieuw new the and of to a vintage dames heren kinderen".split())


def woorden(t):
    return {w for w in re.findall(r"[^\W_]{3,}", (t or "").lower()) if w not in STOP and not w.isdigit()}


def laad():
    db = get_db()
    sold = fetch_all(lambda: db.table("listings").select("id,item_id,platform,sold_price,status")
                     .eq("status", "sold").not_.is_("sold_price", "null"))
    ids = list({s["item_id"] for s in sold})
    items = {i["id"]: i for i in fetch_all_in(
        lambda: db.table("items").select("id,user_id,title,brand,category,price,condition,purchase_price"),
        "id", ids)}
    rijen = []
    for s in sold:
        it = items.get(s["item_id"])
        try:
            p = float(s["sold_price"])
        except (TypeError, ValueError):
            continue
        if it and p > 0:
            rijen.append({"id": s["item_id"], "user": it["user_id"], "platform": s["platform"], "titel": it["title"],
                          "w": woorden(it["title"]), "cat": it.get("category"), "merk": (it.get("brand") or "").lower(),
                          "vraag": float(it["price"] or 0), "echt": p})
    # een artikel kan op twee kanalen verkocht zijn: een rij per artikel
    uniek = {}
    for r in rijen:
        uniek.setdefault(r["id"], r)
    return list(uniek.values())


def jacc(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def voorspel(r, pool, k=5, min_sim=0.25):
    cand = [(jacc(r["w"], o["w"]) + (0.15 if r["cat"] and r["cat"] == o["cat"] else 0)
             + (0.15 if r["merk"] and r["merk"] == o["merk"] else 0), o) for o in pool if o["id"] != r["id"]]
    cand = [(s, o) for s, o in cand if s >= min_sim]
    if len(cand) < 2:
        return None
    cand.sort(key=lambda x: -x[0])
    return statistics.median(o["echt"] for _, o in cand[:k])


def binnen(v, echt, f):
    return abs(v - echt) <= f * echt


def main():
    rijen = laad()
    per_user = defaultdict(list)
    for r in rijen:
        per_user[r["user"]].append(r)
    print("verkochte artikelen met prijs:", len(rijen), "bij", len(per_user), "klanten")
    uit = {}
    for naam, kies in (("eigen", lambda r: per_user[r["user"]]), ("markt", lambda r: rijen)):
        n = dek = b20 = b30 = 0
        mediaan_b20 = vraag_b20 = vraag_n = 0
        for r in rijen:
            pool = kies(r)
            if naam == "eigen" and len(pool) < 8:
                continue
            n += 1
            v = voorspel(r, pool)
            med = statistics.median(o["echt"] for o in pool if o["id"] != r["id"])
            mediaan_b20 += binnen(med, r["echt"], .2)
            if r["vraag"] > 0:
                vraag_n += 1
                vraag_b20 += binnen(r["vraag"], r["echt"], .2)
            if v is not None:
                dek += 1
                b20 += binnen(v, r["echt"], .2)
                b30 += binnen(v, r["echt"], .3)
        uit[naam] = {"artikelen": n, "advies_komt": dek, "dekking": round(dek / max(n, 1), 3),
                     "binnen20": round(b20 / max(dek, 1), 3), "binnen30": round(b30 / max(dek, 1), 3),
                     "klantmediaan_binnen20": round(mediaan_b20 / max(n, 1), 3),
                     "vraagprijs_binnen20": round(vraag_b20 / max(vraag_n, 1), 3)}
        print(naam, uit[naam])
    # hoe ver ligt verkocht van vraagprijs? (voor 'verlaag je prijs'-advies)
    ratio = [r["echt"] / r["vraag"] for r in rijen if r["vraag"] > 0]
    print("verkocht/vraag mediaan", round(statistics.median(ratio), 3),
          "binnen 10%:", round(sum(abs(x - 1) <= .1 for x in ratio) / len(ratio), 3))
    Path.home().joinpath(".omnivaleur/meting_ai/prijsadvies.json").write_text(json.dumps(uit, indent=1))


if __name__ == "__main__":
    main()
