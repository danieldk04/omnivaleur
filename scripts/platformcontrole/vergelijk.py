#!/usr/bin/env python3
"""Hulp voor de platformcontrole: dagelijkse rubrieken kiezen en uitslagen met gisteren vergelijken.

  python3 scripts/platformcontrole/vergelijk.py rubrieken        # 3 Marktplaats-rubrieken van vandaag (roteert, dekt alles)
  python3 scripts/platformcontrole/vergelijk.py bewaar < uitslag.json
  python3 scripts/platformcontrole/vergelijk.py vergelijk        # vandaag tegenover de vorige bewaarde dag

uitslag.json: {"vinted kinderen schoenen": {"category": "ok", "size": "ok", ...}, "marktplaats boek": {...}}
Elke stap uit het log ("stap X: ok" of "NIET gelukt") komt erin, ook de bekende artefacten
(description, halswijdte): die horen elke dag hetzelfde uit te vallen; een verandering is een afwijking.
De map data/platformcontrole/ blijft buiten git.
"""
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP = ROOT / "data" / "platformcontrole"
FIXTURE = ROOT / "tests" / "fixtures" / "marktplaats_nieuwe_takken_24-09-2026.json"
PER_DAG = 3


def rubrieken(vandaag=None):
    lijst = sorted(json.loads(FIXTURE.read_text())["rubrieken"].items())
    dag = (vandaag or datetime.date.today()).toordinal()
    return [lijst[(dag * PER_DAG + i) % len(lijst)] for i in range(PER_DAG)]


def bewaar(uitslag, vandaag=None):
    MAP.mkdir(parents=True, exist_ok=True)
    pad = MAP / f"{(vandaag or datetime.date.today()).isoformat()}.json"
    pad.write_text(json.dumps(uitslag, indent=1, sort_keys=True))
    return pad


def verschil(nu, eerder):
    """Lijst met afwijkingen: een stap die anders uitvalt dan de vorige dag, of een artikel dat ontbreekt."""
    uit = []
    for artikel, stappen in nu.items():
        oud = eerder.get(artikel)
        if oud is None:
            uit.append(f"nieuw artikel in de proef: {artikel}")
            continue
        for stap, uitkomst in stappen.items():
            if oud.get(stap) != uitkomst:
                uit.append(f"{artikel}: stap {stap} was {oud.get(stap, 'afwezig')}, nu {uitkomst}")
        for stap in oud.keys() - stappen.keys():
            uit.append(f"{artikel}: stap {stap} komt niet meer voor")
    for artikel in eerder.keys() - nu.keys():
        uit.append(f"artikel niet meer getest: {artikel}")
    return uit


def vorige(voor):
    dagen = sorted(p for p in MAP.glob("*.json") if p.stem < voor.isoformat())
    return (dagen[-1].stem, json.loads(dagen[-1].read_text())) if dagen else (None, {})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "rubrieken":
        for naam, r in rubrieken():
            print(f"{naam}: /plaats/{r['cat1']}/{r['cat3']}?bucketId={r['bucketId']}&title=Proef")
    elif cmd == "bewaar":
        print(bewaar(json.load(sys.stdin)))
    elif cmd == "vergelijk":
        vandaag = datetime.date.today()
        nu = json.loads((MAP / f"{vandaag.isoformat()}.json").read_text())
        dag, eerder = vorige(vandaag)
        if not dag:
            print("geen eerdere dag om mee te vergelijken")
        else:
            d = verschil(nu, eerder)
            print(f"vergeleken met {dag}: " + ("geen verschil" if not d else ""))
            print("\n".join(d))
            sys.exit(1 if d else 0)
    else:
        print(__doc__)
