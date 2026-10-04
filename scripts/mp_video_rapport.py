#!/usr/bin/env python3
"""Hoe presteert /mp-video (de pagina achter de koude mail)? Alleen lezen, geen AI.

Gebruikt de bestaande GA4-koppeling (backend/services/ga4.py), dus draai dit
waar de GA4_*- en GOOGLE_ADS_*-sleutels in de omgeving staan (Daniels Mac).

    python3 scripts/mp_video_rapport.py              # laatste 30 dagen
    python3 scripts/mp_video_rapport.py --dagen 14

Wat het laat zien:
  1. Bezoek per bron/medium op /mp-video (koude-mail/email is de mail zelf).
  2. Hoe lang ze blijven en hoeveel er echt actief waren.
  3. Events op de pagina: scroll, cta_click, en video_start/progress/complete.
     Sinds 04-10-2026 meldt de YouTube-embed (enablejsapi) start, 25/50/75% en
     uitgekeken. Let op: een milestone telt ook als iemand ernaartoe spoelt. Staan ze
     voor die datum op 0, dan bestond de meting nog niet.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services import ga4  # noqa: E402

PAD = "/mp-video"


def _nl(n) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _sec(n) -> str:
    n = float(n or 0)
    return f"{int(n // 60)}m{int(n % 60):02d}s"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dagen", type=int, default=30)
    args = ap.parse_args()
    eind = date.today().isoformat()
    start = (date.today() - timedelta(days=args.dagen)).isoformat()

    if not ga4.is_configured():
        print("GA4 is hier niet gekoppeld (GA4_PROPERTY_ID / refresh token / OAuth-client ontbreekt).")
        return 1
    probe = ga4.probe(start, eind)
    if not probe.get("ok"):
        print("GA4-koppeling werkt niet:", probe.get("reden"))
        return 1

    print(f"/mp-video, {start} t/m {eind}\n")

    rijen = ga4._run(
        ["landingPagePlusQueryString", "sessionSource", "sessionMedium"],
        ["sessions", "activeUsers", "engagedSessions", "engagementRate",
         "userEngagementDuration", "conversions"],
        start, eind, limit=1000)
    rijen = [r for r in rijen if r["landingPagePlusQueryString"].split("?")[0].rstrip("/") == PAD]
    per: dict[tuple, dict] = {}
    for r in rijen:
        k = (r["sessionSource"], r["sessionMedium"])
        t = per.setdefault(k, dict(s=0, u=0, e=0, d=0.0, c=0))
        t["s"] += r["sessions"]; t["u"] += r["activeUsers"]; t["e"] += r["engagedSessions"]
        t["d"] += r["userEngagementDuration"]; t["c"] += r["conversions"]

    print("1. Bezoek per bron (landing op /mp-video)")
    print(f"   {'bron / medium':34} {'sessies':>8} {'betrokken':>10} {'gem. tijd':>10} {'conv.':>6}")
    if not per:
        print("   geen sessies gevonden: check of de mail wel via /mp loopt en het venster klopt")
    for (src, med), t in sorted(per.items(), key=lambda x: -x[1]["s"]):
        pct = 100 * t["e"] / t["s"] if t["s"] else 0
        gem = t["d"] / t["s"] if t["s"] else 0
        print(f"   {src + ' / ' + med:34} {_nl(t['s']):>8} {pct:>9.0f}% {_sec(gem):>10} {_nl(t['c']):>6}")

    print("\n2. Events op de pagina")
    ev = ga4._run(["pagePath", "eventName"], ["eventCount", "totalUsers"], start, eind, limit=1000)
    ev = [e for e in ev if e["pagePath"].rstrip("/") == PAD]
    gezien = {e["eventName"]: e for e in ev}
    for naam in ("page_view", "scroll", "cta_click", "video_start", "video_progress", "video_complete"):
        e = gezien.get(naam)
        print(f"   {naam:16} {_nl(e['eventCount']) if e else '0':>7} events"
              f"{'  (' + _nl(e['totalUsers']) + ' gebruikers)' if e else ''}")
    if "video_start" not in gezien:
        print("   -> geen video_start: niemand drukte op play, of de meting bestond nog niet (voor 04-10-2026).")

    print("\n3. Welke knop is geklikt (cta_location)")
    knoppen = ga4._run(["customEvent:cta_location"], ["eventCount"], start, eind, limit=20)
    if not knoppen:
        print("   niet beschikbaar: registreer cta_location als aangepaste dimensie in GA4")
        print("   (Beheer > Aangepaste definities), anders blijft hij leeg.")
    for k in knoppen:
        print(f"   {k['customEvent:cta_location']:16} {_nl(k['eventCount']):>7}")

    print("\nAanmeldingen die hierna volgen: /register in GA4 > Paden, of de tabel Leads/Logboek.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
