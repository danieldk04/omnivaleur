"""Gratis toegang zonder einddatum voor een creator of partner (sinds 29-10-2026).

Gebruik (python3.13, vanuit de repo-root):

  python3.13 scripts/gratis_toegang.py EMAIL            kijken wat er zou gebeuren
  python3.13 scripts/gratis_toegang.py EMAIL --doe-het  echt zetten

Zet de abonnementsrij op status `complimentary` (zie evaluate_access in
backend/services/billing.py: onbeperkte toegang, nooit gezet door Stripe). De rij
ontstaat bij een nieuw account pas bij het eerste openen van het dashboard; bestaat
hij nog niet, dan maakt dit script hem aan. Heeft het account al een betalend
Stripe-abonnement, dan weigert het: dat zou het abonnement verbergen.
De oude rij gaat naar ~/.omnivaleur/backups/ zodat terugzetten kan.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def plan(rij: dict | None) -> tuple[str, dict | None]:
    """Wat moet er gebeuren met deze rij? ('weiger'|'niets'|'maak'|'zet', nieuwe waarden)."""
    if rij is None:
        return "maak", {"status": "complimentary", "plan": "pro"}
    if rij.get("stripe_subscription_id"):
        return "weiger", None
    if rij.get("status") == "complimentary":
        return "niets", None
    return "zet", {"status": "complimentary"}


def zoek_gebruiker(db, email: str) -> str | None:
    doel = email.strip().lower()
    for pagina in range(1, 21):
        gevonden = db.auth.admin.list_users(page=pagina, per_page=200)
        for u in gevonden or []:
            if (u.email or "").lower() == doel:
                return u.id
        if not gevonden or len(gevonden) < 200:
            break
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("email")
    ap.add_argument("--doe-het", action="store_true")
    args = ap.parse_args()

    from supabase import create_client
    from backend.config import settings
    if not settings.supabase_service_key:
        print("SUPABASE_SERVICE_KEY ontbreekt.")
        return 1
    db = create_client(settings.supabase_url, settings.supabase_service_key)

    uid = zoek_gebruiker(db, args.email)
    if not uid:
        print(f"Geen account met {args.email}. Heeft ze zich al aangemeld en haar mail bevestigd?")
        return 2
    rij = (db.table("subscriptions").select("*").eq("user_id", uid).limit(1).execute().data or [None])[0]
    wat, nieuw = plan(rij)
    print(f"Account {uid}; huidige rij: {json.dumps(rij, default=str) if rij else 'geen'}")
    if wat == "weiger":
        print("GEWEIGERD: dit account heeft een Stripe-abonnement. Niets veranderd.")
        return 3
    if wat == "niets":
        print("Staat al op complimentary. Niets te doen.")
        return 0
    print(f"Actie: {wat} {nieuw}")
    if not args.doe_het:
        print("Droogloop: niets veranderd. Voeg --doe-het toe om te zetten.")
        return 0

    kopie = Path.home() / ".omnivaleur" / "backups" / f"gratis_toegang_{uid[:8]}_{datetime.now(timezone.utc):%Y%m%d%H%M}.json"
    kopie.parent.mkdir(parents=True, exist_ok=True)
    kopie.write_text(json.dumps(rij, default=str))
    if wat == "maak":
        db.table("subscriptions").insert({"user_id": uid, **nieuw}).execute()
    else:
        db.table("subscriptions").update(nieuw).eq("user_id", uid).execute()
    na = (db.table("subscriptions").select("*").eq("user_id", uid).limit(1).execute().data or [None])[0]
    from backend.services.billing import evaluate_access
    print(f"Nu: {json.dumps(na, default=str)}")
    print(f"Toegang: {evaluate_access(na)}  (oude rij bewaard in {kopie})")
    return 0 if na and na.get("status") == "complimentary" else 4


if __name__ == "__main__":
    sys.exit(main())
