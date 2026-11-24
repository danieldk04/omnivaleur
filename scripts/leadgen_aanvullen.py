#!/usr/bin/env python3
"""Vult de wachtrij van de koude mail aan zodra hij dun wordt (24-11-2026).

Waarom: de wachtrij liep leeg op 02-10, 20-10, 19-11 en 24-11 en elke keer stond de
koude mail dagen stil. Dit script meet de wachtrij en haalt alleen bij te weinig
leads nieuwe op: Marktplaats en 2dehands (zoeken, profielen, beoordelen via de
Claude-opdrachtregel, naar de sheet), en voegt ze daarna SAMEN met de lijst in
Supabase (nooit `leadgen_mail.py overzetten`: dat overschrijft).

Gebruik (vanaf de repo-map, met .env en ~/.omnivaleur/sheets-sleutel.json):
    python3 scripts/leadgen_aanvullen.py            # alleen als de wachtrij < 40 is
    python3 scripts/leadgen_aanvullen.py --altijd   # nu, ook bij volle wachtrij
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))
DREMPEL = 40


def _env() -> None:
    for regel in (REPO / ".env").read_text().splitlines():
        if "=" in regel and not regel.lstrip().startswith("#"):
            k, _, v = regel.partition("=")
            if k.strip().isidentifier():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    os.environ["SUPABASE_KEY"] = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    sleutel = Path.home() / ".omnivaleur" / "sheets-sleutel.json"
    os.environ["GOOGLE_SHEETS_SLEUTEL"] = sleutel.read_text()


def _stap(*args: str) -> None:
    print("→", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=REPO, check=False)


def main() -> None:
    _env()
    import leadgen_mail as lm

    st = lm._db_lees("mail_state", {}) or {}
    wacht = len(lm._wachtrij(st, 10 ** 6))
    print(f"wachtrij: {wacht}")
    if wacht >= DREMPEL and "--altijd" not in sys.argv:
        print("genoeg leads, niets te doen")
        return

    for site in ("marktplaats", "2dehands"):
        _stap("scripts/leadgen_marktplaats.py", "discover", "--site", site)
        _stap("scripts/leadgen_marktplaats.py", "enrich", "--site", site)
        _stap("scripts/leadgen_marktplaats.py", "crosslist", "--site", site)
        _stap("scripts/leadgen_classify_cli.py", "classify", "--only-email",
              "--min-ads", "10", "--site", site)
        _stap("scripts/leadgen_marktplaats.py", "push", "--site", site)

    mp = lm._db_lees("mp_leads", []) or []
    dh = lm._db_lees("2dh_leads", []) or []
    ex = lm._db_lees("extra_leads", []) or []
    bekend = {(l.get("email") or "").lower() for l in mp + dh + ex} | {k.lower() for k in st}
    nieuw_mp = [l for l in json.loads(lm.MP_LEADS.read_text())
                if (l.get("email") or "").lower() not in bekend]
    bekend |= {(l.get("email") or "").lower() for l in nieuw_mp}
    nieuw_dh = [l for l in json.loads(lm.TWEEDEHANDS_LEADS.read_text())
                if (l.get("email") or "").lower() not in bekend]
    if nieuw_mp:
        lm._db_schrijf("mp_leads", mp + nieuw_mp)
    if nieuw_dh:
        lm._db_schrijf("2dh_leads", dh + nieuw_dh)
    wacht = len(lm._wachtrij(lm._db_lees("mail_state", {}) or {}, 10 ** 6))
    print(f"nieuw: {len(nieuw_mp)} Marktplaats, {len(nieuw_dh)} 2dehands; wachtrij nu {wacht}")


if __name__ == "__main__":
    main()
