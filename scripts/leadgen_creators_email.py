#!/usr/bin/env python3
"""
Zoekt e-mailadressen voor creators in de Notion-database "Creator Outreach
(TikTok)" die er nog geen hebben, door hun TikTok-bio te lezen. Vult NOOIT
iets anders in dan een e-mailadres dat letterlijk in de bio staat — er wordt
niets over de persoon of hun content verzonnen (zie leadgen_creators_mail.py
voor waarom dat een bewezen risico is).

HOE
    TikTok rendert de bio ("signature") server-side in een JSON-blok
    (__UNIVERSAL_DATA_FOR_REHYDRATION__) dat een gewone HTTP GET al
    binnenhaalt — geen browser of login nodig. Een e-mailregex op die tekst
    vindt exact wat een mens ook zou zien staan (bijv. Cecile's bio:
    "💌cecilevindthet@gmail.com").

Gebruik:
    export NOTION_TOKEN=...
    python3 scripts/leadgen_creators_email.py run              # echt bijwerken
    python3 scripts/leadgen_creators_email.py run --dry-run    # alleen tonen
"""
from __future__ import annotations

import argparse
import json
import re
import time

import httpx

DB_ID = "b49ee78e-8c0e-418e-b516-4a432753b499"  # Creator Outreach (TikTok)
NOTION_API = "https://api.notion.com/v1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _need(naam: str) -> str:
    import os
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


def _zonder_email() -> list[dict]:
    r = httpx.post(f"{NOTION_API}/databases/{DB_ID}/query", headers=_notion_headers(),
                    json={"page_size": 100}, timeout=20)
    r.raise_for_status()
    gevonden = []
    for row in r.json().get("results", []):
        p = row["properties"]
        status = (p.get("Status", {}).get("select") or {}).get("name")
        email = p.get("E-mail", {}).get("email")
        tiktok_url = p.get("TikTok", {}).get("url")
        naam = ""
        for _, val in p.items():
            if val["type"] == "title":
                naam = "".join(t.get("plain_text", "") for t in val["title"])
        if status == "Nieuw" and not email and tiktok_url:
            gevonden.append({"id": row["id"], "naam": naam, "tiktok_url": tiktok_url})
    return gevonden


def _bio(tiktok_url: str) -> str | None:
    """Leest de bio-tekst van een TikTok-profiel. None bij een mislukte poging."""
    try:
        r = httpx.get(tiktok_url, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        return data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["user"].get("signature", "")
    except (KeyError, json.JSONDecodeError):
        return None


def _zet_email(page_id: str, email: str, bron: str) -> None:
    r = httpx.patch(f"{NOTION_API}/pages/{page_id}", headers=_notion_headers(),
                     json={"properties": {"E-mail": {"email": email}}}, timeout=20)
    r.raise_for_status()
    logregel = f"E-mailadres gevonden in TikTok-bio ({bron}), automatisch door leadgen_creators_email.py."
    r2 = httpx.patch(f"{NOTION_API}/blocks/{page_id}/children", headers=_notion_headers(),
                      json={"children": [{
                          "object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": [{"type": "text", "text": {"content": logregel}}]},
                      }]}, timeout=20)
    r2.raise_for_status()


def run(dry_run: bool) -> None:
    rijen = _zonder_email()
    print(f"{len(rijen)} creator(s) zonder e-mailadres met een TikTok-link.")
    gevonden = 0
    niet_gevonden = 0
    for rij in rijen:
        bio = _bio(rij["tiktok_url"])
        if bio is None:
            print(f"  ? {rij['naam']}: profiel niet te lezen ({rij['tiktok_url']})")
            niet_gevonden += 1
            time.sleep(1.5)
            continue
        match = EMAIL_RE.search(bio)
        if not match:
            print(f"  - {rij['naam']}: geen e-mailadres in bio")
            niet_gevonden += 1
        else:
            email = match.group(0)
            print(f"  + {rij['naam']}: {email}" + (" [dry-run]" if dry_run else ""))
            if not dry_run:
                _zet_email(rij["id"], email, bio.strip()[:80])
            gevonden += 1
        time.sleep(1.5)
    print(f"\nGevonden: {gevonden}, niet gevonden: {niet_gevonden}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("opdracht", choices=["run"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
