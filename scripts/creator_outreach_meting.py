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
    naar_sheet(rijen)


def naar_sheet(rijen: list[dict]) -> None:
    """Spiegelt het logboek naar het tabblad Creators in "Omnivaleur E-mail outreach".
    Faalt de sheet, dan blijft het lokale logboek goed en krijg je een waarschuwing."""
    from pathlib import Path as _P
    import os
    from leadgen_sheets import MAIL_SHEET, Sheets
    try:
        pad = _P.home() / ".omnivaleur" / "sheets-sleutel.json"
        ruw = os.environ.get("GOOGLE_SHEETS_SLEUTEL") or (pad.read_text() if pad.exists() else "")
        blad = [KOP] + [[r[k] for k in KOP] for r in rijen]
        Sheets(ruw).schrijf(MAIL_SHEET, [{"range": "Creators!A1", "values": blad}])
    except Exception as fout:
        print(f"Let op: tabblad Creators niet bijgewerkt ({fout}). Het logboek staat wel goed.",
              file=sys.stderr)


def maak_code(code: str, naam: str, handle: str) -> int:
    from backend.config import settings
    from backend.database import execute_with_retry
    from supabase import create_client
    if not settings.supabase_service_key:
        print("SUPABASE_SERVICE_KEY ontbreekt: zonder die sleutel schrijft de database niets (RLS).")
        return 1
    # Bewust de service-sleutel: backend.database.get_db() pakt lokaal de anon-sleutel.
    db = create_client(settings.supabase_url, settings.supabase_service_key)
    rij = {
        "code": code, "creator_name": naam, "platform": "instagram",
        "profile_url": f"https://www.instagram.com/{handle}/", "bounty_cents": 0,
        "fee_paid_cents": 0, "kind": "creator", "active": True,
    }
    try:
        # 25% commissie, uitbetaald via scripts/creator_commissie.py.
        execute_with_retry(db.table("referral_codes").upsert(
            {**rij, "commission_pct": 25}, on_conflict="code"))
    except Exception:
        # Kolom ontbreekt: scripts/sql/creator_commissie.sql is nog niet gedraaid.
        # De link moet blijven werken, maar zonder percentage telt er niets mee.
        execute_with_retry(db.table("referral_codes").upsert(rij, on_conflict="code"))
        print("Let op: commissie niet gekoppeld aan deze link. Draai eerst "
              "scripts/sql/creator_commissie.sql in Supabase en maak de link opnieuw aan.",
              file=sys.stderr)
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
    # Leren: welk type creator reageert en zegt ja? Pas bij genoeg mails zegt dit iets.
    typen = sorted({r["type"] or "onbekend" for r in rijen})
    print(f"\n{'type':<12}{'verstuurd':>10}{'gereageerd':>12}{'ja':>5}")
    for t in typen:
        s = [r for r in rijen if (r["type"] or "onbekend") == t]
        print(f"{t:<12}{len(s):>10}{sum(r['reactie'] in ('ja', 'nee') for r in s):>12}"
              f"{sum(r['reactie'] == 'ja' for r in s):>5}")
    oud = [r for r in rijen if not r["reactie"] and (date.today() - date.fromisoformat(r["datum"])).days >= 5]
    if oud:
        print(f"\nOpvolging nodig: {len(oud)} mails 5+ dagen zonder reactie "
              f"(eerst Zoho checken): {', '.join(r['handle'] for r in oud)}")
    if n < 30:
        print(f"Let op: pas bij ~30 mails zegt het verschil per type iets, nu {n}.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    l = s.add_parser("log")
    l.add_argument("--handle", required=True)
    l.add_argument("--naam", required=True)
    l.add_argument("--email", default="")
    l.add_argument("--versie", default="A")
    l.add_argument("--type", default="", choices=["", "verkoper", "ugc", "bureau"],
                   help="verkoper = verkoopt zelf tweedehands, ugc = brand-UGC creator, bureau = via bureau")
    l.add_argument("--volgers", default="", help="aantal volgers, ruwweg (bv. 1500)")
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
