#!/usr/bin/env python3
"""Meting van de creatormails (Instagram): wie is benaderd, wie klikte, wie meldde zich aan, wie betaalt.

  log --handle H --naam N --email E [--versie A]   code aanmaken + regel in het logboek
  reactie HANDLE ja|nee|geen                       reactie van de creator vastleggen
  stand                                            hele trechter, per creator en totaal

Draaien met python3.13 vanuit de repo-root (python3 mist de Supabase-pakketten).
Het logboek staat in data/creator_outreach/ en blijft buiten git (bevat e-mailadressen).

De creatorcode is de Instagram-naam in kleine letters; de link is omnivaleur.com/r/CODE.
Een aanmelding telt alleen mee als de code bestond voordat de ander zich aanmeldde, dus
eerst `log`, dan pas de mail versturen.

bounty_cents staat bewust op 0: de oude teller in referrals.py rekent een vaste 25 euro per
klant na 60 dagen. De afspraak van 24-10-2026 is 25% commissie; dat bedrag rekenen we uit
de echte Stripe-betalingen, niet uit die oude teller."""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import execute_with_retry, get_db  # noqa: E402
from backend.services.referral_codes import schoon_code  # noqa: E402

LOG = ROOT / "data" / "creator_outreach" / "instagram.csv"
KOP = ["datum", "handle", "naam", "email", "code", "versie", "reactie"]
BETALEND = {"active", "payment_processing"}


def lees() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open(newline="") as f:
        return list(csv.DictReader(f))


def schrijf(rijen: list[dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOP)
        w.writeheader()
        w.writerows(rijen)


def log(a) -> int:
    handle = a.handle.lstrip("@").strip()
    code = schoon_code(handle.replace(".", "_"))
    if not code:
        print(f"Ongeldige code uit {handle!r}: alleen letters, cijfers, - en _")
        return 1
    rijen = lees()
    if any(r["code"] == code for r in rijen):
        print(f"{code} staat al in het logboek, niets gedaan.")
        return 0
    execute_with_retry(get_db().table("referral_codes").upsert({
        "code": code, "creator_name": a.naam, "platform": "instagram",
        "profile_url": f"https://www.instagram.com/{handle}/", "bounty_cents": 0,
        "fee_paid_cents": 0, "kind": "creator", "active": True,
    }, on_conflict="code"))
    rijen.append({"datum": str(date.today()), "handle": handle, "naam": a.naam,
                  "email": a.email, "code": code, "versie": a.versie, "reactie": ""})
    schrijf(rijen)
    print(f"Klaar. Link voor de mail: https://omnivaleur.com/r/{code}")
    return 0


def reactie(a) -> int:
    rijen = lees()
    hit = [r for r in rijen if r["handle"].lower() == a.handle.lstrip("@").strip().lower()]
    if not hit:
        print("Niet gevonden in het logboek.")
        return 1
    hit[0]["reactie"] = a.waarde
    schrijf(rijen)
    return 0


def stand(_a) -> int:
    rijen = lees()
    if not rijen:
        print("Nog niets verstuurd.")
        return 0
    db = get_db()
    codes = [r["code"] for r in rijen]
    kliks = execute_with_retry(db.table("referral_clicks").select("code, ip_hash").in_("code", codes)).data or []
    verw = execute_with_retry(db.table("referrals").select("user_id, code, first_paid_at").in_("code", codes)).data or []
    abos = {}
    if verw:
        for r in execute_with_retry(db.table("subscriptions").select("user_id, status").in_("user_id", [v["user_id"] for v in verw])).data or []:
            abos[r["user_id"]] = r.get("status")
    tot = dict(verstuurd=0, reactie=0, ja=0, klik=0, aanmeld=0, betalend=0)
    print(f"{'creator':<22}{'datum':<12}{'reactie':<8}{'kliks':>6}{'uniek':>6}{'aanmeld':>8}{'betalend':>9}")
    for r in rijen:
        k = [x for x in kliks if x["code"] == r["code"]]
        uniek = len({x["ip_hash"] for x in k if x["ip_hash"]})
        v = [x for x in verw if x["code"] == r["code"]]
        b = [x for x in v if abos.get(x["user_id"]) in BETALEND]
        print(f"{r['handle'][:21]:<22}{r['datum']:<12}{(r['reactie'] or '-'):<8}{len(k):>6}{uniek:>6}{len(v):>8}{len(b):>9}")
        tot["verstuurd"] += 1
        tot["reactie"] += bool(r["reactie"])
        tot["ja"] += r["reactie"] == "ja"
        tot["klik"] += uniek > 0
        tot["aanmeld"] += len(v)
        tot["betalend"] += len(b)
    print(f"\nVerstuurd {tot['verstuurd']}, gereageerd {tot['reactie']} (ja: {tot['ja']}), "
          f"creators met een klik {tot['klik']}, aanmeldingen {tot['aanmeld']}, betalend {tot['betalend']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    l = s.add_parser("log")
    l.add_argument("--handle", required=True)
    l.add_argument("--naam", required=True)
    l.add_argument("--email", required=True)
    l.add_argument("--versie", default="A")
    l.set_defaults(f=log)
    r = s.add_parser("reactie")
    r.add_argument("handle")
    r.add_argument("waarde", choices=["ja", "nee", "geen"])
    r.set_defaults(f=reactie)
    s.add_parser("stand").set_defaults(f=stand)
    a = p.parse_args()
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
