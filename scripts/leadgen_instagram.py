#!/usr/bin/env python3
"""
Leadgen voor de Instagram-outreach van Omnivaleur.

HET PROBLEEM
Zoeken op hashtags (#vinted, #tweedehands) levert vooral kopers, reviewers,
haul-accounts en buitenlandse verkopers. Die hashtag zegt "ik heb iets met
tweedehands", niet "ik verkoop serieus en heb last van crosslisten".

WAT WEL WERKT — alles live getest (2026-07), niet aangenomen
  * Vinted als bron: ONBRUIKBAAR. Cloudflare weigert datacenter-IP's; drie
    verschillende Apify Vinted-actors gaven allemaal nul resultaten.
  * Marktplaats als bron: scrape werkt, maar er is GEEN brug naar Instagram.
    Handles raden gaf 4 treffers op 13 gokken en de enige echte match was een
    verzamelaar uit Tokio; 0 van 53 advertentieteksten noemde een @handle.
  * Instagram-hashtags: BESTE BRON. 30 posts op #tweedehandskleding gaven 22 unieke
    Nederlandse winkels. Zie leadgen_sources.py voor de cijfers per methode.

DE TRECHTER
  discover  handles verzamelen uit vier bronnen (zie leadgen_sources.py)
  enrich    bio, volgers en website erbij halen — de bron levert alleen een handle
  classify  Haiku beoordeelt: verkoper of consument/reviewer? + Notion-veldwaardes
  push      als lead in de Notion-Leadlist zetten, status "Reach out"

Elke stap schrijft naar scripts/output/leads/ en leest de vorige van schijf, zodat je
een dure stap nooit twee keer draait en tussendoor met de hand kunt controleren.
'discover' stapelt: elke run voegt toe aan wat er al ligt in plaats van te overschrijven.

DIT SCRIPT VERSTUURT NIETS. De officiële Instagram-API staat koude DM's niet toe
(alleen antwoorden binnen 24 uur nadat iemand jou schrijft), en tools die het toch
doen worden gedetecteerd — met je eigen merkaccount als inzet. Alles tot en met de
kant-en-klare tekst is geautomatiseerd, op de verzendknop na.

Gebruik:
    export APIFY_TOKEN=... NOTION_TOKEN=...
    python3 scripts/leadgen_instagram.py discover --method hashtag
    python3 scripts/leadgen_instagram.py enrich
    python3 scripts/leadgen_instagram.py classify
    python3 scripts/leadgen_instagram.py push --dry-run

    python3 scripts/leadgen_instagram.py bench      # welke bron levert het meest op
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import leadgen_sources as src  # noqa: E402

OUT = Path(__file__).parent / "output" / "leads"
HANDLES = OUT / "handles.json"
CANDIDATES = OUT / "candidates.json"
LEADS = OUT / "leads.json"
BENCH = OUT / "bench.json"

PROFILE_ACTOR = "figue~instagram-profile-scraper"

NOTION_DB = "399b0954-fb72-8053-a8fc-fa7c21616371"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _need(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        sys.exit(f"Zet {var} in je omgeving (export {var}=...)")
    return val


def _clean(v) -> str:
    """Actors schrijven letterlijk "N/A" in lege velden; dat is voor een prompt
    misleidender dan gewoon niets."""
    return "" if v in (None, "N/A", "", "null") else str(v)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


def _save(path: Path, rows: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- discover


def _collect(method: str, args, token: str, exclude: list[str]) -> list[dict]:
    if method == "dork":
        return src.from_dork(pages=args.pages)
    if method == "hashtag":
        return src.from_hashtag(args.hashtags, per_tag=args.per_tag, token=token)
    if method == "keyword":
        return src.from_keyword(args.queries, max_count=args.max, token=token,
                                exclude=exclude)
    if method == "local":
        return src.from_local(args.cities, max_per_run=5, token=token, exclude=exclude)
    sys.exit(f"Onbekende methode: {method}")


def discover(args) -> None:
    methods = list(src.SOURCES) if args.method == "all" else [args.method]
    # 'dork' is de enige bron zonder Apify; alleen daarvoor mag de token ontbreken.
    token = "" if methods == ["dork"] else _need("APIFY_TOKEN")

    existing = _load(HANDLES)
    seen = {r["handle"] for r in existing}
    exclude = _existing_handles_or_empty() + sorted(seen)
    print(f"{len(existing)} handles al verzameld, {len(exclude)} uitgesloten\n")

    added = 0
    for method in methods:
        print(f"[{method}]")
        for rec in _collect(method, args, token, exclude):
            if rec["handle"] in seen:
                continue
            seen.add(rec["handle"])
            existing.append(rec)
            added += 1
        print()

    _save(HANDLES, existing)
    print(f"{added} nieuwe handles ({len(existing)} totaal) → {HANDLES}")
    for rec in existing[-15:]:
        print(f"  @{rec['handle']:30s} {rec['method']:8s} {rec['full_name'][:34]}")


def _existing_handles_or_empty() -> list[str]:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        return []
    try:
        return [u.rstrip("/").rsplit("/", 1)[-1] for u in _existing_urls(token)]
    except Exception:  # noqa: BLE001 — dedupe is een optimalisatie, geen vereiste
        return []


# ------------------------------------------------------------------ enrich


def _enrich_rows(rows: list[dict], token: str, batch: int = 50) -> list[dict]:
    """Handle → volledig profiel. Hashtag- en dork-bronnen leveren alleen een naam;
    zonder bio kan de classificatie een winkel niet van een koper onderscheiden.

    Dit is óók waar de gratis-plan-limiet omzeild wordt: die zit op de discovery-
    actor, niet op de profiel-actor. Hier betaal je ~$0,001 per profiel, ongelimiteerd.
    """
    by_handle = {r["handle"]: r for r in rows}

    # Instagram knijpt deze actor af bij grote batches: van veertig profielen in één
    # keer kwamen er twaalf terug, met "Could not retrieve profile data" voor de rest.
    # Dat is tijdelijk, geen bestaand-of-niet. Zonder deze herhaalronde gooi je dus
    # tweederde van je leads weg omdat Instagram het even te druk had.
    for attempt in range(1, attempts + 1):
        todo = [r for r in rows if not r.get("enriched")]
        if not todo:
            break
        if attempt > 1:
            print(f"  ronde {attempt}: {len(todo)} profielen opnieuw proberen")
            time.sleep(5 * attempt)

        for i in range(0, len(todo), batch):
            chunk = todo[i: i + batch]
            print(f"  profielen {i + 1}-{i + len(chunk)} van {len(todo)}…", flush=True)
            got = src._run(PROFILE_ACTOR,
                           {"profiles": [r["handle"] for r in chunk],
                            "includeRecentPosts": True}, token)
            for row in got:
                handle = (row.get("username") or "").lower()
                target = by_handle.get(handle)
                # Een 'error'-rij is geen profiel; die laten we onverrijkt zodat de
                # volgende ronde hem opnieuw oppakt.
                if not target or row.get("error"):
                    continue
                target.update({
                "enriched": True,
                "full_name": _clean(row.get("full_name")) or target.get("full_name", ""),
                "followers": row.get("followersCount") or target.get("followers") or 0,
                "posts": row.get("postsCount") or 0,
                "bio": _clean(row.get("biography")),
                "website": _clean(row.get("external_url")),
                "email": _clean(row.get("business_email")),
                "category": _clean(row.get("category_name")),
                "private": bool(row.get("is_private")),
                    "captions": [(p.get("caption") or "")[:240]
                                 for p in (row.get("latestPosts") or [])[:4]],
                })

    missing = [r["handle"] for r in rows if not r.get("enriched")]
    if missing:
        print(f"  · {len(missing)} profielen bleven onbereikbaar: "
              f"{', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")
        print("    Die blijven in handles.json staan; een latere 'enrich' pakt ze op.")
    return rows


def enrich(args) -> None:
    token = _need("APIFY_TOKEN")
    everything = _load(HANDLES)
    if not everything:
        sys.exit("Nog geen handles.json — draai eerst 'discover'")

    # _enrich_rows muteert de dicts, dus een slice verrijkt dezelfde objecten die in
    # `everything` zitten. Daardoor kan --limit een deel doen zonder dat de rest van
    # handles.json bij het opslaan verdwijnt, en is een tweede run een goedkope
    # voortzetting in plaats van een herhaling.
    _enrich_rows(everything[: args.limit] if args.limit else everything, token)

    _save(HANDLES, everything)
    ok = [r for r in everything if r.get("enriched") and not r.get("private")]
    _save(CANDIDATES, ok)
    print(f"\n{len(ok)} publieke profielen verrijkt → {CANDIDATES}")


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
  website: {website}
  categorie: {category}
  e-mail: {email}
  recente bijschriften: {captions}

Antwoord met UITSLUITEND JSON:
{{"is_lead": true/false,
  "confidence": 0-100,
  "reden": "één zin, Nederlands",
  "verkoopt_vooral": "Kleding|Meubilair|Alles|Antieke vintage|Hoogwaardige vintage|Vintage jewelry|Vintage interieur|Sieraden|Knutselmaterialen",
  "verkoop_op": "Eigen website|Fysieke winkel|Marktplaats|Instagram|Vinted|Onbekend|Vinted en eigen website",
  "je_jullie": "Je|Jullie",
  "language": "NL|EN"}}"""


def _classify_rows(rows: list[dict], min_confidence: int, quiet: bool = False) -> list[dict]:
    import anthropic
    from backend.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    leads = []
    for i, row in enumerate(rows, 1):
        prompt = PROMPT.format(
            handle=row["handle"],
            full_name=row.get("full_name") or "(leeg)",
            followers=row.get("followers") or 0,
            posts=row.get("posts") or 0,
            bio=row.get("bio") or "(leeg)",
            website=row.get("website") or "(geen)",
            category=row.get("category") or "(geen)",
            email=row.get("email") or "(geen)",
            captions=" | ".join(row.get("captions") or []) or "(geen)",
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            verdict = json.loads(re.search(r"\{.*\}", resp.content[0].text, re.S).group(0))
        except Exception as e:  # noqa: BLE001
            print(f"  ! @{row['handle']}: {e}")
            continue

        keep = verdict.get("is_lead") and verdict.get("confidence", 0) >= min_confidence
        if not quiet:
            print(f"[{i}/{len(rows)}] {'✓' if keep else '·'} @{row['handle']:28s} "
                  f"{verdict.get('reden', '')[:60]}")
        if keep:
            leads.append({
                **{k: row.get(k) for k in
                   ("handle", "method", "source", "full_name", "followers",
                    "bio", "email", "website")},
                "ig_url": f"https://www.instagram.com/{row['handle']}/",
                **verdict,
            })
    return leads


def classify(args) -> None:
    rows = _load(CANDIDATES)
    if not rows:
        sys.exit("Nog geen candidates.json — draai eerst 'enrich'")
    leads = _classify_rows(rows, args.min_confidence)
    _save(LEADS, leads)
    print(f"\n{len(leads)} van {len(rows)} accounts gekwalificeerd → {LEADS}")


# ------------------------------------------------------------------- bench


def bench(args) -> None:
    """Draai alle vier de bronnen apart en vergelijk de opbrengst.

    Meet wat er telt: niet hoeveel handles een bron oplevert, maar hoeveel daarvan
    de classificatie overleven. Een bron die 100 kopers aandraagt is slechter dan
    een die 12 winkels vindt.
    """
    token = _need("APIFY_TOKEN")
    results = []

    for method in ("hashtag", "local", "keyword", "dork"):
        if args.only and method not in args.only:
            continue
        print(f"\n{'=' * 62}\n[{method}]\n{'=' * 62}")
        budget = argparse.Namespace(
            pages=1, per_tag=args.per_tag, max=args.max, queries=None,
            hashtags=src.HASHTAGS[: args.n], cities=src.CITIES[: args.n],
        )
        try:
            found = _collect(method, budget, token, [])
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"  ! bron faalde: {e}")
            found = []

        enriched = [r for r in _enrich_rows(found, token)
                    if r.get("enriched") and not r.get("private")] if found else []
        leads = _classify_rows(enriched, args.min_confidence, quiet=True) if enriched else []
        results.append({
            "methode": method,
            "handles": len(found),
            "profielen": len(enriched),
            "leads": len(leads),
            "precisie": round(100 * len(leads) / len(enriched)) if enriched else 0,
            "voorbeelden": [l["handle"] for l in leads[:5]],
        })

    _save(BENCH, results)
    print(f"\n\n{'methode':10s} {'handles':>8s} {'profielen':>10s} {'leads':>6s} {'precisie':>9s}")
    print("-" * 48)
    for r in sorted(results, key=lambda r: r["leads"], reverse=True):
        print(f"{r['methode']:10s} {r['handles']:>8d} {r['profielen']:>10d} "
              f"{r['leads']:>6d} {r['precisie']:>8d}%")
    print(f"\nDetails → {BENCH}")


# --------------------------------------------------------------------- push


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
    leads = _load(LEADS)
    if not leads:
        sys.exit("Nog geen leads.json — draai eerst 'classify'")

    if args.dry_run:
        print(f"{len(leads)} leads klaar (dry-run, er wordt niets weggeschreven):\n")
        for l in leads:
            print(f"  @{l['handle']:28s} {l.get('followers') or 0:>7} volgers  "
                  f"{l.get('method', ''):8s} {l.get('verkoopt_vooral', '')}")
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
            f"{l.get('followers') or 0} volgers",
            f"gevonden via {l.get('source') or l.get('method')}",
            l.get("website"), l.get("email"), l.get("reden"),
        ] if x)
        props = {
            "Name": {"title": [{"text": {"content": l.get("full_name") or l["handle"]}}]},
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

    d = sub.add_parser("discover", help="handles verzamelen uit een of alle bronnen")
    d.add_argument("--method", default="hashtag",
                   choices=[*src.SOURCES, "all"])
    d.add_argument("--max", type=int, default=40, help="keyword: kostenplafond")
    d.add_argument("--per-tag", type=int, default=40, help="hashtag: posts per tag")
    d.add_argument("--pages", type=int, default=2, help="dork: zoekpagina's per term")
    d.add_argument("--queries", nargs="*", help="keyword: eigen zoektermen")
    d.add_argument("--hashtags", nargs="*", help="hashtag: eigen tags")
    d.add_argument("--cities", nargs="*", help="local: eigen steden")
    d.set_defaults(func=discover)

    e = sub.add_parser("enrich", help="bio/volgers/website bij de handles zoeken")
    e.add_argument("--limit", type=int, default=0)
    e.set_defaults(func=enrich)

    c = sub.add_parser("classify", help="Haiku beoordeelt verkoper vs consument")
    c.add_argument("--min-confidence", type=int, default=60)
    c.set_defaults(func=classify)

    b = sub.add_parser("bench", help="vergelijk de opbrengst van de vier bronnen")
    b.add_argument("--n", type=int, default=3, help="hashtags/steden per methode")
    b.add_argument("--per-tag", type=int, default=30)
    b.add_argument("--max", type=int, default=10)
    b.add_argument("--min-confidence", type=int, default=60)
    b.add_argument("--only", nargs="*", help="alleen deze methoden")
    b.set_defaults(func=bench)

    p = sub.add_parser("push", help="naar de Notion-Leadlist")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=push)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
