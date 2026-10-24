#!/usr/bin/env python3
"""Meting van de creatormails (Instagram): wie is benaderd, wie reageerde, wat zei die.

  log --handle H --naam N --email E [--versie A]   mail vastleggen in het logboek
  reactie HANDLE ja|nee|geen                       eerste reactie van de creator vastleggen
  stand                                            verstuurd, gereageerd, ja/nee, na hoeveel dagen

Draaien met python3.13 vanuit de repo-root. Het logboek staat in data/creator_outreach/ en
blijft buiten git (bevat e-mailadressen). Er wordt geen link of code per creator gemaakt:
de mail meet alleen de eerste reactie. Pas na een ja volgt een eigen link, dan met
`log --link` (maakt een creatorcode, dit schrijft naar de echte database en vraagt de
service-sleutel). Aanmeldingen en betalingen zijn daarna te zien via
/api/referrals/admin/overzicht.

Reacties zoekt Claude op in de Zoho-inbox (mail_zoek op het adres van de creator) en legt
ze hier vast. bounty_cents staat op 0: de oude teller rekent een vaste 25 euro, de afspraak
is 25% commissie."""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG = ROOT / "data" / "creator_outreach" / "instagram.csv"
KOP = ["datum", "handle", "naam", "email", "code", "versie", "reactie", "reactie_datum", "link",
       "type", "volgers"]


def lees() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open(newline="") as f:
        return [{k: r.get(k, "") or "" for k in KOP} for r in csv.DictReader(f)]


def schrijf(rijen: list[dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KOP)
        w.writeheader()
        w.writerows(rijen)


def maak_code(code: str, naam: str, handle: str) -> int:
    from backend.config import settings
    from backend.database import execute_with_retry
    from supabase import create_client
    if not settings.supabase_service_key:
        print("SUPABASE_SERVICE_KEY ontbreekt: zonder die sleutel schrijft de database niets (RLS).")
        return 1
    # Bewust de service-sleutel: backend.database.get_db() pakt lokaal de anon-sleutel.
    db = create_client(settings.supabase_url, settings.supabase_service_key)
    execute_with_retry(db.table("referral_codes").upsert({
        "code": code, "creator_name": naam, "platform": "instagram",
        "profile_url": f"https://www.instagram.com/{handle}/", "bounty_cents": 0,
        "fee_paid_cents": 0, "kind": "creator", "active": True,
    }, on_conflict="code"))
    print(f"Link: https://omnivaleur.com/r/{code}")
    return 0


def log(a) -> int:
    handle = a.handle.lstrip("@").strip()
    rijen = lees()
    bestaand = [r for r in rijen if r["handle"].lower() == handle.lower()]
    if bestaand and not a.link:
        print(f"{handle} staat al in het logboek, niets gedaan.")
        return 0
    code = ""
    if a.link:
        from backend.services.referral_codes import schoon_code
        code = schoon_code(handle.replace(".", "_")) or ""
        if not code:
            print(f"Ongeldige code uit {handle!r}")
            return 1
        fout = maak_code(code, a.naam, handle)
        if fout:
            return fout
    if bestaand:
        bestaand[0].update(code=code, link="ja")
    else:
        rijen.append({"datum": str(date.today()), "handle": handle, "naam": a.naam, "email": a.email,
                      "code": code, "versie": a.versie, "reactie": "", "reactie_datum": "",
                      "link": "ja" if a.link else "", "type": a.type, "volgers": a.volgers})
    schrijf(rijen)
    print("Vastgelegd.")
    return 0


def reactie(a) -> int:
    rijen = lees()
    hit = [r for r in rijen if r["handle"].lower() == a.handle.lstrip("@").strip().lower()]
    if not hit:
        print("Niet gevonden in het logboek.")
        return 1
    hit[0]["reactie"] = a.waarde
    hit[0]["reactie_datum"] = str(date.today())
    schrijf(rijen)
    return 0


def dagen(r: dict) -> str:
    if not r["reactie_datum"]:
        return "-"
    return str((date.fromisoformat(r["reactie_datum"]) - date.fromisoformat(r["datum"])).days)


def stand(_a) -> int:
    rijen = lees()
    if not rijen:
        print("Nog niets verstuurd.")
        return 0
    print(f"{'creator':<22}{'verstuurd':<12}{'reactie':<9}{'na dagen':>9}")
    for r in rijen:
        print(f"{r['handle'][:21]:<22}{r['datum']:<12}{(r['reactie'] or '-'):<9}{dagen(r):>9}")
    n = len(rijen)
    g = [r for r in rijen if r["reactie"] in ("ja", "nee")]
    ja = sum(r["reactie"] == "ja" for r in rijen)
    print(f"\nVerstuurd {n}, gereageerd {len(g)} ({100 * len(g) // n}%), ja {ja}, "
          f"nee {len(g) - ja}, nog open {sum(not r['reactie'] for r in rijen)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    l = s.add_parser("log")
    l.add_argument("--handle", required=True)
    l.add_argument("--naam", required=True)
    l.add_argument("--email", default="")
    l.add_argument("--versie", default="A")
    l.add_argument("--link", action="store_true", help="ook een creatorcode aanmaken (na een ja)")
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
