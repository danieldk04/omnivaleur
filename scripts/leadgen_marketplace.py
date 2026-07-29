#!/usr/bin/env python3
"""
Leadgen voor Instagram-outreach, gevoed vanuit de marketplace in plaats van vanuit
Instagram zelf.

WAAROM ANDERSOM
Zoeken op Instagram (#vinted, #tweedehands) levert per definitie een mengelmoes:
kopers, reviewers, haul-accounts, buitenlandse verkopers. Die hashtag zegt "ik heb
iets met tweedehands", niet "ik verkoop serieus en heb last van crosslisten".
Marktplaats zegt dat laatste wel — iemand met 20 actieve advertenties in Nederland
IS aantoonbaar een serieuze verkoper. We beginnen dus daar en zoeken pas daarna het
Instagram-account erbij.

WAAROM NIET VINTED ALS BRON
Vinted zit achter Cloudflare en weigert datacenter-IP's. Drie verschillende Apify
Vinted-actors gaven allemaal nul resultaten (2026-07, live getest), terwijl de
Marktplaats-actor gewoon 100% werkt. Marktplaats is bovendien NL/BE per definitie,
wat het "buitenlandse verkopers"-probleem in de bron oplost in plaats van achteraf.

DE TRECHTER
  harvest   Marktplaats-advertenties oogsten (Apify)
  rank      groeperen per verkoper; alleen wie ≥MIN_LISTINGS advertenties heeft
  enrich    Instagram-handle raden uit de winkelnaam en verifiëren (Apify)
  classify  Haiku beoordeelt: reseller of consument? + Notion-veldwaardes
  push      als lead in de Notion-Leadlist zetten, status "Reach out"

Elke stap schrijft naar scripts/output/leads/ en leest de vorige stap van schijf,
zodat je een dure stap nooit twee keer hoeft te draaien en tussentijds met de hand
kunt kijken of de kwaliteit klopt.

Dit script VERSTUURT NIETS. Instagram staat koude DM's via de officiële API niet toe
en detecteert automatisering agressief; het risico ligt bij je eigen merkaccount.
Alles tot en met de kant-en-klare tekst is geautomatiseerd, op verzenden na.

Gebruik:
    export APIFY_TOKEN=... NOTION_TOKEN=...
    python3 scripts/leadgen_marketplace.py harvest --max-per-source 200
    python3 scripts/leadgen_marketplace.py rank
    python3 scripts/leadgen_marketplace.py enrich
    python3 scripts/leadgen_marketplace.py classify
    python3 scripts/leadgen_marketplace.py push --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

OUT = Path(__file__).parent / "output" / "leads"
LISTINGS = OUT / "listings.jsonl"
SELLERS = OUT / "sellers.json"
ENRICHED = OUT / "instagram.json"
LEADS = OUT / "leads.json"

APIFY_SYNC = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
MP_ACTOR = "haketa~marktplaats-scraper"
IG_ACTOR = "figue~instagram-profile-scraper"

NOTION_DB = "399b0954-fb72-8053-a8fc-fa7c21616371"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Alleen categorie-ID's die LIVE resultaten teruggaven. De actor accepteert er meer
# in zijn enum, maar 92/135/1100/1525/2017/380/367/33/34 geven stil nul items terug —
# een geaccepteerde input is hier geen bewijs dat de categorie bestaat.
SOURCES = [
    {"label": "Kleding | Dames", "category": "621"},
    {"label": "Huis en Inrichting", "category": "504"},
    {"label": "Hobby en Vrije Tijd", "category": "1099"},
    # Trefwoorden vangen wat buiten die categorieën valt. Let op: een los woord als
    # "vintage" matcht ook kapsalons en autogarages, dus altijd met een productwoord.
    {"label": "vintage kleding", "query": "vintage kleding"},
    {"label": "vintage jas", "query": "vintage jas"},
    {"label": "designer tas", "query": "designer tas"},
    {"label": "partij kleding", "query": "partij kleding"},
    {"label": "vintage meubel", "query": "vintage meubel"},
]

MIN_LISTINGS = 4        # onder dit aantal is iemand een opruimer, geen verkoper
MAX_SELLERS_TO_ENRICH = 150

# Winkelsignalen in de verkopersnaam. "Tho Ber" of "A Vos" is een particulier die
# zijn zolder opruimt; "decotrends vintage living" is een merk — en alleen zo iemand
# heeft überhaupt een Instagram om te benaderen. Dit filter kost dekking en levert
# precisie op, en dat is hier de goede ruil.
SHOP_WORDS = {
    "vintage", "store", "shop", "winkel", "boutique", "kringloop", "brocante",
    "curiosa", "thrift", "closet", "wardrobe", "collect", "retro", "atelier",
    "concept", "studio", "living", "interior", "interieur", "fashion", "mode",
    "kleding", "sieraden", "jewelry", "antiek", "design", "label", "the", "by",
}


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


def _apify(actor: str, payload: dict, token: str, timeout: float = 300.0) -> list[dict]:
    """Draai een actor en geef de dataset terug. Faalt zacht naar een lege lijst:
    één kapotte bron mag een harvest over acht bronnen niet slopen."""
    import httpx

    try:
        r = httpx.post(
            APIFY_SYNC.format(actor=actor),
            params={"token": token},
            json=payload,
            timeout=timeout,
        )
        if r.status_code >= 400:
            print(f"  ! actor {actor} gaf HTTP {r.status_code}: {r.text[:200]}")
            return []
        return r.json() or []
    except Exception as e:  # noqa: BLE001
        print(f"  ! actor {actor} faalde: {e}")
        return []


# ---------------------------------------------------------------- harvest


def harvest(args) -> None:
    token = _need("APIFY_TOKEN")
    OUT.mkdir(parents=True, exist_ok=True)

    # Hervatten na een onderbroken run: al geoogste advertenties overslaan in plaats
    # van opnieuw betalen.
    seen: set[str] = set()
    if LISTINGS.exists() and not args.fresh:
        with LISTINGS.open() as f:
            seen = {json.loads(line).get("listingId") for line in f if line.strip()}
        print(f"{len(seen)} advertenties al geoogst, die sla ik over")
    elif args.fresh:
        LISTINGS.unlink(missing_ok=True)

    written = 0
    with LISTINGS.open("a") as f:
        for src in SOURCES:
            payload = {
                "platform": "marktplaats.nl",
                "sellerTypeFilter": "private",
                "maxListings": args.max_per_source,
                "scrapeDetails": False,
                "sortBy": "SORT_INDEX",
                "sortOrder": "DECREASING",
            }
            if src.get("category"):
                payload["category"] = src["category"]
            if src.get("query"):
                payload["query"] = src["query"]

            print(f"[{src['label']}] oogsten…", flush=True)
            rows = _apify(MP_ACTOR, payload, token)
            new = 0
            for row in rows:
                lid = row.get("listingId")
                if not lid or lid in seen:
                    continue
                seen.add(lid)
                f.write(json.dumps({
                    "listingId": lid,
                    "title": row.get("title"),
                    "price": row.get("price"),
                    "sellerName": row.get("sellerName"),
                    "sellerId": str(row.get("sellerId") or ""),
                    "location": row.get("location"),
                    "url": row.get("url"),
                    "date": row.get("date"),
                    "source": src["label"],
                }, ensure_ascii=False) + "\n")
                new += 1
            written += new
            print(f"  {len(rows)} advertenties, {new} nieuw")

    print(f"\n{written} nieuwe advertenties → {LISTINGS}")


# ---------------------------------------------------------------- rank


def _category_from_url(url: str) -> str:
    """De categorie zit betrouwbaar in het URL-pad; het losse `category`-veld van de
    actor is vaak leeg."""
    m = re.search(r"marktplaats\.nl/v/([^/]+)/", url or "")
    return m.group(1).replace("-", " ") if m else ""


def _looks_like_shop(name: str) -> bool:
    """Een eerste versie hiervan liet "M." en "Larissa & Ton" door, op niet meer dan
    'bevat een punt' en 'bestaat uit drie woorden'. Dat zijn particulieren die hun
    kast leegruimen, precies het soort lead waar we vanaf willen. Nu is een expliciet
    winkelwoord de enige echte ingang, en telt lengte alleen mee als er geen
    persoonsnaam-patroon in zit."""
    clean = (name or "").strip()
    if len(clean) < 4:
        return False
    words = [w for w in re.split(r"[\s._&-]+", clean.lower()) if w]
    if any(w in SHOP_WORDS for w in words):
        return True
    # "Larissa & Ton" of "Jan de Vries": voornamen aan elkaar geplakt met een
    # koppelwoord is een mens, geen merk.
    if re.search(r"\s(&|en|de|van|der|den)\s", clean.lower()):
        return False
    return len(words) >= 3


def rank(args) -> None:
    if not LISTINGS.exists():
        sys.exit("Nog geen listings.jsonl — draai eerst 'harvest'")

    by_seller: dict[str, dict] = defaultdict(
        lambda: {"listings": [], "categories": set(), "locations": set()})
    with LISTINGS.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            sid = row.get("sellerId")
            if not sid:
                continue
            s = by_seller[sid]
            s["sellerId"] = sid
            s["sellerName"] = row.get("sellerName") or ""
            s["listings"].append({"title": row.get("title"), "price": row.get("price")})
            s["categories"].add(_category_from_url(row.get("url", "")))
            if row.get("location"):
                s["locations"].add(row["location"])

    sellers = []
    for s in by_seller.values():
        prices = [p["price"] for p in s["listings"] if isinstance(p.get("price"), (int, float)) and p["price"] > 0]
        sellers.append({
            "sellerId": s["sellerId"],
            "sellerName": s["sellerName"],
            "listing_count": len(s["listings"]),
            "categories": sorted(c for c in s["categories"] if c),
            "location": sorted(s["locations"])[0] if s["locations"] else "",
            "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
            "sample_titles": [p["title"] for p in s["listings"][:8] if p.get("title")],
            "shop_name": _looks_like_shop(s["sellerName"]),
        })

    qualified = [s for s in sellers
                 if s["listing_count"] >= args.min_listings and s["shop_name"]]
    qualified.sort(key=lambda s: s["listing_count"], reverse=True)

    OUT.mkdir(parents=True, exist_ok=True)
    SELLERS.write_text(json.dumps(qualified, indent=2, ensure_ascii=False))

    volume = sum(1 for s in sellers if s["listing_count"] >= args.min_listings)
    print(f"{len(sellers)} verkopers gezien")
    print(f"  {volume} met ≥{args.min_listings} advertenties")
    print(f"  {len(qualified)} daarvan met een winkelachtige naam → {SELLERS}")
    for s in qualified[:15]:
        print(f"    {s['listing_count']:3d}x  {s['sellerName'][:38]:38s}  {s['location']}")


# ---------------------------------------------------------------- enrich


def _handle_candidates(name: str) -> list[str]:
    """Winkelnaam → mogelijke Instagram-handles. Instagram staat alleen letters,
    cijfers, punt en underscore toe, max 30 tekens."""
    base = re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()
    if not base:
        return []
    parts = base.split()
    out = ["".join(parts), ".".join(parts), "_".join(parts)]
    if len(parts) > 2:                          # vaak korten mensen af tot 2 woorden
        out.append("".join(parts[:2]))
    return [h for h in dict.fromkeys(out) if 3 <= len(h) <= 30]


def enrich(args) -> None:
    token = _need("APIFY_TOKEN")
    if not SELLERS.exists():
        sys.exit("Nog geen sellers.json — draai eerst 'rank'")

    sellers = json.loads(SELLERS.read_text())[: args.limit]
    candidates: dict[str, dict] = {}
    for s in sellers:
        for h in _handle_candidates(s["sellerName"]):
            candidates.setdefault(h, s)

    print(f"{len(sellers)} verkopers → {len(candidates)} handle-gokken te verifiëren")
    if args.dry_run:
        for h, s in list(candidates.items())[:25]:
            print(f"  {h:32s} ← {s['sellerName']}")
        return

    handles = list(candidates)
    found: dict[str, dict] = {}
    for i in range(0, len(handles), 50):
        batch = handles[i: i + 50]
        print(f"  batch {i // 50 + 1} ({len(batch)} handles)…", flush=True)
        rows = _apify(IG_ACTOR, {"profiles": batch, "includeRecentPosts": True}, token)
        for row in rows:
            handle = (row.get("username") or row.get("ownerUsername") or "").lower()
            if not handle or handle in found:
                continue
            seller = candidates.get(handle)
            if not seller:
                continue
            found[handle] = {
                **seller,
                "ig_handle": handle,
                "ig_url": f"https://www.instagram.com/{handle}/",
                "ig_name": row.get("fullName") or row.get("full_name") or "",
                "ig_bio": row.get("biography") or row.get("bio") or "",
                "ig_followers": row.get("followersCount") or row.get("followers") or 0,
                "ig_posts": row.get("postsCount") or row.get("posts_count") or 0,
                "ig_link": row.get("externalUrl") or row.get("external_url") or "",
                "ig_private": bool(row.get("private") or row.get("isPrivate")),
                "ig_captions": [
                    (p.get("caption") or "")[:280]
                    for p in (row.get("latestPosts") or row.get("recentPosts") or [])[:6]
                ],
            }
        time.sleep(1)

    hits = [v for v in found.values() if not v["ig_private"]]
    ENRICHED.write_text(json.dumps(hits, indent=2, ensure_ascii=False))
    print(f"\n{len(hits)} publieke Instagram-accounts gevonden → {ENRICHED}")


# ---------------------------------------------------------------- classify


PROMPT = """Je beoordeelt of een Instagram-account een goede lead is voor Omnivaleur,
een tool waarmee tweedehands-verkopers hun advertenties in één keer op Marktplaats,
2dehands, Vinted, eBay en Shopify zetten.

Een GOEDE lead verkoopt zelf structureel tweedehands of vintage spullen: een
kringloop-, vintage- of conceptwinkel, een reseller, een thriftshop-account.
Een SLECHTE lead is een consument, een koper, een reviewer/haul-account, een
influencer, een merk dat nieuw verkoopt, of iets zonder verband met tweedehands.

Marktplaats-gegevens (bewezen verkoopactiviteit):
  naam: {sellerName}
  actieve advertenties gezien: {listing_count}
  categorieën: {categories}
  plaats: {location}
  voorbeelden: {sample_titles}

Instagram:
  @{ig_handle} — {ig_name}
  volgers: {ig_followers}, posts: {ig_posts}
  bio: {ig_bio}
  link: {ig_link}
  recente bijschriften: {ig_captions}

Antwoord met UITSLUITEND JSON:
{{"is_lead": true/false,
  "confidence": 0-100,
  "reden": "één zin, Nederlands",
  "verkoopt_vooral": "Kleding|Meubilair|Alles|Antieke vintage|Hoogwaardige vintage|Vintage jewelry|Vintage interieur|Sieraden|Knutselmaterialen",
  "je_jullie": "Je|Jullie",
  "language": "NL|EN"}}"""


def classify(args) -> None:
    if not ENRICHED.exists():
        sys.exit("Nog geen instagram.json — draai eerst 'enrich'")

    import anthropic
    from backend.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    rows = json.loads(ENRICHED.read_text())
    leads = []

    for i, row in enumerate(rows, 1):
        prompt = PROMPT.format(
            sellerName=row["sellerName"],
            listing_count=row["listing_count"],
            categories=", ".join(row["categories"]) or "onbekend",
            location=row["location"] or "onbekend",
            sample_titles=" | ".join(row["sample_titles"][:6]),
            ig_handle=row["ig_handle"],
            ig_name=row["ig_name"],
            ig_followers=row["ig_followers"],
            ig_posts=row["ig_posts"],
            ig_bio=row["ig_bio"] or "(leeg)",
            ig_link=row["ig_link"] or "(geen)",
            ig_captions=" | ".join(row["ig_captions"]) or "(geen)",
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            verdict = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        except Exception as e:  # noqa: BLE001
            print(f"  ! {row['ig_handle']}: {e}")
            continue

        mark = "✓" if verdict.get("is_lead") else "·"
        print(f"[{i}/{len(rows)}] {mark} @{row['ig_handle']:28s} {verdict.get('reden', '')[:60]}")
        if verdict.get("is_lead") and verdict.get("confidence", 0) >= args.min_confidence:
            leads.append({**row, **verdict})

    LEADS.write_text(json.dumps(leads, indent=2, ensure_ascii=False))
    print(f"\n{len(leads)} van {len(rows)} accounts gekwalificeerd → {LEADS}")


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
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _notion("POST", f"/databases/{NOTION_DB}/query", token, body)
        for page in data.get("results", []):
            prop = page.get("properties", {}).get("URL", {})
            if prop.get("url"):
                urls.add(prop["url"].rstrip("/").lower())
        if not data.get("has_more"):
            return urls
        cursor = data["next_cursor"]


def push(args) -> None:
    if not LEADS.exists():
        sys.exit("Nog geen leads.json — draai eerst 'classify'")

    leads = json.loads(LEADS.read_text())
    if args.dry_run:
        print(f"{len(leads)} leads klaar (dry-run, niets weggeschreven):\n")
        for l in leads:
            print(f"  @{l['ig_handle']:28s} {l['ig_followers']:>7} volgers  "
                  f"{l['listing_count']:3d} adv.  {l.get('verkoopt_vooral', '')}")
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
        notes = (f"{l['listing_count']} actieve MP-advertenties · "
                 f"{l['location']} · {', '.join(l['categories'][:3])} · "
                 f"{l['ig_followers']} volgers. {l.get('reden', '')}")
        props = {
            "Name": {"title": [{"text": {"content": l["ig_name"] or l["sellerName"] or l["ig_handle"]}}]},
            "URL": {"url": l["ig_url"]},
            "Platform": {"select": {"name": "IG"}},
            "Language": {"select": {"name": l.get("language", "NL")}},
            "Status": {"status": {"name": "Reach out"}},
            "Verkoop op...": {"select": {"name": "Marktplaats"}},
            "Je/Jullie": {"select": {"name": l.get("je_jullie", "Je")}},
            "Notes (Optional)": {"rich_text": [{"text": {"content": notes[:1900]}}]},
        }
        if l.get("verkoopt_vooral"):
            props["Verkoopt vooral..."] = {"select": {"name": l["verkoopt_vooral"]}}
        try:
            _notion("POST", "/pages", token,
                    {"parent": {"database_id": NOTION_DB}, "properties": props})
            created += 1
            print(f"  + @{l['ig_handle']}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! @{l['ig_handle']}: {e}")

    print(f"\n{created} leads toegevoegd, {skipped} bestonden al.")
    print("De AI-autofill in Notion schrijft de outreach-tekst zelf. "
          "Versturen doe je met de hand — zie de kop van dit bestand.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="Marktplaats-advertenties oogsten")
    h.add_argument("--max-per-source", type=int, default=200)
    h.add_argument("--fresh", action="store_true", help="begin opnieuw i.p.v. hervatten")
    h.set_defaults(func=harvest)

    r = sub.add_parser("rank", help="groeperen per verkoper en filteren")
    r.add_argument("--min-listings", type=int, default=MIN_LISTINGS)
    r.set_defaults(func=rank)

    e = sub.add_parser("enrich", help="Instagram-account zoeken bij de winkelnaam")
    e.add_argument("--limit", type=int, default=MAX_SELLERS_TO_ENRICH)
    e.add_argument("--dry-run", action="store_true", help="alleen de gokken tonen")
    e.set_defaults(func=enrich)

    c = sub.add_parser("classify", help="Haiku beoordeelt reseller vs consument")
    c.add_argument("--min-confidence", type=int, default=60)
    c.set_defaults(func=classify)

    p = sub.add_parser("push", help="naar de Notion-Leadlist")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=push)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
