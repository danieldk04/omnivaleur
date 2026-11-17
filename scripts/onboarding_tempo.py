#!/usr/bin/env python3
"""Hoe snel komt een nieuwe klant van aanmelding tot een echte advertentie online?

WAAROM DIT BESTAAT (17-11-2026)
Op 16-11-2026 is de onboarding versneld (inlezen start vanzelf, snelle import, eerste
plaatsing met een knop). Of dat werkt weet je pas als je de tijd van aanmelding tot
eerste live advertentie voor en na die wijziging naast elkaar legt. Dit script doet
dat, elke keer opnieuw, uit de tijdstempels die er al zijn. Er wordt niets bijgehouden
dat kan zoekraken: draai het op elk moment en je krijgt dezelfde uitkomst.

MEETPUNTEN (per klant, vanaf aanmelding)
  1. eerste_opdracht : eerste gelukte opdracht van welke soort ook (de extensie draait)
  2. eerste_artikel  : eerste artikel in de voorraad (inlezen is begonnen)
  3. eerste_live     : eerste gelukte plaatsing (action create, status done)

GROEPEN
  voor  = aangemeld vóór de wijziging (VOOR_TOT)
  na    = aangemeld erna
  en per aanmeldweek, zodat een trend zichtbaar is.

EERLIJKHEID OVER DE CIJFERS
- Een klant van 3 uur oud kan nog niet "binnen 24 uur live" zijn. Percentages binnen X
  uur tellen daarom alleen klanten die minstens X uur oud zijn.
- De mediaan telt alleen klanten die het punt bereikten. Daarom staat "bereikt" erbij:
  een mediaan van 2 uur bij 10% bereikt zegt weinig.
- Eigen en test-accounts (omnivaleur.com, crosslisteu.com) en onbevestigde aanmeldingen
  tellen niet mee.
- Kleine groepen (minder dan 10 klanten) krijgen een waarschuwing; die cijfers zijn
  richting, geen bewijs.

LICHT OP DE DATABASE: alles per user_id, 1 rij per vraag (kennisbank, meten-op-de-productiedatabase).

GEBRUIK
    python3 scripts/onboarding_tempo.py                 # laatste 90 dagen
    python3 scripts/onboarding_tempo.py --dagen 30
    python3 scripts/onboarding_tempo.py --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mail_analyse as A  # noqa: E402

# Commit 344e3893, "inlezen start vanzelf", 16-11-2026 15:51 NL = 14:51 UTC.
VOOR_TOT = datetime(2026, 11, 16, 14, 51, tzinfo=timezone.utc)
EIGEN_DOMEINEN = ("omnivaleur.com", "crosslisteu.com")
MIN_GROEP = 10
PUNTEN = ("eerste_opdracht", "eerste_artikel", "eerste_live")
DREMPELS_UUR = (1, 24, 72)


def _tijd(s):
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def accounts(admin, sinds):
    uit = {}
    for pagina in range(1, 51):
        gevonden = admin.auth.admin.list_users(page=pagina, per_page=200)
        for u in gevonden or []:
            uit[u.id] = u
        if not gevonden or len(gevonden) < 200:
            break
    if not uit:
        raise RuntimeError("Nul accounts gelezen: kapotte meting, geen lege lijst.")
    lijst = []
    for uid, u in uit.items():
        aangemeld = _tijd(str(u.created_at))
        mail = (u.email or "").lower()
        if (aangemeld and aangemeld >= sinds and u.email_confirmed_at
                and not mail.endswith(EIGEN_DOMEINEN)):
            lijst.append((uid, aangemeld))
    return sorted(lijst, key=lambda x: x[1])


def een(vraag, kolom):
    rij = (vraag.order(kolom).limit(1).execute().data or [{}])[0]
    return _tijd(rij.get(kolom))


def meet_klant(db, uid, aangemeld):
    t_opdracht = een(db.table("jobs").select("done_at").eq("user_id", uid)
                     .eq("status", "done").not_.is_("done_at", "null"), "done_at")
    t_artikel = een(db.table("items").select("created_at").eq("user_id", uid), "created_at")
    t_live = een(db.table("jobs").select("done_at").eq("user_id", uid).eq("action", "create")
                 .eq("status", "done").not_.is_("done_at", "null"), "done_at")
    uit = {"aangemeld": aangemeld}
    for naam, t in zip(PUNTEN, (t_opdracht, t_artikel, t_live)):
        uit[naam] = (t - aangemeld).total_seconds() / 3600 if t and t >= aangemeld else None
    return uit


def samenvat(klanten, nu):
    s = {"klanten": len(klanten), "waarschuwing": len(klanten) < MIN_GROEP}
    for p in PUNTEN:
        uren = [k[p] for k in klanten if k[p] is not None]
        s[p] = {
            "bereikt": len(uren),
            "mediaan_uur": round(statistics.median(uren), 1) if uren else None,
            "binnen": {},
        }
        for u in DREMPELS_UUR:
            oud_genoeg = [k for k in klanten if (nu - k["aangemeld"]).total_seconds() / 3600 >= u]
            goed = [k for k in oud_genoeg if k[p] is not None and k[p] <= u]
            s[p]["binnen"][f"{u}u"] = (
                {"van": len(oud_genoeg), "aantal": len(goed),
                 "pct": round(100 * len(goed) / len(oud_genoeg)) if oud_genoeg else None})
    return s


def maandag(d):
    return (d - timedelta(days=d.weekday())).date().isoformat()


def meet(dagen=90, db=None, admin=None, nu=None):
    nu = nu or datetime.now(timezone.utc)
    if db is None:
        sys.path.insert(0, str(REPO))
        from backend.database import get_admin_db, get_db
        db, admin = get_db(), get_admin_db()
    sinds = nu - timedelta(days=dagen)
    klanten = []
    for uid, aangemeld in accounts(admin, sinds):
        k = meet_klant(db, uid, aangemeld)
        k["uid"] = uid
        klanten.append(k)
    groepen = {
        "voor": [k for k in klanten if k["aangemeld"] < VOOR_TOT],
        "na": [k for k in klanten if k["aangemeld"] >= VOOR_TOT],
    }
    weken = {}
    for k in klanten:
        weken.setdefault(maandag(k["aangemeld"]), []).append(k)
    return {
        "gemeten_op": nu.isoformat(), "wijziging_op": VOOR_TOT.isoformat(),
        "voor": samenvat(groepen["voor"], nu), "na": samenvat(groepen["na"], nu),
        "per_week": {w: samenvat(v, nu) for w, v in sorted(weken.items())},
    }


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
