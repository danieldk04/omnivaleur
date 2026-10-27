"""Wat ben ik creators verschuldigd? (sinds 27-10-2026)

Gebruik (python3.13, vanuit de repo-root):

  python3.13 scripts/creator_commissie.py stand
  python3.13 scripts/creator_commissie.py uitbetaald --code CODE --bedrag 12,34 --ref "bank 28-12"

`stand` toont per creator wat nog wacht (jonger dan 60 dagen), wat nu
uitbetaalbaar is en wat al betaald is. De cijfers komen uit het kasboek dat de
server elk uur bijwerkt vanuit Stripe (backend/services/creator_commissie.py).

`uitbetaald` zet de uitbetaalbare regels op betaald, ná jouw bankoverschrijving.
Het script maakt zelf nooit geld over. Je moet het bedrag opnieuw intikken: komt
het niet overeen met wat er nu uitbetaalbaar is (er kwam intussen een betaling
bij), dan weigert het en verandert er niets.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.creator_commissie import TABEL, WACHT_DAGEN, uitbetaalbaar  # noqa: E402


def _euro(cents: int) -> str:
    return f"€ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _db():
    from backend.config import settings
    from supabase import create_client
    if not settings.supabase_service_key:
        print("SUPABASE_SERVICE_KEY ontbreekt: zonder die sleutel leest de database niets (RLS).")
        return None
    # Bewust de service-sleutel: backend.database.get_db() pakt lokaal de anon-sleutel.
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _lees(db):
    from backend.database import execute_with_retry
    try:
        codes = execute_with_retry(db.table("referral_codes").select(
            "code, creator_name, commission_pct").eq("kind", "creator")).data or []
        rijen = execute_with_retry(db.table(TABEL).select("*")).data or []
    except Exception as e:
        print(f"Kasboek niet te lezen ({e}). Staat scripts/sql/creator_commissie.sql al in Supabase?")
        return None, None
    return [c for c in codes if (c.get("commission_pct") or 0) > 0], rijen


def stand(_a) -> int:
    db = _db()
    if db is None:
        return 1
    codes, rijen = _lees(db)
    if codes is None:
        return 1
    if not codes:
        print("Nog geen creatorcodes met commissie.")
        return 0
    nu = datetime.now(timezone.utc)
    for c in codes:
        eigen = [r for r in rijen if r["code"] == c["code"]]
        klaar = sum(r["commission_cents"] for r in eigen if uitbetaalbaar(r, nu))
        wacht = sum(r["commission_cents"] for r in eigen
                    if r["status"] == "open" and not uitbetaalbaar(r, nu))
        betaald = sum(r["commission_cents"] for r in eigen if r["status"] == "uitbetaald")
        klanten = len({r["referred_user_id"] for r in eigen})
        print(f"{c.get('creator_name') or c['code']} ({c['code']}, {c['commission_pct']}%): "
              f"{klanten} betalende klant(en)")
        print(f"   uitbetaalbaar nu   {_euro(klaar)}")
        print(f"   wacht (< {WACHT_DAGEN} dgn)   {_euro(wacht)}")
        print(f"   al uitbetaald      {_euro(betaald)}")
    return 0


def uitbetaald(a) -> int:
    db = _db()
    if db is None:
        return 1
    from backend.database import execute_with_retry
    codes, rijen = _lees(db)
    if codes is None:
        return 1
    nu = datetime.now(timezone.utc)
    klaar = [r for r in rijen if r["code"] == a.code and uitbetaalbaar(r, nu)]
    totaal = sum(r["commission_cents"] for r in klaar)
    try:
        opgegeven = round(float(a.bedrag.replace(".", "").replace(",", ".")) * 100)
    except ValueError:
        print(f"Bedrag '{a.bedrag}' is geen getal.")
        return 1
    if opgegeven != totaal:
        print(f"Niet gedaan: uitbetaalbaar is nu {_euro(totaal)}, jij gaf {_euro(opgegeven)} op. "
              "Draai `stand` opnieuw en maak het juiste bedrag over.")
        return 1
    if not klaar:
        print("Niets uitbetaalbaar voor deze code.")
        return 0
    for r in klaar:
        execute_with_retry(db.table(TABEL).update({
            "status": "uitbetaald", "uitbetaald_at": nu.isoformat(),
            "uitbetaling_ref": a.ref, "updated_at": nu.isoformat(),
        }).eq("invoice_id", r["invoice_id"]).eq("status", "open"))
    print(f"{len(klaar)} betaling(en) voor {_euro(totaal)} op uitbetaald gezet ({a.ref}).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stand").set_defaults(fn=stand)
    u = sub.add_parser("uitbetaald")
    u.add_argument("--code", required=True)
    u.add_argument("--bedrag", required=True, help='bijvoorbeeld "12,34"')
    u.add_argument("--ref", required=True, help="hoe je het overmaakte, voor de administratie")
    u.set_defaults(fn=uitbetaald)
    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
