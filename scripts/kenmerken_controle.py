#!/usr/bin/env python3
"""Gelukte plaatsingen met een verkeerde of lege waarde (kleur, maat).

WAAROM (02-11-2026, Mieneke): "Silver" werd stil "Grijs" en de ringmaat bleef leeg,
terwijl elke plaatsing 'done' was. De klantfoutenronde kijkt alleen naar status
'error' en zag het dus nooit. Dit script kijkt naar de opdracht zelf: wat zou er
ingevuld moeten zijn, en klopt dat met wat onze eigen vertaling ervan maakt.

Meet alleen create-opdrachten met status done van de laatste N uur, per klant, op
payload (nooit result, zie kennisbank: meten-op-de-productiedatabase).

    python3.13 scripts/kenmerken_controle.py [uren]      # standaard 24
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db  # noqa: E402
from backend.services.kleur import normaliseer_kleur  # noqa: E402

# Wie "silver" schrijft moet "Zilver" krijgen, nooit een buurkleur.
VERWACHT = (("zilver", "silver", "Zilver"), ("goud", "gold", "Goud"))
MAAT_IN_TEKST = re.compile(r"\b(?:ring)?maat\s*(?:is|=|:|nu|ca\.?|circa)?\s*\d", re.I)


def beoordeel(p: dict) -> list[str]:
    uit = []
    kleur = str(p.get("color") or "").strip()
    if kleur:
        laag = kleur.lower()
        nl = normaliseer_kleur(kleur)
        for nl_woord, en_woord, goed in VERWACHT:
            if (nl_woord in laag or en_woord in laag) and str(nl or "").lower() != goed.lower():
                uit.append(f"kleur_verschuift ({kleur} wordt {nl})")
    if not str(p.get("size") or "").strip():
        tekst = f"{p.get('title') or ''} {p.get('description') or ''}"
        if MAAT_IN_TEKST.search(tekst):
            uit.append("maat_leeg_maar_in_tekst")
    return uit


def main() -> int:
    uren = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    grens = (datetime.now(timezone.utc) - timedelta(hours=uren)).isoformat()
    db = get_db()
    users: set[str] = set()
    for off in range(0, 20000, 1000):
        b = (db.table("jobs").select("user_id").eq("action", "create").eq("status", "done")
             .gte("created_at", grens).range(off, off + 999).execute().data)
        users |= {x["user_id"] for x in b}
        if len(b) < 1000:
            break
    if not users:
        print(f"LET OP: 0 klanten met gelukte plaatsingen in {uren} uur. Controleer eerst of de meting klopt.")
        return 1
    totaal = Counter()
    per_klant: dict[str, Counter] = defaultdict(Counter)
    voorbeeld: dict[str, str] = {}
    n = 0
    for uid in sorted(users):
        for off in range(0, 5000, 500):
            rijen = (db.table("jobs").select("payload").eq("user_id", uid).eq("action", "create")
                     .eq("status", "done").gte("created_at", grens).range(off, off + 499).execute().data)
            for r in rijen:
                p = r.get("payload") or {}
                n += 1
                for fout in beoordeel(p):
                    soort = fout.split(" (")[0]
                    totaal[soort] += 1
                    per_klant[uid][fout] += 1
                    voorbeeld.setdefault(f"{uid[:8]} {fout}", str(p.get("title") or "")[:60])
            if len(rijen) < 500:
                break
    print(f"{n} gelukte plaatsingen bij {len(users)} klanten in {uren} uur.")
    if not totaal:
        print("Geen verdachte kleur of maat gevonden.")
    for uid, c in per_klant.items():
        for fout, k in c.most_common():
            print(f"  {uid[:8]}  {k:4d}x  {fout}   bv. {voorbeeld.get(f'{uid[:8]} {fout}', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
