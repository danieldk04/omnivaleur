#!/usr/bin/env python3
"""Wie kwam de afgelopen dagen binnen via de uitnodiging van een klant?

Alleen lezen. Per nieuwe vriend: wie hem uitnodigde (ingekort adres), of hij proeft of
betaalt, en hoe ver hij is (artikelen, gekoppelde kanalen). De onboardingroutine
draait dit elke ronde en behandelt deze mensen als eerste: aan hen is "wij zetten je
eerste 100 artikelen in" beloofd (docs/aankondiging-nieuwe-plannen.md).

GEBRUIK
    python3.13 scripts/nieuwe_vrienden.py              # laatste 48 uur
    python3.13 scripts/nieuwe_vrienden.py --uren 168
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import execute_with_retry, get_db  # noqa: E402
from backend.services.referral_mail import email_van, maskeer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uren", type=int, default=48)
    args = ap.parse_args()
    db = get_db()
    sinds = (datetime.now(timezone.utc) - timedelta(hours=args.uren)).isoformat()
    codes = (execute_with_retry(db.table("referral_codes").select("code, owner_user_id")).data) or []
    eigenaar = {c["code"]: c["owner_user_id"] for c in codes if c.get("owner_user_id")}
    nieuw = (execute_with_retry(
        db.table("referrals").select("user_id, code, created_at, first_paid_at")
        .gte("created_at", sinds).order("created_at", desc=True)).data) or []
    # Alleen uitnodigingen van klanten. Creatorcodes horen bij de creatorroutine.
    nieuw = [v for v in nieuw if v.get("code") in eigenaar and v["user_id"] != eigenaar[v["code"]]]
    print(f"Nieuwe vrienden via een klant, laatste {args.uren} uur: {len(nieuw)}")
    for v in nieuw:
        uid = v["user_id"]
        # Per klant gemeten, nooit over meerdere klanten tegelijk (meten-op-de-productiedatabase).
        abo = (execute_with_retry(db.table("subscriptions").select("status, plan")
               .eq("user_id", uid).limit(1)).data or [{}])[0]
        items = execute_with_retry(db.table("items").select("id", count="exact").eq("user_id", uid).limit(1)).count
        kanalen = (execute_with_retry(db.table("platform_credentials").select("platform")
                   .eq("user_id", uid)).data) or []
        kanalen = sorted({k["platform"] for k in kanalen if not str(k["platform"]).startswith("_")})
        print(f"- {maskeer(email_van(uid))}  (uitgenodigd door {maskeer(email_van(eigenaar[v['code']]))}, "
              f"{(v.get('created_at') or '')[:16]})")
        print(f"    status {abo.get('status') or 'proef/onbekend'}, plan {abo.get('plan') or '-'}, "
              f"artikelen {items}, kanalen {', '.join(kanalen) or 'geen'}, user_id {uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
