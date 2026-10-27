#!/usr/bin/env python3
"""Verstuurt klaarstaande creatormails uit data/creator_outreach/wachtrij.csv via Zoho SMTP,
op dezelfde manier als leadgen_creators_mail.py voor koude leads.

  python3.13 scripts/creator_outreach_verstuur.py                 dry-run: toont wat er zou gaan
  python3.13 scripts/creator_outreach_verstuur.py --echt          verstuurt echt (max 10 per dag)
  python3.13 scripts/creator_outreach_verstuur.py --echt --test ADRES   proefmail naar ADRES,
                                                                  de creator wordt niet gelogd

Een rij komt pas in de wachtrij met status 'klaar' en een concept dat een mens heeft gelezen.
Geen tekst verzinnen: de opener moet uit het echte profiel komen (zie kennisbank, Hermes-tas).
Verstuurd wordt alleen naar een adres dat nog niet in het logboek staat. Het wachtwoord komt uit
MAIL_PASS in de omgeving of in .env en wordt nooit getoond."""
import argparse
import csv
import os
import smtplib
import ssl
import sys
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import creator_outreach_meting as meting  # noqa: E402

WACHTRIJ = ROOT / "data" / "creator_outreach" / "wachtrij.csv"
KOP = ["handle", "naam", "email", "type", "volgers", "onderwerp", "concept", "status"]
HOST = "smtp.zoho.eu"
USER = "daniel@omnivaleur.nl"
DAGMAX = 10


def wachtwoord() -> str:
    if os.environ.get("MAIL_PASS"):
        return os.environ["MAIL_PASS"]
    for regel in (ROOT / ".env").read_text().splitlines():
        if regel.startswith("MAIL_PASS="):
            return regel.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("MAIL_PASS ontbreekt in de omgeving en in .env")


def lees_wachtrij() -> list[dict]:
    if not WACHTRIJ.exists():
        return []
    with WACHTRIJ.open(newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") or "" for k in KOP} for r in csv.DictReader(f)]


def schrijf_wachtrij(rijen: list[dict]) -> None:
    WACHTRIJ.parent.mkdir(parents=True, exist_ok=True)
    with WACHTRIJ.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOP)
        w.writeheader()
        w.writerows(rijen)


def verstuur(ontvanger: str, r: dict) -> None:
    msg = MIMEText(r["concept"], "plain", "utf-8")
    msg["Subject"] = r["onderwerp"]
    msg["From"] = f"Daniel <{USER}>"
    msg["To"] = ontvanger
    with smtplib.SMTP_SSL(HOST, 465, context=ssl.create_default_context()) as smtp:
        smtp.login(USER, wachtwoord())
        smtp.sendmail(USER, [ontvanger], msg.as_string())


def run(a: argparse.Namespace) -> int:
    rijen = lees_wachtrij()
    log = meting.lees()
    bekend = {r["email"].lower() for r in log}
    vandaag = sum(1 for r in log if r["datum"] == str(date.today()))
    ruimte = DAGMAX - vandaag
    if ruimte <= 0:
        print(f"Dagmaximum van {DAGMAX} is al bereikt vandaag.")
        return 0
    kandidaten = [r for r in rijen if r["status"] == "klaar"][: min(a.limit, ruimte)]
    if not kandidaten:
        print("Niets klaar in de wachtrij.")
        return 0
    for r in kandidaten:
        if r["email"].lower() in bekend:
            print(f"OVERSLAAN {r['handle']}: dit adres staat al in het logboek")
            r["status"] = "overgeslagen"
            continue
        ontvanger = a.test or r["email"]
        print(f"{'VERSTUUR' if a.echt else 'DRY-RUN'} {r['handle']} -> {ontvanger}")
        if not a.echt:
            continue
        verstuur(ontvanger, r)
        if a.test:
            continue
        log.append({"datum": str(date.today()), "handle": r["handle"], "naam": r["naam"],
                    "email": r["email"], "code": "", "versie": "A", "reactie": "",
                    "reactie_datum": "", "link": "", "type": r["type"], "volgers": r["volgers"]})
        meting.schrijf(log)
        r["status"] = "verstuurd"
    if a.echt and not a.test:
        schrijf_wachtrij(rijen)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--echt", action="store_true", help="echt versturen, anders alleen tonen")
    p.add_argument("--limit", type=int, default=10, help="maximaal N per beurt")
    p.add_argument("--test", default="", help="stuur de mail naar dit adres in plaats van de creator")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
