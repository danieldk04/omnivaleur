#!/usr/bin/env python3
"""Leert Daniels schrijfstijl uit wat hij echt verstuurt.

Drie opdrachten:
  concept   bewaart een concept dat Claude schreef (tekst via stdin)
  ophalen   leest nieuwe, door Daniel zelf verstuurde mails uit Zoho en zet ze
            naast het bijbehorende concept, in data/schrijfstijl/nieuw.json
  klaar     markeert alles uit nieuw.json als verwerkt

Eigen mails herkennen we aan de kop X-Mailer: Zoho Mail. De koude mails van de
machine hebben die kop niet. Alles staat in data/schrijfstijl/, buiten git,
want er staan klantgegevens in. Alleen docs/schrijfstijl-daniel.md gaat mee.
"""
import argparse
import email
import imaplib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "schrijfstijl"
CONCEPTEN = DATA / "concepten"
GEZIEN = DATA / "gezien.json"
NIEUW = DATA / "nieuw.json"
MAX_TEKST = 3000
CONCEPT_VENSTER = timedelta(days=4)

CITAAT_START = re.compile(
    r"^\s*(-{2,}\s*)?(Op|On)\s.+(schreef|wrote).*$|^\s*(Van|From):\s.+$", re.I)


def _env() -> None:
    for regel in (ROOT / ".env").read_text().splitlines():
        regel = regel.strip()
        if "=" in regel and not regel.startswith("#"):
            k, v = regel.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _eigen_tekst(msg: email.message.EmailMessage) -> str:
    deel = msg.get_body(("plain",))
    if deel is not None:
        tekst = deel.get_content()
    else:
        deel = msg.get_body(("html",))
        tekst = re.sub(r"<[^>]+>", " ", deel.get_content()) if deel else ""
    regels = []
    for regel in tekst.splitlines():
        if regel.lstrip().startswith(">") or CITAAT_START.match(regel):
            break
        regels.append(regel.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(regels)).strip()[:MAX_TEKST]


def _gezien() -> set[str]:
    return set(json.loads(GEZIEN.read_text())) if GEZIEN.exists() else set()


def cmd_concept(a) -> None:
    CONCEPTEN.mkdir(parents=True, exist_ok=True)
    tekst = sys.stdin.read().strip()
    if not tekst:
        sys.exit("Geen conceptttekst via stdin ontvangen.")
    nu = datetime.now(timezone.utc)
    pad = CONCEPTEN / f"{nu:%Y%m%d-%H%M%S}.json"
    pad.write_text(json.dumps({
        "aan": a.aan.strip().lower(), "onderwerp": a.onderwerp or "",
        "gemaakt": nu.isoformat(), "tekst": tekst}, ensure_ascii=False, indent=1))
    print(f"Concept bewaard: {pad.name}")


def _concepten() -> list[dict]:
    uit = []
    for pad in sorted(CONCEPTEN.glob("*.json")) if CONCEPTEN.exists() else []:
        c = json.loads(pad.read_text())
        c["gemaakt_dt"] = datetime.fromisoformat(c["gemaakt"])
        uit.append(c)
    return uit


def cmd_ophalen(a) -> None:
    _env()
    DATA.mkdir(parents=True, exist_ok=True)
    gezien, concepten = _gezien(), _concepten()
    eigen = os.environ["MAIL_USER"].lower()
    sinds = (date.today() - timedelta(days=a.dagen)).strftime("%d-%b-%Y")
    nieuw: list[dict] = []
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"], 993) as imap:
        imap.login(os.environ["MAIL_USER"], os.environ["MAIL_PASS"])
        if imap.select('"Verzonden"', readonly=True)[0] != "OK":
            sys.exit("Map Verzonden niet gevonden: dit is een storing, geen lege lijst.")
        nummers = (imap.search(None, f"(SINCE {sinds})")[1][0] or b"").split()
        for n in nummers:
            kop = email.message_from_bytes(imap.fetch(
                n, "(BODY.PEEK[HEADER.FIELDS (X-MAILER MESSAGE-ID)])")[1][0][1])
            mid = str(kop.get("Message-ID") or "").strip()
            if not mid or mid in gezien:
                continue
            # Eigen mails herkennen aan de kop; de machine zet die niet.
            if "zoho mail" not in str(kop.get("X-Mailer") or "").lower():
                continue
            ruw = imap.fetch(n, "(BODY.PEEK[])")[1][0][1]
            msg = email.message_from_bytes(ruw, policy=policy.default)
            aan = parseaddr(str(msg.get("To") or ""))[1].lower()
            if not aan or aan == eigen:
                continue
            try:
                wanneer = parsedate_to_datetime(str(msg.get("Date")))
            except Exception:  # noqa: BLE001
                wanneer = datetime.now(timezone.utc)
            passend = [c for c in concepten if c["aan"] == aan
                       and timedelta(0) <= wanneer - c["gemaakt_dt"] <= CONCEPT_VENSTER]
            concept = max(passend, key=lambda c: c["gemaakt_dt"]) if passend else None
            nieuw.append({
                "message_id": mid, "wanneer": wanneer.isoformat(), "aan": aan,
                "onderwerp": str(msg.get("Subject") or ""),
                "antwoord": bool(msg.get("In-Reply-To")),
                "verstuurd": _eigen_tekst(msg),
                "concept": concept["tekst"] if concept else None})
    nieuw.sort(key=lambda m: m["wanneer"])
    NIEUW.write_text(json.dumps(nieuw, ensure_ascii=False, indent=1))
    mt = sum(1 for m in nieuw if m["concept"])
    print(f"{len(nieuw)} nieuwe eigen mails, waarvan {mt} met concept ernaast -> {NIEUW}")


def cmd_klaar(_a) -> None:
    ids = {m["message_id"] for m in json.loads(NIEUW.read_text())}
    GEZIEN.write_text(json.dumps(sorted(_gezien() | ids)))
    print(f"{len(ids)} mails als verwerkt gemarkeerd.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("concept")
    c.add_argument("--aan", required=True)
    c.add_argument("--onderwerp", default="")
    c.set_defaults(f=cmd_concept)
    o = sub.add_parser("ophalen")
    o.add_argument("--dagen", type=int, default=3)
    o.set_defaults(f=cmd_ophalen)
    sub.add_parser("klaar").set_defaults(f=cmd_klaar)
    args = p.parse_args()
    args.f(args)
