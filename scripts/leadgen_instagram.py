#!/usr/bin/env python3
"""
Leadgen voor de Instagram-outreach van Omnivaleur.

HET PROBLEEM
Zoeken op hashtags (#vinted, #tweedehands) levert vooral kopers, reviewers,
haul-accounts en buitenlandse verkopers. Die hashtag zegt "ik heb iets met
tweedehands", niet "ik verkoop serieus en heb last van crosslisten".

WAT WEL WERKT — en wat ik eerst heb geprobeerd (2026-07, alles live getest)
  * Vinted als bron: ONBRUIKBAAR. Zit achter Cloudflare en weigert datacenter-IP's;
    drie verschillende Apify Vinted-actors gaven allemaal nul resultaten.
  * Marktplaats als bron: de scrape werkt prima, maar er is GEEN brug naar Instagram.
    Handles raden uit de winkelnaam gaf 4 treffers op 13 gokken, en de enige echte
    match was een verzamelaar uit Tokio. Advertentieteksten noemen ook niets:
    0 van 53 beschrijvingen bevatte een @handle of instagram-link.
  * Instagram keyword-discovery met Nederlandse zoektermen: WERKT. Levert direct
    tweedehandskleding.nl, kringloopenclave, thriftshopnl — precies de doelgroep.

Vandaar deze trechter:
  discover  Instagram-accounts vinden op Nederlandse zoektermen (Apify)
  classify  Haiku beoordeelt: verkoper of consument/reviewer? + Notion-veldwaardes
  push      als lead in de Notion-Leadlist zetten, status "Reach out"

Elke stap schrijft naar scripts/output/leads/ en leest de vorige van schijf, zodat
je een dure stap nooit twee keer draait en tussendoor met de hand kunt controleren.

DIT SCRIPT VERSTUURT NIETS. De officiële Instagram-API staat koude DM's niet toe
(alleen antwoorden binnen 24 uur nadat iemand jou schrijft), en tools die het toch
doen worden gedetecteerd — met je eigen merkaccount als inzet. Alles tot en met de
kant-en-klare tekst is geautomatiseerd, op de verzendknop na.

LET OP: keyword-discovery is op een gratis Apify-account gelimiteerd tot 5
kandidaten per run. Voor serieuze volumes is een betaald Apify-plan nodig.

Gebruik:
    export APIFY_TOKEN=... NOTION_TOKEN=...
    python3 scripts/leadgen_instagram.py discover --max 40
    python3 scripts/leadgen_instagram.py classify
    python3 scripts/leadgen_instagram.py push --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent / "output" / "leads"
CANDIDATES = OUT / "candidates.json"
LEADS = OUT / "leads.json"

APIFY_SYNC = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
IG_DISCOVERY = "afanasenko~instagram-profile-scraper"

NOTION_DB = "399b0954-fb72-8053-a8fc-fa7c21616371"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Nederlandstalige zoektermen zijn zelf al het landfilter: wie zijn winkel
# "kringloop" of "tweedehands kleding" noemt zit in NL/BE. Engelse termen als
# "thrift" halen de halve wereld binnen en horen hier dus niet los in thuis.
QUERIES = [
    "vintage kleding", "tweedehands kleding", "kringloop", "kringloopwinkel",
    "vintage winkel", "tweedehands winkel", "vintage shop nederland",
    "thriftshop nl", "vintage meubels", "brocante", "curiosa",
    "preloved kleding", "vintage sieraden", "retro winkel",
]


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


# ---------------------------------------------------------------- discover


def discover(args) -> None:
    token = _need("APIFY_TOKEN")
    import httpx

    payload = {
        "operationMode": "keywordDiscovery",
        "searchQueries": args.queries or QUERIES,
        "maxCountDiscovery": args.max,
        "maxSearchPagesPerQuery": 3,
        "extractEmail": True,
        # Kandidaten die al in Notion staan worden hier al weggegooid vóórdat ze
        # geanalyseerd (en dus betaald) worden.
        "excludeAccounts": _existing_handles_or_empty(),
        "clearSavedData": True,
    }
    print(f"{len(payload['searchQueries'])} zoektermen, max {args.max} kandidaten…")

    r = httpx.post(APIFY_SYNC.format(actor=IG_DISCOVERY),
                   params={"token": token}, json=payload, timeout=900.0)
    if r.status_code >= 400:
        sys.exit(f"Apify gaf HTTP {r.status_code}: {r.text[:300]}")
    rows = r.json() or []

    OUT.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\n{len(rows)} kandidaten → {CANDIDATES}")
    for row in rows[:20]:
        print(f"  {_handle(row):28s} {row.get('Followers Count', 0):>7} volgers  "
              f"{(row.get('Full Name') or '')[:34]}")
    if len(rows) <= 5:
        print("\nLET OP: 5 of minder resultaten wijst op de gratis-plan-limiet "
              "van Apify (5 kandidaten per run bij keyword-discovery).")


def _handle(row: dict) -> str:
    """De actor geeft een profiel-URL terug, niet de losse handle."""
    return (row.get("Account") or "").rstrip("/").rsplit("/", 1)[-1].lower()


def _existing_handles_or_empty() -> list[str]:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        return []
    try:
        return [u.rstrip("/").rsplit("/", 1)[-1] for u in _existing_urls(token)]
    except Exception:  # noqa: BLE001 — dedupe is een optimalisatie, geen vereiste
        return []


# ---------------------------------------------------------------- classify


PROMPT = """Je beoordeelt of een Instagram-account een goede lead is voor Omnivaleur,
een tool waarmee tweedehands-verkopers hun advertenties in één keer op Marktplaats,
2dehands, Vinted, eBay en Shopify zetten.

Een GOEDE lead verkoopt zelf structureel tweedehands, vintage of kringloopspullen:
een winkel, een reseller, een thriftshop-account, een vintage-webshop.
Een SLECHTE lead is een consument, een koper, een reviewer of haul-account, een
influencer, een merk dat nieuw verkoopt, of een account dat alleen in het buitenland
verkoopt en niets met Nederland of België te maken heeft.

Account:
  @{handle} — {full_name}
  volgers: {followers}, posts: {posts}
  bio: {bio}
  website: {url}
  categorie: {category}
  e-mail: {email}

Antwoord met UITSLUITEND JSON:
{{"is_lead": true/false,
  "confidence": 0-100,
  "reden": "één zin, Nederlands",
  "verkoopt_vooral": "Kleding|Meubilair|Alles|Antieke vintage|Hoogwaardige vintage|Vintage jewelry|Vintage interieur|Sieraden|Knutselmaterialen",
  "verkoop_op": "Eigen website|Fysieke winkel|Marktplaats|Instagram|Vinted|Onbekend|Vinted en eigen website",
  "je_jullie": "Je|Jullie",
  "language": "NL|EN"}}"""


def classify(args) -> None:
    if not CANDIDATES.exists():
        sys.exit("Nog geen candidates.json — draai eerst 'discover'")

    import anthropic
    from backend.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    rows = json.loads(CANDIDATES.read_text())
    leads = []

    for i, row in enumerate(rows, 1):
        handle = _handle(row)
        if not handle:
            continue
        prompt = PROMPT.format(
            handle=handle,
            full_name=row.get("Full Name") or "(leeg)",
            followers=row.get("Followers Count") or 0,
            posts=row.get("Total Posts") or 0,
            bio=row.get("Biography") or "(leeg)",
            url=_clean(row.get("External URL")),
            category=_clean(row.get("Category")),
            email=_clean(row.get("Email")),
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            verdict = json.loads(
                re.search(r"\{.*\}", resp.content[0].text, re.S).group(0))
        except Exception as e:  # noqa: BLE001
            print(f"  ! @{handle}: {e}")
            continue

        keep = verdict.get("is_lead") and verdict.get("confidence", 0) >= args.min_confidence
        print(f"[{i}/{len(rows)}] {'✓' if keep else '·'} @{handle:28s} "
              f"{verdict.get('reden', '')[:62]}")
        if keep:
            leads.append({
                "handle": handle,
                "ig_url": f"https://www.instagram.com/{handle}/",
                "full_name": row.get("Full Name") or "",
                "followers": row.get("Followers Count") or 0,
                "bio": row.get("Biography") or "",
                "email": _clean(row.get("Email")),
                "website": _clean(row.get("External URL")),
                **verdict,
            })

    OUT.mkdir(parents=True, exist_ok=True)
    LEADS.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
    print(f"\n{len(leads)} van {len(rows)} accounts gekwalificeerd → {LEADS}")


def _clean(v) -> str:
    """De actor schrijft letterlijk "N/A" in lege velden; dat is voor een prompt
    misleidender dan gewoon niets."""
    return "" if v in (None, "N/A", "") else str(v)


# ---------------------------------------------------------------- push


def _notion(method: str, path: str, token: str, body: dict | None = None) -> dict:
    import httpx

    r = httpx.request(
        method, f"{NOTION_API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json=body, timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def _existing_urls(token: str) -> set[str]:
    """Wat al in de Leadlist staat, ook handmatig toegevoegd. Zonder deze check
    krijgt iemand bij een tweede run een tweede DM."""
    urls: set[str] = set()
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _notion("POST", f"/databases/{NOTION_DB}/query", token, body)
        for page in data.get("results", []):
            url = (page.get("properties", {}).get("URL") or {}).get("url")
            if url:
                urls.add(url.rstrip("/").lower())
        if not data.get("has_more"):
            return urls
        cursor = data["next_cursor"]


def push(args) -> None:
    if not LEADS.exists():
        sys.exit("Nog geen leads.json — draai eerst 'classify'")

    leads = json.loads(LEADS.read_text())
    if args.dry_run:
        print(f"{len(leads)} leads klaar (dry-run, er wordt niets weggeschreven):\n")
        for l in leads:
            print(f"  @{l['handle']:28s} {l['followers']:>7} volgers  "
                  f"{l.get('verkoopt_vooral', '')}")
            print(f"     {l.get('reden', '')}")
        return

    token = _need("NOTION_TOKEN")
    seen = _existing_urls(token)
    print(f"{len(seen)} bestaande leads in Notion, die sla ik over")

    created = skipped = 0
    for l in leads:
        if l["ig_url"].rstrip("/").lower() in seen:
            skipped += 1
            continue
        notes = " · ".join(x for x in [
            f"{l['followers']} volgers",
            l.get("website"),
            l.get("email"),
            l.get("reden"),
        ] if x)
        props = {
            "Name": {"title": [{"text": {"content": l["full_name"] or l["handle"]}}]},
            "URL": {"url": l["ig_url"]},
            "Platform": {"select": {"name": "IG"}},
            "Language": {"select": {"name": l.get("language", "NL")}},
            "Status": {"status": {"name": "Reach out"}},
            "Je/Jullie": {"select": {"name": l.get("je_jullie", "Je")}},
            "Notes (Optional)": {"rich_text": [{"text": {"content": notes[:1900]}}]},
        }
        for key, prop in (("verkoopt_vooral", "Verkoopt vooral..."),
                          ("verkoop_op", "Verkoop op...")):
            if l.get(key):
                props[prop] = {"select": {"name": l[key]}}
        try:
            _notion("POST", "/pages", token,
                    {"parent": {"database_id": NOTION_DB}, "properties": props})
            created += 1
            print(f"  + @{l['handle']}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! @{l['handle']}: {e}")

    print(f"\n{created} leads toegevoegd, {skipped} bestonden al.")
    print("De AI-autofill in Notion schrijft de outreach-tekst zelf. "
          "Versturen doe je met de hand — zie de kop van dit bestand.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="Instagram-accounts zoeken op NL-termen")
    d.add_argument("--max", type=int, default=40, help="kostenplafond in kandidaten")
    d.add_argument("--queries", nargs="*", help="eigen zoektermen i.p.v. de standaardlijst")
    d.set_defaults(func=discover)

    c = sub.add_parser("classify", help="Haiku beoordeelt verkoper vs consument")
    c.add_argument("--min-confidence", type=int, default=60)
    c.set_defaults(func=classify)

    p = sub.add_parser("push", help="naar de Notion-Leadlist")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=push)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
