#!/usr/bin/env python3
"""
Verstuurt klaarstaande conceptberichten uit de Notion-database "Creator
Outreach (TikTok)" en werkt de rij daarna bij. Doet BEWUST geen tekst
verzinnen — dat gebeurt hier niet met AI, zie WAAROM hieronder.

WAT DIT SCRIPT WEL DOET
    Voor elke rij met Status "Nieuw", een gevuld "Concept bericht"-veld en
    een e-mailadres: de mail versturen vanaf daniel@omnivaleur.nl via Zoho,
    en de rij bijwerken naar Status "Benaderd", Kanaal "E-mail", Benaderd op
    vandaag, plus een logregel onderaan de pagina.

WAT DIT SCRIPT NIET DOET
    Geen concepttekst verzinnen voor rijen zonder "Concept bericht". Op
    06-09-2026 heeft Daniel AI-gegenereerde tekst in de mailmachine bewust
    uitgezet (kostte tokens, liet het API-tegoed leeglopen — zie
    docs/team-notes.md). Los daarvan: op 11-09-2026 bleek in deze zelfde
    outreach een door AI verzonnen persoonlijk detail (een Hermes-tas die niet
    op iemands account voorkwam) een geforceerde, verkeerde opener. Automatisch
    persoonlijke content-claims verzinnen over echte mensen zonder controle is
    dus twee keer een bewezen risico, niet een keer. Een concept moet met de
    hand (of met een los onderzoeksmoment) klaargezet worden voor dit script
    het verstuurt.

NOOIT VANAF HET PRODUCTDOMEIN / NOOIT VIA RESEND
    Zie scripts/leadgen_mail.py — Resend verbiedt koude acquisitie en dat
    account verstuurt ook de wachtwoord- en factuurmail van de app. Deze
    outreach gaat altijd via Zoho/daniel@omnivaleur.nl.

Gebruik:
    export MAIL_HOST=smtp.zoho.eu MAIL_USER=daniel@omnivaleur.nl MAIL_PASS=...
    export NOTION_TOKEN=...
    python3 scripts/leadgen_creators_mail.py run              # echt versturen
    python3 scripts/leadgen_creators_mail.py run --dry-run    # tonen, niet versturen
    python3 scripts/leadgen_creators_mail.py run --limit 5    # per beurt max N (default 5)
"""
from __future__ import annotations

import argparse
import datetime
import os
import smtplib
import ssl
from email.mime.text import MIMEText

import httpx

DB_ID = "b49ee78e-8c0e-418e-b516-4a432753b499"  # Creator Outreach (TikTok)
NOTION_API = "https://api.notion.com/v1"
MAIL_HOST = os.environ.get("MAIL_HOST", "smtp.zoho.eu")
MAIL_USER = os.environ.get("MAIL_USER", "daniel@omnivaleur.nl")
SUBJECT = "Samenwerking met Omnivaleur"


def _need(naam: str) -> str:
    v = os.environ.get(naam, "").strip()
    if not v:
        raise RuntimeError(f"{naam} ontbreekt in de omgeving")
    return v


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {_need('NOTION_TOKEN')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def _klaarstaande_rijen() -> list[dict]:
    """Rijen met Status Nieuw, een gevuld concept en een e-mailadres."""
    r = httpx.post(f"{NOTION_API}/databases/{DB_ID}/query", headers=_notion_headers(),
                    json={"page_size": 100}, timeout=20)
    r.raise_for_status()
    gevonden = []
    for row in r.json().get("results", []):
        p = row["properties"]
        status = (p.get("Status", {}).get("select") or {}).get("name")
        if status != "Nieuw":
            continue
        concept = "".join(t.get("plain_text", "") for t in p.get("Concept bericht", {}).get("rich_text", []))
        email = p.get("E-mail", {}).get("email")
        naam = ""
        for _, val in p.items():
            if val["type"] == "title":
                naam = "".join(t.get("plain_text", "") for t in val["title"])
        if concept.strip() and email:
            gevonden.append({"id": row["id"], "naam": naam, "email": email, "concept": concept})
    return gevonden


def _verstuur(email: str, tekst: str) -> None:
    context = ssl.create_default_context()
    msg = MIMEText(tekst, "plain", "utf-8")
    msg["Subject"] = SUBJECT
    msg["From"] = f"Daniel <{MAIL_USER}>"
    msg["To"] = email
    with smtplib.SMTP_SSL(MAIL_HOST, 465, context=context) as smtp:
        smtp.login(MAIL_USER, _need("MAIL_PASS"))
        smtp.sendmail(MAIL_USER, [email], msg.as_string())


def _bijwerken(page_id: str, vandaag: str) -> None:
    props = {
        "Status": {"select": {"name": "Benaderd"}},
        "Benaderd op": {"date": {"start": vandaag}},
        "Kanaal": {"select": {"name": "E-mail"}},
    }
    r = httpx.patch(f"{NOTION_API}/pages/{page_id}", headers=_notion_headers(),
                     json={"properties": props}, timeout=20)
    r.raise_for_status()
    logregel = f"{vandaag} — Mail verstuurd vanaf {MAIL_USER} (Zoho), automatisch door leadgen_creators_mail.py."
    r2 = httpx.patch(f"{NOTION_API}/blocks/{page_id}/children", headers=_notion_headers(),
                      json={"children": [{
                          "object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": [{"type": "text", "text": {"content": logregel}}]},
                      }]}, timeout=20)
    r2.raise_for_status()


def run(limit: int, dry_run: bool) -> None:
    vandaag = datetime.date.today().isoformat()
    rijen = _klaarstaande_rijen()
    print(f"{len(rijen)} rij(en) met Status Nieuw + concept klaar + e-mailadres.")
    for rij in rijen[:limit]:
        if dry_run:
            print(f"  [dry-run] zou versturen naar {rij['naam']} <{rij['email']}>")
            continue
        _verstuur(rij["email"], rij["concept"])
        _bijwerken(rij["id"], vandaag)
        print(f"  verstuurd naar {rij['naam']} <{rij['email']}> en bijgewerkt in Notion")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("opdracht", choices=["run"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)
