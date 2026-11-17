#!/usr/bin/env python3
"""Hoe snel komt een nieuwe klant van aanmelding tot een echte advertentie online?

De meting zelf staat in backend/services/onboarding_tempo.py (daar leest ook de
zondagsmail uit). Dit is het handmatige gezicht ervan, met uitleg van de groepen en
eerlijkheidsregels in die module.

GEBRUIK
    python3.13 scripts/onboarding_tempo.py                 # laatste 90 dagen
    python3.13 scripts/onboarding_tempo.py --dagen 30
    python3.13 scripts/onboarding_tempo.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
import mail_analyse as A  # noqa: E402
from backend.services.onboarding_tempo import PUNTEN, meet  # noqa: E402


def _regel(naam, s):
    if not s["klanten"]:
        return f"{naam}: geen klanten"
    w = "  (WEINIG KLANTEN, richting)" if s["waarschuwing"] else ""
    uit = [f"{naam}: {s['klanten']} klanten{w}"]
    for p in PUNTEN:
        x = s[p]
        b = "  ".join(
            f"binnen {u}: {v['aantal']}/{v['van']}" + (f" ({v['pct']}%)" if v["pct"] is not None else "")
            for u, v in x["binnen"].items())
        med = f"{x['mediaan_uur']} u" if x["mediaan_uur"] is not None else "nog niemand"
        uit.append(f"   {p:16} bereikt {x['bereikt']}/{s['klanten']}, mediaan {med}   {b}")
    return "\n".join(uit)


def main():
    A._omgeving_uit_env_bestand()
    ap = argparse.ArgumentParser(description="Tijd van aanmelding tot eerste live advertentie.")
    ap.add_argument("--dagen", type=int, default=90)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = meet(args.dagen)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    print(f"Wijziging live: {r['wijziging_op']}")
    print(_regel("VOOR de wijziging", r["voor"]))
    print(_regel("NA de wijziging", r["na"]))
    print("\nPer aanmeldweek (maandag):")
    for w, s in r["per_week"].items():
        print(_regel(w, s))


if __name__ == "__main__":
    main()
