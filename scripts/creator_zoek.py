#!/usr/bin/env python3.13
"""Zoekt Nederlandse creators die open staan voor samenwerking en een zakelijk e-mailadres in hun
bio hebben. Bron: alleen de zoekresultaten van Google (Serper), dus de bio-tekst zoals Google die
toont. Er wordt geen Instagram-profiel of -post zelf opgehaald of gescrapet.

  python3.13 scripts/creator_zoek.py            zoekt en schrijft data/creator_outreach/kandidaten.csv

Sleutel: SERPER_API_KEY in de omgeving, anders ~/.omnivaleur/serper-sleutel.txt (buiten de repo).
Een e-mailadres komt alleen in de lijst als het letterlijk in de zoekresultaat-tekst staat.
Niets wordt verstuurd; de lijst is de input voor een mens of voor de standaardmail."""
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UIT = ROOT / "data" / "creator_outreach" / "kandidaten.csv"
LOG = ROOT / "data" / "creator_outreach" / "instagram.csv"
KOP = ["handle", "bio", "email", "zoekterm"]
ZOEKTERMEN = [
    'site:instagram.com ugc creator nederland email samenwerking',
    'site:instagram.com ugc creator nederland "zakelijk" email',
    'site:instagram.com creator nederland "samenwerkingen" email bio',
    'site:instagram.com ugc creator nederland "contact" "@" samenwerken',
    'site:instagram.com nederlandse content creator "collabs" email',
    'ugc creator nederland instagram bio "email" samenwerking',
    'nederlandse ugc creator instagram "zakelijk" "@" bio',
    'instagram ugc creator nl "samenwerkingen" "info@" OR "contact@"',
]
PROFIEL = re.compile(r"^https://www\.instagram\.com/([A-Za-z0-9._]+)/?$")
MAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def sleutel() -> str:
    if os.environ.get("SERPER_API_KEY"):
        return os.environ["SERPER_API_KEY"].strip()
    pad = Path.home() / ".omnivaleur" / "serper-sleutel.txt"
    if pad.exists():
        return pad.read_text().strip()
    raise RuntimeError("Geen Serper-sleutel: zet SERPER_API_KEY of ~/.omnivaleur/serper-sleutel.txt")


def zoek(term: str, key: str) -> list[dict]:
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": term, "gl": "nl", "hl": "nl", "num": 10}).encode(),
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("organic", [])


def bekende_handles() -> set[str]:
    if not LOG.exists():
        return set()
    with LOG.open(newline="") as f:
        return {r["handle"].lower() for r in csv.DictReader(f)}


def run() -> int:
    key = sleutel()
    bekend = bekende_handles()
    gevonden: dict[str, dict] = {}
    for term in ZOEKTERMEN:
        try:
            hits = zoek(term, key)
        except urllib.error.HTTPError as fout:
            print(f"Zoekterm overgeslagen (HTTP {fout.code}): {term}", file=sys.stderr)
            continue
        for hit in hits:
            m = PROFIEL.match(hit.get("link", ""))
            if not m:
                continue  # alleen profielpagina's, geen posts of reels
            handle = m.group(1).lower()
            if handle in bekend or handle in gevonden:
                continue
            tekst = f"{hit.get('title', '')} {hit.get('snippet', '')}"
            mails = sorted(set(MAIL.findall(tekst)))
            if not mails:
                continue  # geen e-mail in de bio-tekst, dan niet bruikbaar
            gevonden[handle] = {"handle": handle, "bio": hit.get("snippet", "").strip(),
                                "email": mails[0], "zoekterm": term}
    UIT.parent.mkdir(parents=True, exist_ok=True)
    with UIT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOP)
        w.writeheader()
        w.writerows(gevonden.values())
    print(f"{len(gevonden)} kandidaten met e-mail in de bio-tekst -> {UIT}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
