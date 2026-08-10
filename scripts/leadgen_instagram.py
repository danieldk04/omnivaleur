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
  * Instagram-hashtags: BESTE BRON. Zie leadgen_sources.py voor de cijfers per bron.

WIE WE ZOEKEN — en wie NIET
Serieuze resellers: mensen die op Vinted, Marktplaats of eBay verkopen om geld te
verdienen, met verzendbare spullen (kleding, schoenen, sneakers, tassen, sieraden,
games, elektronica) in categorieën die Omnivaleur goed herkent.
Uitdrukkelijk NIET: kringloopwinkels en goede doelen (vrijwilligers, geen winstmotief,
verzenden niet) en meubel-/brocante-/interieurverkopers (onverzendbaar, vaak hobby).
Een eerdere versie zocht op #kringloopwinkel en #vintagemeubels en leverde precies
die twee groepen — hoge precisie op de verkeerde doelgroep.

DE TRECHTER
  discover  handles verzamelen uit vier bronnen (zie leadgen_sources.py)
  enrich    bio, volgers en website erbij halen — de bron levert alleen een handle
  classify  Haiku beoordeelt op winstmotief, verzendbaarheid en NL/BE
  push      als lead in de Notion-Leadlist zetten, status "Reach out"
  run       alle vier bovenstaande in één commando

Elke stap schrijft naar scripts/output/leads/ en leest de vorige van schijf, zodat je
een dure stap nooit twee keer draait en tussendoor met de hand kunt controleren.
'discover' stapelt: elke run voegt toe aan wat er al ligt in plaats van te overschrijven.

DIT SCRIPT VERSTUURT NIETS. De officiële Instagram-API staat koude DM's niet toe
(alleen antwoorden binnen 24 uur nadat iemand jou schrijft), en tools die het toch
doen worden gedetecteerd — met je eigen merkaccount als inzet. Alles tot en met de
kant-en-klare tekst is geautomatiseerd, op de verzendknop na.

Gebruik:
    export APIFY_TOKEN=... NOTION_TOKEN=...
    python3 scripts/leadgen_instagram.py run                 # alles in één keer
    python3 scripts/leadgen_instagram.py run --dry-run       # idem, zonder Notion

    python3 scripts/leadgen_instagram.py bench      # welke bron levert het meest op
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import leadgen_notion as notion  # noqa: E402
from scripts import leadgen_sources as src  # noqa: E402

OUT = Path(__file__).parent / "output" / "leads"
HANDLES = OUT / "handles.json"
CANDIDATES = OUT / "candidates.json"
LEADS = OUT / "leads.json"
BENCH = OUT / "bench.json"

PROFILE_ACTOR = "figue~instagram-profile-scraper"

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
        return [u.rstrip("/").rsplit("/", 1)[-1] for u in notion.existing_urls(token)]
    except Exception:  # noqa: BLE001 — dedupe is een optimalisatie, geen vereiste
        return []


# ------------------------------------------------------------------ enrich


# Na zoveel mislukte rondes (opgeteld over álle runs, niet per run) houdt een handle
# op een kandidaat te zijn. Live gemeten: een handle die drie rondes "Could not
# retrieve profile data" geeft, geeft dat ook in een batch van vijf en ook een dag
# later — het account is hernoemd, verwijderd of geblokkeerd. Zonder deze grens
# betaalt en wacht elke volgende run opnieuw voor dezelfde lijst lijken.
MAX_FAILS = 3


def _enrich_rows(rows: list[dict], token: str, batch: int = 25,
                 attempts: int = 2, workers: int = 4) -> list[dict]:
    """Handle → volledig profiel. Hashtag- en dork-bronnen leveren alleen een naam;
    zonder bio kan de classificatie een winkel niet van een koper onderscheiden.

    Dit is óók waar de gratis-plan-limiet omzeild wordt: die zit op de discovery-
    actor, niet op de profiel-actor. Hier betaal je ~$0,001 per profiel, ongelimiteerd.
    """
    by_handle = {r["handle"]: r for r in rows}

    # Instagram knijpt deze actor af bij grote batches: van veertig profielen in één
    # keer kwamen er twaalf terug, met "Could not retrieve profile data" voor de rest.
    # Dat is deels tijdelijk — vandaar één herhaalronde. Een derde ronde is gemeten en
    # leverde één profiel op 198 pogingen op: dat is de wachttijd niet waard.
    for attempt in range(1, attempts + 1):
        todo = [r for r in rows if not r.get("enriched") and not r.get("dead")]
        if not todo:
            break
        if attempt > 1:
            print(f"  ronde {attempt}: {len(todo)} profielen opnieuw proberen")
            time.sleep(5)

        chunks = [todo[i: i + batch] for i in range(0, len(todo), batch)]
        done = 0
        # Deze actor-runs zijn wachten, geen rekenen: vier tegelijk scheelt ruwweg
        # vier keer de doorlooptijd en kost geen cent extra.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(src._run, PROFILE_ACTOR,
                                   {"profiles": [r["handle"] for r in chunk],
                                    "includeRecentPosts": True}, token)
                       for chunk in chunks]
            for future in as_completed(futures):
                got = future.result()
                done += 1
                print(f"  batch {done}/{len(chunks)} klaar — {len(got)} rijen terug",
                      flush=True)
                for row in got:
                    handle = (row.get("username") or "").lower()
                    target = by_handle.get(handle)
                    # Een 'error'-rij is geen profiel; die laten we onverrijkt zodat
                    # de volgende ronde hem opnieuw oppakt.
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

        for row in todo:
            if row.get("enriched"):
                continue
            row["fails"] = row.get("fails", 0) + 1
            if row["fails"] >= MAX_FAILS:
                row["dead"] = True

    missing = [r for r in rows if not r.get("enriched") and not r.get("dead")]
    buried = [r for r in rows if r.get("dead")]
    if missing:
        print(f"  · {len(missing)} nu onbereikbaar, volgende run opnieuw: "
              f"{', '.join(r['handle'] for r in missing[:6])}"
              f"{' …' if len(missing) > 6 else ''}")
    if buried:
        print(f"  · {len(buried)} handles definitief opgegeven na {MAX_FAILS} rondes "
              f"(hernoemd, verwijderd of geblokkeerd).")
        print("    'enrich --retry-dead' probeert ze alsnog nog een keer.")
    return rows


def enrich(args) -> None:
    token = _need("APIFY_TOKEN")
    everything = _load(HANDLES)
    if not everything:
        sys.exit("Nog geen handles.json — draai eerst 'discover'")

    if getattr(args, "retry_dead", False):
        revived = [r for r in everything if r.pop("dead", None)]
        for row in revived:
            row["fails"] = 0
        print(f"  {len(revived)} eerder opgegeven handles krijgen een nieuwe kans")

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
een tool waarmee verkopers hun advertenties in één keer op Marktplaats, 2dehands,
Vinted, eBay en Shopify zetten. De waarde zit in MEER en SNELLER verkopen.

Een goede lead moet aan ALLE DRIE voldoen:
 1. COMMERCIEEL MOTIEF — verkoopt om geld te verdienen, niet als hobby of goed doel.
    Signalen: inkoopt om door te verkopen, praat over voorraad/drops/restock/omzet,
    heeft een webshop, verkoopt in volume, noemt verzendkosten of levertijden.
 2. VERZENDBARE SPULLEN — kleding, schoenen, sneakers, tassen, sieraden, horloges,
    accessoires, games, consoles, elektronica, telefoons, boeken. Dus GEEN meubels,
    kasten, banken, interieur of andere grote stukken die je niet in een doos doet.
 3. NL/BE — Nederlandstalig of aantoonbaar in Nederland of België actief.

Wijs af (is_lead = false), ook al lijkt het op tweedehands:
 * KRINGLOOPWINKELS, goede doelen, vrijwilligerswinkels (Dorcas, Vincentius, Rode
   Kruis, Woord en Daad, kerkelijke winkels). Die verkopen niet om winst, werken met
   vrijwilligers, verzenden meestal niet en hebben geen crosslist-probleem.
 * Brocante-, antiek-, meubel- en interieurverkopers. Onverzendbaar, en het is voor
   hen vaak liefhebberij in plaats van omzet.
 * Consumenten, kopers, reviewers, haul-accounts, influencers zonder eigen voorraad.
 * Merken die nieuw produceren en verkopen.
 * Accounts die alleen buiten NL/BE actief zijn.

De ideale lead is de serieuze reseller: iemand die op Vinted, Marktplaats of eBay
verkoopt, kleding of sneakers doorverkoopt, of een tweedehands-webshop runt, en die
zijn voorraad nu handmatig op meerdere plekken moet zetten.

Account:
  @{handle} — {full_name}
  volgers: {followers}, posts: {posts}
  bio: {bio}
  website: {website}
  categorie volgens Instagram: {category}
  e-mail: {email}
  gevonden via: {hint}
  recente bijschriften: {captions}

Antwoord met UITSLUITEND JSON:
{{"is_lead": true/false,
  "confidence": 0-100,
  "verkopertype": "reseller|webshop|winkel|kringloop|meubels|consument|influencer|merk|onduidelijk",
  "verzendbaar": true/false,
  "commercieel": true/false,
  "reden": "één zin, Nederlands",
  "verkoopt_vooral": "Kleding|Meubilair|Alles|Antieke vintage|Hoogwaardige vintage|Vintage jewelry|Vintage interieur|Sieraden|Knutselmaterialen",
  "verkoop_op": "Eigen website|Fysieke winkel|Marktplaats|Instagram|Vinted|Onbekend|Vinted en eigen website",
  "je_jullie": "Je|Jullie",
  "language": "NL|EN"}}"""

# Typen die het model wel als "lead" kan markeren maar die je niet wilt benaderen.
# Het oordeel van het model op de drie losse assen (type/verzendbaar/commercieel) is
# betrouwbaarder dan zijn eigen is_lead-vlag, want dat laatste vat te veel samen —
# de eerste ronde leverde kringloopwinkels op met is_lead=true en een keurige
# onderbouwing erbij.
REJECT_TYPES = {"kringloop", "meubels", "consument", "influencer", "merk"}


def _judge(client, row: dict) -> dict | None:
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
        hint=row.get("hint") or row.get("source") or "(onbekend)",
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(re.search(r"\{.*\}", resp.content[0].text, re.S).group(0))
    except Exception as e:  # noqa: BLE001
        print(f"  ! @{row['handle']}: {e}")
        return None


def _keep(verdict: dict, min_confidence: int) -> bool:
    vtype = (verdict.get("verkopertype") or "onduidelijk").lower()
    return bool(verdict.get("is_lead")
                and verdict.get("confidence", 0) >= min_confidence
                and vtype not in REJECT_TYPES
                and verdict.get("verzendbaar") is not False
                and verdict.get("commercieel") is not False)


def _classify_rows(rows: list[dict], min_confidence: int, quiet: bool = False,
                   workers: int = 8) -> list[dict]:
    """Beoordeel elke rij en geef de gekwalificeerde leads terug.

    Het oordeel wordt op de rij zelf bewaard onder "verdict". Een account dat al een
    keer beoordeeld is, wordt niet opnieuw aan het model voorgelegd — de bio van
    gisteren levert vandaag hetzelfde antwoord, en een tweede run betaalde eerder
    voor honderdvijftig herhalingen om er tien nieuwe bij te vinden.
    """
    import anthropic
    from backend.config import settings

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    todo = [r for r in rows if not r.get("verdict")]
    cached = len(rows) - len(todo)
    if cached and not quiet:
        print(f"  {cached} accounts waren al beoordeeld, die sla ik over")

    if todo:
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_judge, client, row): row for row in todo}
            for future in as_completed(futures):
                row = futures[future]
                verdict = future.result()
                done += 1
                if not verdict:
                    continue
                row["verdict"] = verdict
                if not quiet:
                    keep = _keep(verdict, min_confidence)
                    why = "" if keep else (verdict.get("verkopertype") or "?").lower()
                    print(f"[{done}/{len(todo)}] {'✓' if keep else '·'} "
                          f"@{row['handle']:26s} {why:12s} "
                          f"{verdict.get('reden', '')[:52]}", flush=True)

    leads = []
    for row in rows:
        verdict = row.get("verdict")
        if verdict and _keep(verdict, min_confidence):
            leads.append({
                **{k: row.get(k) for k in
                   ("handle", "method", "source", "full_name", "followers",
                    "bio", "email", "website")},
                "ig_url": f"https://www.instagram.com/{row['handle']}/",
                **verdict,
            })
    return leads


def classify(args) -> None:
    # Bewust handles.json en niet candidates.json: de oordelen worden op de rij
    # bewaard, en alleen handles.json overleeft een volgende 'enrich'.
    everything = _load(HANDLES)
    rows = [r for r in everything if r.get("enriched") and not r.get("private")]
    if not rows:
        sys.exit("Nog geen verrijkte profielen — draai eerst 'enrich'")

    leads = _classify_rows(rows, args.min_confidence)
    _save(HANDLES, everything)
    _save(CANDIDATES, rows)
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

        # Eén verrijkingsronde, niet drie: een vergelijking hoeft niet compleet te
        # zijn, alleen eerlijk. Elke bron krijgt dezelfde ene kans, en dat scheelt
        # drie keer de tijd en de kosten van een productierun.
        enriched = [r for r in _enrich_rows(found, token, attempts=1)
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


def push(args) -> None:
    leads = _load(LEADS)
    if not leads:
        sys.exit("Nog geen leads.json — draai eerst 'classify'")

    if args.dry_run:
        print(f"{len(leads)} leads klaar (dry-run, er wordt niets weggeschreven):\n")
        for l in leads:
            print(f"  @{l['handle']:26s} {l.get('followers') or 0:>7} volgers  "
                  f"{l.get('verkopertype', ''):10s} {l.get('verkoopt_vooral', '')}")
            print(f"     {l.get('reden', '')}")
        return

    created, skipped = notion.push_leads(leads, _need("NOTION_TOKEN"))
    print(f"\n{created} leads toegevoegd, {skipped} bestonden al.")
    print("De AI-autofill in Notion schrijft de outreach-tekst zelf. "
          "Versturen doe je met de hand — zie de kop van dit bestand.")


def run(args) -> None:
    """De hele trechter in één commando: zoeken, verrijken, beoordelen, wegschrijven.

    Elke stap schrijft nog steeds naar schijf, dus als er halverwege iets omvalt kun
    je met het losse subcommando verder waar het misging in plaats van opnieuw te
    betalen voor wat al gelukt was.
    """
    _need("APIFY_TOKEN")
    if not args.dry_run:
        _need("NOTION_TOKEN")   # liever nu falen dan na alle Apify-kosten

    print("── 1/4 zoeken ─────────────────────────────────────────────")
    discover(args)
    print("\n── 2/4 profielen ophalen ──────────────────────────────────")
    enrich(args)
    print("\n── 3/4 beoordelen ─────────────────────────────────────────")
    classify(args)
    print("\n── 4/4 naar Notion ────────────────────────────────────────")
    push(args)

    leads = _load(LEADS)
    if leads:
        per_type: dict[str, int] = {}
        for l in leads:
            per_type[l.get("verkopertype", "?")] = per_type.get(l.get("verkopertype", "?"), 0) + 1
        print("\nSoort leads: " + ", ".join(f"{k} {v}" for k, v in sorted(
            per_type.items(), key=lambda kv: -kv[1])))


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
    e.add_argument("--retry-dead", action="store_true",
                   help="eerder opgegeven handles tóch nog een keer proberen")
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

    r = sub.add_parser("run", help="ALLES in één keer: zoeken → verrijken → beoordelen → Notion")
    r.add_argument("--method", default="hashtag", choices=[*src.SOURCES, "all"])
    r.add_argument("--per-tag", type=int, default=40)
    r.add_argument("--max", type=int, default=40)
    r.add_argument("--pages", type=int, default=2)
    r.add_argument("--queries", nargs="*")
    r.add_argument("--hashtags", nargs="*")
    r.add_argument("--cities", nargs="*")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--min-confidence", type=int, default=60)
    r.add_argument("--dry-run", action="store_true",
                   help="alles draaien maar niets naar Notion schrijven")
    r.set_defaults(func=run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
