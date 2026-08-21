"""
Verkenningsronde voor de wekelijkse trendmotor: welke creators zijn de moeite
waard om structureel te volgen?

Waarom een eigen browser en niet Apify: Apify's gratis maandlimiet is eindig en
kost daarna geld per resultaat, terwijl TikTok zijn eigen cijfers gewoon aan de
browser meegeeft. We laten een echte browser de pagina laden, luisteren mee naar
het verzoek dat TikTok zélf doet (item_list) en lezen daar views, likes, shares
en saves uit. Dat is gratis en levert precies de velden die het algoritme beloont.

Zonder de stealth-laag antwoordt TikTok met 200 én een lege body — geen fout,
gewoon niets. Dat is geen bug om te omzeilen maar een detectie die we moeten
respecteren met een browser die zich normaal gedraagt: vandaar de trage scrolls
en de wachttijden. Ga je sneller, dan krijg je stilte terug.

YouTube heeft dit niet nodig: de zoekpagina zet de cijfers rechtstreeks in de
HTML (ytInitialData), dus daar is een simpele GET genoeg.

Instagram ontbreekt hier bewust: hashtagpagina's zijn sinds 2024 alleen na
inloggen te zien. Dat loopt via Apify zodra het maandbudget weer open staat.

Draaien:
    python3 scripts/social_trends_discover.py
    python3 scripts/social_trends_discover.py --snel     # kleine testronde
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UITVOER = Path(__file__).parent / "output"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# ── De drie hoeken van de niche ─────────────────────────────────────────────
# Per hoek: welke TikTok-hashtags en welke YouTube-zoektermen. Nederlands en
# Engels apart, want het Engelse gebied is de trendradar (loopt 2-4 weken voor)
# en het Nederlandse gebied is wat direct toepasbaar is.
NICHES: dict[str, dict] = {
    "resellers": {
        "titel": "Reselling — mensen die zelf tweedehands verkopen",
        "tiktok_nl": ["vinted", "vintednederland", "vintedtips", "tweedehands", "marktplaats"],
        "tiktok_en": ["reseller", "ebayreseller", "depopseller", "poshmarkreseller",
                      "vintedseller", "resellercommunity"],
        "youtube": ["vinted verkopen tips", "reseller tips 2026",
                    "how to sell on vinted", "ebay reseller haul"],
    },
    "thrifting": {
        "titel": "Tweedehands mode & thrifting",
        "tiktok_nl": ["tweedehandskleding", "kringloop", "vintagekleding"],
        "tiktok_en": ["thrifthaul", "thrifting", "vintagefashion", "thriftwithme"],
        "youtube": ["thrift haul 2026", "kringloop haul", "vintage fashion finds"],
    },
    "tools": {
        "titel": "Tools & software voor verkopers",
        "tiktok_nl": ["crosslisten"],
        "tiktok_en": ["crosslisting", "crosslistingapp", "resellersoftware"],
        "youtube": ["crosslisting app review", "list perfectly vs vendoo"],
    },
}


# ── TikTok ──────────────────────────────────────────────────────────────────
async def _tiktok_tag(page, tag: str, scrolls: int) -> list[dict]:
    """Laadt één hashtagpagina en vangt de videolijst op die TikTok zelf ophaalt."""
    gevangen: list[dict] = []
    bezig: list = []

    async def lees(resp):
        if "item_list" not in resp.url:
            return
        try:
            tekst = await resp.text()
        except Exception:
            return
        if len(tekst) < 100:  # lege body = TikTok wimpelt ons af
            return
        try:
            data = json.loads(tekst)
        except json.JSONDecodeError:
            return
        gevangen.extend(data.get("itemList") or [])

    handler = lambda r: bezig.append(asyncio.create_task(lees(r)))  # noqa: E731
    page.on("response", handler)
    try:
        await page.goto(f"https://www.tiktok.com/tag/{tag}",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(7000)
        for _ in range(scrolls):
            await page.mouse.wheel(0, 3500)
            await page.wait_for_timeout(3500)
    except Exception as e:
        print(f"   ! #{tag} mislukt: {type(e).__name__}", file=sys.stderr)
    finally:
        page.remove_listener("response", handler)
        if bezig:
            await asyncio.gather(*bezig, return_exceptions=True)
    return gevangen


def _tiktok_norm(it: dict, niche: str, taal: str, tag: str) -> dict | None:
    a = it.get("author") or {}
    s = it.get("stats") or {}
    ast = it.get("authorStats") or it.get("authorStatsV2") or {}
    handle = a.get("uniqueId")
    if not handle:
        return None
    views = _int(s.get("playCount"))
    muziek = it.get("music") or {}
    return {
        "platform": "TikTok",
        "niche": niche,
        "taal": taal,
        "gevonden_via": f"#{tag}",
        "handle": handle,
        "naam": a.get("nickname") or "",
        "volgers": _int(ast.get("followerCount")),
        "video_id": str(it.get("id") or ""),
        "url": f"https://www.tiktok.com/@{handle}/video/{it.get('id')}",
        "tekst": (it.get("desc") or "")[:300],
        "datum": _datum(it.get("createTime")),
        "views": views,
        "likes": _int(s.get("diggCount")),
        "comments": _int(s.get("commentCount")),
        "shares": _int(s.get("shareCount")),
        "saves": _int(s.get("collectCount")),
        "duur": _int((it.get("video") or {}).get("duration")),
        "sound": (muziek.get("title") or "")[:120],
    }


async def verzamel_tiktok(scrolls: int, hashtag_limiet: int | None) -> list[dict]:
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None
        print("! playwright-stealth ontbreekt — TikTok geeft dan lege antwoorden",
              file=sys.stderr)

    opdrachten: list[tuple[str, str, str]] = []  # (niche, taal, hashtag)
    for niche, cfg in NICHES.items():
        for taal, sleutel in (("nl", "tiktok_nl"), ("en", "tiktok_en")):
            for tag in cfg.get(sleutel, [])[:hashtag_limiet]:
                opdrachten.append((niche, taal, tag))

    resultaat: list[dict] = []
    gezien: set[str] = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            locale="nl-NL", user_agent=UA, viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()
        if stealth_async:
            try:
                await stealth_async(page)
            except Exception as e:
                print(f"! stealth overgeslagen: {e}", file=sys.stderr)

        for i, (niche, taal, tag) in enumerate(opdrachten, 1):
            print(f"  [{i}/{len(opdrachten)}] TikTok #{tag} ({niche}/{taal}) …", flush=True)
            for it in await _tiktok_tag(page, tag, scrolls):
                vid = str(it.get("id") or "")
                if not vid or vid in gezien:
                    continue
                gezien.add(vid)
                rij = _tiktok_norm(it, niche, taal, tag)
                if rij:
                    resultaat.append(rij)
        await browser.close()
    return resultaat


# ── YouTube (gratis, geen sleutel: cijfers staan in de zoekpagina) ──────────
def _yt_getal(tekst: str) -> int:
    """'1,2 mln. weergaven' / '12K views' → int. Onleesbaar → 0."""
    if not tekst:
        return 0
    t = tekst.lower().replace("\xa0", " ")
    m = re.search(r"([\d.,]+)\s*(mln|mio|m|k|d|dzd)?", t)
    if not m:
        return 0
    getal = m.group(1)
    # NL gebruikt komma als decimaalteken, EN de punt. Bij een achtervoegsel is
    # het laatste scheidingsteken altijd decimaal; zonder achtervoegsel zijn het
    # duizendtallen die we simpelweg weghalen.
    achtervoegsel = m.group(2) or ""
    if achtervoegsel:
        getal = getal.replace(".", "@").replace(",", "@")
        deel = getal.split("@")
        getal = deel[0] + ("." + deel[-1] if len(deel) > 1 else "")
    else:
        getal = re.sub(r"[.,]", "", getal)
    try:
        waarde = float(getal)
    except ValueError:
        return 0
    factor = {"k": 1_000, "d": 1_000, "dzd": 1_000,
              "m": 1_000_000, "mln": 1_000_000, "mio": 1_000_000}.get(achtervoegsel, 1)
    return int(waarde * factor)


def _yt_zoek(query: str, niche: str, max_items: int = 20) -> list[dict]:
    """YouTube-zoekpagina, gefilterd op Shorts (sp=EgQQARgB = korte video's)."""
    url = ("https://www.youtube.com/results?search_query="
           + urllib.parse.quote(query) + "&sp=EgIYAQ%253D%253D")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"   ! YouTube '{query}' mislukt: {type(e).__name__}", file=sys.stderr)
        return []

    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    uit: list[dict] = []

    def loop(node):
        if len(uit) >= max_items:
            return
        if isinstance(node, dict):
            vr = node.get("videoRenderer")
            if vr:
                kanaal = ((vr.get("ownerText") or {}).get("runs") or [{}])[0]
                titel = "".join(r.get("text", "") for r in
                                ((vr.get("title") or {}).get("runs") or []))
                views = _yt_getal(((vr.get("viewCountText") or {}).get("simpleText") or ""))
                uit.append({
                    "platform": "YouTube",
                    "niche": niche,
                    "taal": "nl" if any(w in query for w in ("verkopen", "kringloop", "tips ")) else "en",
                    "gevonden_via": query,
                    "handle": (kanaal.get("navigationEndpoint", {})
                               .get("browseEndpoint", {})
                               .get("canonicalBaseUrl", "") or "").lstrip("/"),
                    "naam": kanaal.get("text", ""),
                    "volgers": 0,  # staat niet in de zoekpagina
                    "video_id": vr.get("videoId", ""),
                    "url": f"https://www.youtube.com/watch?v={vr.get('videoId','')}",
                    "tekst": titel[:300],
                    "datum": "",  # alleen 'x weken geleden' — te grof om op te rekenen
                    "views": views,
                    "likes": 0, "comments": 0, "shares": 0, "saves": 0,
                    "duur": 0, "sound": "",
                })
            for v in node.values():
                loop(v)
        elif isinstance(node, list):
            for v in node:
                loop(v)

    loop(data)
    return uit


def verzamel_youtube(query_limiet: int | None) -> list[dict]:
    import urllib.parse  # noqa: F401  (gebruikt in _yt_zoek via globals)
    uit: list[dict] = []
    for niche, cfg in NICHES.items():
        for q in cfg.get("youtube", [])[:query_limiet]:
            print(f"  YouTube '{q}' ({niche}) …", flush=True)
            uit.extend(_yt_zoek(q, niche))
    return uit


# ── Hulpjes ─────────────────────────────────────────────────────────────────
def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _datum(v) -> str:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


# ── Van losse video's naar een lijst kandidaat-creators ─────────────────────
def bundel_per_creator(videos: list[dict]) -> list[dict]:
    """
    Rangschikt creators op bruikbaarheid, niet op grootte.

    Drie dingen tellen mee, in deze volgorde:
      1. Hoe vaak hij opduikt in onze zoektermen — dat is het niche-bewijs.
      2. Zijn mediane engagement-ratio — het gemiddelde wordt kapotgemaakt door
         één uitschieter, de mediaan niet. Dit zegt of zijn publiek écht kijkt.
      3. Zijn mediane views — als ondergrens, niet als hoofdmaat, anders staan
         hier straks alleen maar grote accounts.

    Bewust géén platformweging: een creator die op twee platforms opduikt hoort
    juist bovenaan, en dat gebeurt vanzelf via punt 1.
    """
    per: dict[tuple[str, str], dict] = {}
    for v in videos:
        if not v["handle"]:
            continue
        sleutel = (v["platform"], v["handle"])
        c = per.setdefault(sleutel, {
            "platform": v["platform"], "handle": v["handle"], "naam": v["naam"],
            "volgers": 0, "videos": [], "niches": {}, "talen": {}, "bronnen": set(),
        })
        c["volgers"] = max(c["volgers"], v["volgers"])
        c["naam"] = c["naam"] or v["naam"]
        c["videos"].append(v)
        c["niches"][v["niche"]] = c["niches"].get(v["niche"], 0) + 1
        c["talen"][v["taal"]] = c["talen"].get(v["taal"], 0) + 1
        c["bronnen"].add(v["gevonden_via"])

    uit = []
    for c in per.values():
        vs = c["videos"]
        views = [v["views"] for v in vs if v["views"] > 0]
        ratios = [(v["likes"] + v["comments"] + v["shares"] + v["saves"]) / v["views"] * 100
                  for v in vs if v["views"] > 0]
        med_views = int(statistics.median(views)) if views else 0
        med_ratio = round(statistics.median(ratios), 2) if ratios else 0.0
        beste = max(vs, key=lambda v: v["views"])
        uit.append({
            "platform": c["platform"],
            "handle": c["handle"],
            "naam": c["naam"],
            "volgers": c["volgers"],
            "aantal_hits": len(vs),
            "niche": max(c["niches"], key=c["niches"].get),
            "niches": c["niches"],
            "taal": max(c["talen"], key=c["talen"].get),
            "bronnen": sorted(c["bronnen"]),
            "mediaan_views": med_views,
            "mediaan_engagement_pct": med_ratio,
            "top_views": beste["views"],
            "top_url": beste["url"],
            "top_tekst": beste["tekst"][:140],
            # Rangschikking: niche-bewijs weegt het zwaarst, dan betrokkenheid,
            # dan pas bereik. De logaritme houdt grote accounts binnen de perken.
            "score": round(
                len(vs) * 10
                + med_ratio * 3
                + (med_views ** 0.35) / 5, 1),
        })
    uit.sort(key=lambda c: c["score"], reverse=True)
    return uit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snel", action="store_true",
                    help="kleine testronde: 1 hashtag en 1 zoekterm per hoek")
    ap.add_argument("--geen-youtube", action="store_true")
    ap.add_argument("--geen-tiktok", action="store_true")
    args = ap.parse_args()

    limiet = 1 if args.snel else None
    scrolls = 1 if args.snel else 3

    videos: list[dict] = []
    if not args.geen_tiktok:
        print("TikTok verzamelen …")
        videos += asyncio.run(verzamel_tiktok(scrolls, limiet))
    if not args.geen_youtube:
        print("YouTube verzamelen …")
        videos += verzamel_youtube(limiet)

    creators = bundel_per_creator(videos)
    UITVOER.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    pad = UITVOER / f"trends-verkenning-{stempel}.json"
    pad.write_text(json.dumps({
        "gedraaid_op": datetime.now(timezone.utc).isoformat(),
        "aantal_videos": len(videos),
        "aantal_creators": len(creators),
        "creators": creators,
        "videos": videos,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{len(videos)} video's, {len(creators)} creators → {pad}")
    print(f"\n{'#':>3} {'platform':9} {'handle':26} {'views':>9} {'eng%':>6} {'hits':>4}  niche")
    for i, c in enumerate(creators[:40], 1):
        print(f"{i:>3} {c['platform']:9} @{c['handle'][:25]:25} "
              f"{c['mediaan_views']:>9,} {c['mediaan_engagement_pct']:>6} "
              f"{c['aantal_hits']:>4}  {c['niche']}")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noodzakelijk voor _yt_zoek
    sys.exit(main())
