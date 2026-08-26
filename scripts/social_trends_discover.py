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
import os
import re
import statistics
import sys
import urllib.parse
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
        "tiktok_nl": ["vinted", "vintednederland", "vintedtips", "tweedehands",
                      "marktplaats", "vintedverkopen", "tweedehandsverkopen"],
        "tiktok_en": ["reseller", "ebayreseller", "depopseller", "poshmarkreseller",
                      "vintedseller", "resellercommunity"],
        "youtube": ["vinted verkopen tips", "reseller tips 2026",
                    "how to sell on vinted", "ebay reseller haul"],
        "instagram_nl": ["vinted", "tweedehands"],
        "instagram_en": ["reseller", "ebayreseller"],
    },
    "thrifting": {
        "titel": "Tweedehands mode & thrifting",
        "tiktok_nl": ["tweedehandskleding", "kringloop", "vintagekleding",
                      "kringloopwinkel", "thriftnederland"],
        "tiktok_en": ["thrifthaul", "thrifting", "vintagefashion", "thriftwithme"],
        "youtube": ["thrift haul 2026", "kringloop haul", "vintage fashion finds"],
        "instagram_nl": ["kringloop"],
        "instagram_en": ["thrifthaul", "vintagefashion"],
    },
    "tools": {
        "titel": "Tools & software voor verkopers",
        "tiktok_nl": ["crosslisten", "verkooptips"],
        "tiktok_en": ["crosslisting", "crosslistingapp", "resellersoftware"],
        "youtube": ["crosslisting app review", "list perfectly vs vendoo"],
        "instagram_nl": [],
        "instagram_en": ["crosslisting"],
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
        "sound_id": str(muziek.get("id") or ""),
        # Het staande beeldje van de video. We slaan de URL op, niet het plaatje:
        # TikToks CDN-links verlopen na een paar dagen, dus wie ze later wil
        # tonen moet ze meteen ophalen (zie haal_beeldjes).
        "beeld": ((it.get("video") or {}).get("cover")
                  or (it.get("video") or {}).get("originCover") or ""),
        "hashtags": re.findall(r"#(\w+)", it.get("desc") or "")[:12],
        # De link naar de ondertiteling van TikTok zelf. Dit is het gesproken
        # woord, en daarmee de echte hook: wat de maker in de eerste seconden
        # zégt. De link verloopt binnen enkele uren, dus we halen hem binnen
        # dezelfde browsersessie op (zie _haal_ondertitels).
        "vtt": _kies_ondertitel(it),
    }


def _kies_ondertitel(it: dict) -> str:
    """
    Kiest de bruikbaarste ondertitelspoor van een TikTok-video.

    TikTok levert soms meerdere sporen: het origineel (ASR, wat er echt gezegd
    is) en machinevertalingen. Voor hookonderzoek willen we het origineel —
    een vertaling verandert precies de woordkeuze die we meten.
    """
    sporen = (it.get("video") or {}).get("subtitleInfos") or []
    if not sporen:
        return ""
    origineel = [s for s in sporen if (s.get("Source") or "").upper() == "ASR"]
    keuze = (origineel or sporen)[0]
    return f"{keuze.get('LanguageCodeName', '')}|{keuze.get('Url') or ''}"


def _vtt_naar_zinnen(tekst: str) -> list[tuple[float, str]]:
    """WebVTT omzetten naar (starttijd in seconden, zin)."""
    uit: list[tuple[float, str]] = []
    blokken = re.split(r"\n\s*\n", tekst.replace("\r", ""))
    for blok in blokken:
        m = re.search(r"(\d\d):(\d\d):(\d\d)[.,](\d+)\s*-->", blok)
        if not m:
            continue
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
        regels = [r.strip() for r in blok.split("\n")[1:] if r.strip() and "-->" not in r]
        zin = " ".join(regels).strip()
        if zin:
            uit.append((sec, zin))
    return uit


async def _haal_ondertitels(ctx, rijen: list[dict]) -> int:
    """
    Haalt het gesproken woord op voor de video's die ondertiteling hebben.

    Moet binnen dezelfde browsersessie: de ondertitel-links zijn ondertekend en
    verlopen. We bewaren twee dingen: de eerste 3 seconden (de hook waarmee
    iemand blijft kijken of wegveegt) en de eerste 15 seconden (de belofte die
    daarop volgt). Ook het spreektempo, want dat blijkt op korte video's een
    eigen signaal.
    """
    kandidaten = [r for r in rijen if r.get("vtt")]
    if not kandidaten:
        return 0
    gelukt = 0
    for rij in kandidaten:
        taal, _, link = rij["vtt"].partition("|")
        try:
            antwoord = await ctx.request.get(
                link, headers={"Referer": "https://www.tiktok.com/"}, timeout=20000)
            if antwoord.status != 200:
                continue
            zinnen = _vtt_naar_zinnen(await antwoord.text())
        except Exception:
            continue
        if not zinnen:
            continue
        rij["stem_taal"] = taal[:3]   # nld, eng, deu, pol …
        rij["gesproken_3s"] = " ".join(z for t, z in zinnen if t < 3.0)[:200]
        rij["gesproken_15s"] = " ".join(z for t, z in zinnen if t < 15.0)[:600]
        eind = max(t for t, _ in zinnen) or 1
        woorden = sum(len(z.split()) for _, z in zinnen)
        rij["spreektempo"] = round(woorden / max(eind, 1), 2)
        gelukt += 1
    for rij in rijen:
        rij.pop("vtt", None)   # de link is na deze ronde toch dood
    return gelukt


async def verzamel_tiktok(scrolls: int, hashtag_limiet: int | None) -> list[dict]:
    from playwright.async_api import async_playwright
    # playwright-stealth is optioneel. Het staat er niet en het hoeft ook niet:
    # wat TikTok tevreden houdt is de vlag --disable-blink-features hieronder,
    # plus een verse sessie per hashtag. De oude waarschuwing hier beweerde dat
    # het zonder stealth mis zou gaan, en dat klopte niet — dat is elke ronde
    # een loos alarm in de logs.
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None

    opdrachten: list[tuple[str, str, str]] = []  # (niche, taal, hashtag)
    for niche, cfg in NICHES.items():
        for taal, sleutel in (("nl", "tiktok_nl"), ("en", "tiktok_en")):
            for tag in cfg.get(sleutel, [])[:hashtag_limiet]:
                opdrachten.append((niche, taal, tag))

    resultaat: list[dict] = []
    gezien: set[str] = set()
    leeg_op_rij = 0

    # Elke hashtag krijgt een verse sessie. Hergebruikten we één browser, dan
    # leverde alleen de eerste hashtag data op en kwam al het volgende leeg terug:
    # TikTok telt de verzoeken per sessie en zet je daarna op stil. Een nieuwe
    # context per hashtag, met een pauze ertussen, blijft binnen wat een normale
    # bezoeker doet. Het kost ~25 seconden per hashtag; dat is de prijs van gratis.
    async with async_playwright() as p:
        for i, (niche, taal, tag) in enumerate(opdrachten, 1):
            print(f"  [{i}/{len(opdrachten)}] TikTok #{tag} ({niche}/{taal}) …",
                  end="", flush=True)
            nieuw_aantal = 0
            browser = await p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"])
            try:
                ctx = await browser.new_context(
                    locale="nl-NL", user_agent=UA,
                    viewport={"width": 1400, "height": 900})
                page = await ctx.new_page()
                if stealth_async:
                    try:
                        await stealth_async(page)
                    except Exception:
                        pass
                for it in await _tiktok_tag(page, tag, scrolls):
                    vid = str(it.get("id") or "")
                    if not vid or vid in gezien:
                        continue
                    gezien.add(vid)
                    rij = _tiktok_norm(it, niche, taal, tag)
                    if rij:
                        resultaat.append(rij)
                        nieuw_aantal += 1
                verse = resultaat[-nieuw_aantal:] if nieuw_aantal else []
                met_stem = await _haal_ondertitels(ctx, verse)
                print(f" {nieuw_aantal} video's ({met_stem} met gesproken tekst)",
                      flush=True)
            finally:
                await browser.close()

            # Blijft het drie hashtags achter elkaar leeg, dan is niet de hashtag
            # het probleem maar wij: doorgaan levert alleen meer stilte op.
            leeg_op_rij = leeg_op_rij + 1 if nieuw_aantal == 0 else 0
            if leeg_op_rij >= 3:
                print("  ! drie lege hashtags op rij — TikTok houdt de boot af, "
                      "ronde afgebroken", file=sys.stderr)
                break
            if i < len(opdrachten):
                await asyncio.sleep(8)
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
                               .get("canonicalBaseUrl", "") or "").lstrip("/@"),
                    "naam": kanaal.get("text", ""),
                    "volgers": 0,  # staat niet in de zoekpagina
                    "video_id": vr.get("videoId", ""),
                    "url": f"https://www.youtube.com/watch?v={vr.get('videoId','')}",
                    "tekst": titel[:300],
                    "datum": _yt_geleden(
                        (vr.get("publishedTimeText") or {}).get("simpleText") or ""),
                    # De zoekpagina zegt "3 weken geleden", niet "17 maart". Dat is
                    # grof, maar het alternatief is geen datum, en zonder datum telt
                    # een video in geen enkel tijdvenster mee — dan staat YouTube er
                    # wel maar doet het nergens aan mee. We zetten er een vlag bij,
                    # zodat de 7-dagenlaag deze video's kan overslaan: "1 week
                    # geleden" kan alles tussen 7 en 13 dagen zijn.
                    "datum_geschat": True,
                    "views": views,
                    "likes": 0, "comments": 0, "shares": 0, "saves": 0,
                    "duur": 0, "sound": "", "sound_id": "",
                    "beeld": (((vr.get("thumbnail") or {}).get("thumbnails") or [{}])[-1]
                              .get("url", "")),
                    "hashtags": re.findall(r"#(\w+)", titel)[:12],
                })
            for v in node.values():
                loop(v)
        elif isinstance(node, list):
            for v in node:
                loop(v)

    loop(data)
    return uit


# ── YouTube verrijken: van 'alleen views' naar echte cijfers ────────────────
# De zoekpagina geeft alleen views en een vage "3 weken geleden". Daarmee kun
# je niets vergelijken: zonder datum geen tijdvenster, zonder likes geen
# engagement. Twee wegen om dat op te lossen, in deze volgorde:
#
#   1. De officiële YouTube Data API, als er een sleutel is. Die geeft likes,
#      reacties, duur en de exacte datum, 50 video's per verzoek, gratis binnen
#      een dagbudget dat we nooit halen. Dit is de goede weg.
#   2. Anders de videopagina zelf. Die geeft datum en duur, maar geen likes:
#      YouTube haalde dat getal uit de HTML. Beter dan niets, minder dan (1).
def _yt_via_api(rijen: list[dict], sleutel: str) -> int:
    raak = 0
    ids = [r["video_id"] for r in rijen if r.get("video_id")]
    per_id = {r["video_id"]: r for r in rijen}
    for i in range(0, len(ids), 50):
        blok = ids[i:i + 50]
        url = ("https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet,"
               "contentDetails&id=" + ",".join(blok) + "&key=" + sleutel)
        try:
            data = json.loads(urllib.request.urlopen(url, timeout=30).read())
        except Exception as e:
            print(f"   ! YouTube-API mislukt: {type(e).__name__} — terug naar de "
                  f"videopagina", file=sys.stderr)
            return raak
        for item in data.get("items", []):
            rij = per_id.get(item.get("id"))
            if not rij:
                continue
            st = item.get("statistics") or {}
            sn = item.get("snippet") or {}
            rij["views"] = _int(st.get("viewCount")) or rij["views"]
            rij["likes"] = _int(st.get("likeCount"))
            rij["comments"] = _int(st.get("commentCount"))
            rij["datum"] = (sn.get("publishedAt") or "")[:10]
            rij["datum_geschat"] = False
            rij["duur"] = _iso_duur((item.get("contentDetails") or {}).get("duration", ""))
            rij["hashtags"] = re.findall(r"#(\w+)", (sn.get("description") or ""))[:12]
            raak += 1
    return raak


def _yt_geleden(tekst: str) -> str:
    """"3 weken geleden" omrekenen naar een datum. Nederlands en Engels."""
    # Let op de Nederlandse meervouden: "weken" bevat niet "week" en "jaren"
    # niet "jaar". Op die twee ging het eerst mis en kregen alle Nederlandse
    # YouTube-resultaten stilletjes geen datum.
    m = re.search(r"(\d+)\s*(second|seconde|minu|uur|hour|minute|dag|day|"
                  r"wek|week|maand|month|jaar|jaren|year)", tekst.lower())
    if not m:
        return ""
    aantal, eenheid = int(m.group(1)), m.group(2)
    dagen = {"seconde": 0, "second": 0, "minu": 0, "minute": 0, "uur": 0, "hour": 0,
             "dag": 1, "day": 1, "wek": 7, "week": 7, "maand": 30, "month": 30,
             "jaar": 365, "jaren": 365, "year": 365}[eenheid] * aantal
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=dagen)).strftime("%Y-%m-%d")


def _iso_duur(v: str) -> int:
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", v or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def verrijk_youtube(rijen: list[dict]) -> None:
    rijen = [r for r in rijen if r["platform"] == "YouTube"]
    if not rijen:
        return
    sleutel = os.environ.get("YT_API_KEY", "").strip()
    if sleutel:
        raak = _yt_via_api(rijen, sleutel)
        print(f"  YouTube verrijkt via de API: {raak}/{len(rijen)} "
              f"(met likes en reacties)", flush=True)
        if raak:
            return
    zonder = [r for r in rijen if not r.get("datum")]
    print(f"  YouTube: {len(rijen) - len(zonder)}/{len(rijen)} video's met een "
          f"geschatte datum uit de zoekpagina (geen likes). Zet YT_API_KEY als "
          f"secret voor exacte datums, likes en reacties.", flush=True)
    if zonder:
        print(f"  ! {len(zonder)} YouTube-video's zonder datum — die tellen in geen "
              f"enkel tijdvenster mee", file=sys.stderr)


# ── Instagram ───────────────────────────────────────────────────────────────
# Instagram is het enige platform dat niet gratis kan. Hashtagpagina's zitten
# sinds 2024 achter de inlog, en inloggen met een echt account om te schrapen is
# precies waar accounts voor geblokkeerd worden — dat risico is het niet waard.
# Daarom loopt Instagram via Apify, dat de rekening en het risico overneemt.
#
# Bewust zuinig ingesteld: een klein aantal posts per hashtag, en alleen de
# hashtags die er in de meting toe doen. Zonder token slaat dit stil over, dan
# is het rapport gewoon een rapport zonder Instagram in plaats van een fout.
IG_ACTOR = "apify~instagram-hashtag-scraper"
IG_PER_HASHTAG = 30


def _ig_norm(post: dict, niche: str, taal: str, tag: str) -> dict | None:
    handle = post.get("ownerUsername") or ""
    if not handle:
        return None
    views = _int(post.get("videoPlayCount") or post.get("videoViewCount"))
    tekst = (post.get("caption") or "")[:300]
    return {
        "platform": "Instagram",
        "niche": niche, "taal": taal, "gevonden_via": f"#{tag}",
        "handle": handle, "naam": post.get("ownerFullName") or "",
        "volgers": 0,
        "video_id": str(post.get("id") or post.get("shortCode") or ""),
        "url": post.get("url") or f"https://www.instagram.com/p/{post.get('shortCode','')}/",
        "tekst": tekst,
        "datum": (post.get("timestamp") or "")[:10],
        "views": views,
        "likes": _int(post.get("likesCount")),
        "comments": _int(post.get("commentsCount")),
        # Instagram geeft delen en bewaren niet vrij. Nul invullen zou suggereren
        # dat het gemeten is en nul was; het is niet gemeten. De viraliteitsscore
        # slaat Instagram daarom over, net als YouTube zonder likes.
        "shares": 0, "saves": 0,
        "duur": _int(post.get("videoDuration")),
        "sound": "", "sound_id": "",
        "beeld": post.get("displayUrl") or "",
        "hashtags": re.findall(r"#(\w+)", tekst)[:12],
    }


def verzamel_instagram(hashtag_limiet: int | None) -> list[dict]:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print("  Instagram overgeslagen: geen APIFY_TOKEN "
              "(hashtagpagina's zijn niet zonder inlog te lezen)", flush=True)
        return []

    opdrachten = []
    for niche, cfg in NICHES.items():
        for taal, sleutel in (("nl", "instagram_nl"), ("en", "instagram_en")):
            for tag in cfg.get(sleutel, [])[:hashtag_limiet]:
                opdrachten.append((niche, taal, tag))
    if not opdrachten:
        return []

    uit: list[dict] = []
    gezien: set[str] = set()
    for niche, taal, tag in opdrachten:
        print(f"  Instagram #{tag} ({niche}/{taal}) …", end="", flush=True)
        try:
            verzoek = urllib.request.Request(
                f"https://api.apify.com/v2/acts/{IG_ACTOR}/run-sync-get-dataset-items"
                f"?token={token}&format=json&timeout=180",
                data=json.dumps({"hashtags": [tag],
                                 "resultsLimit": IG_PER_HASHTAG}).encode(),
                headers={"Content-Type": "application/json"})
            posts = json.loads(urllib.request.urlopen(verzoek, timeout=200).read())
        except Exception as e:
            # Meestal: het maandtegoed is op. Dat is geen storing om te herstellen,
            # dat is een rekening. De rest van de meting gaat gewoon door.
            print(f" mislukt ({type(e).__name__})", flush=True)
            continue
        nieuw = 0
        for post in posts if isinstance(posts, list) else []:
            rij = _ig_norm(post, niche, taal, tag)
            if not rij or not rij["video_id"] or rij["video_id"] in gezien:
                continue
            gezien.add(rij["video_id"])
            uit.append(rij)
            nieuw += 1
        print(f" {nieuw} posts", flush=True)
    return uit


# De officiële bovengrens van een Short. YouTube's zoekfilter voor korte video's
# laat er in de praktijk gewone video's doorheen glippen — er stonden er van drie
# minuten tussen. Dat konden we eerder niet zien omdat we de duur niet hadden;
# met de API-sleutel wel, en dan hoort een video van 3,5 minuut niet mee te tellen
# in een meting over kortevideo-hooks.
YT_MAX_SECONDEN = 180


def verzamel_youtube(query_limiet: int | None) -> list[dict]:
    uit: list[dict] = []
    for niche, cfg in NICHES.items():
        for q in cfg.get("youtube", [])[:query_limiet]:
            print(f"  YouTube '{q}' ({niche}) …", flush=True)
            uit.extend(_yt_zoek(q, niche))
    verrijk_youtube(uit)

    # Alleen filteren als we de duur écht weten. Zonder API-sleutel staat duur op
    # nul en zouden we alles weggooien.
    met_duur = [v for v in uit if v.get("duur")]
    if met_duur:
        kort = [v for v in uit
                if not v.get("duur") or v["duur"] <= YT_MAX_SECONDEN]
        weg = len(uit) - len(kort)
        if weg:
            print(f"  {weg} YouTube-video's weggelaten: langer dan "
                  f"{YT_MAX_SECONDEN} seconden, dus geen Short", flush=True)
        return kort
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
            # dan pas bereik. De macht < 1 houdt grote accounts binnen de perken.
            #
            # YouTube krijgt een eigen formule: de zoekpagina geeft geen likes of
            # reacties, alleen views. Zou YouTube in dezelfde formule meedoen, dan
            # scoort elke YouTuber 0 op betrokkenheid en verdwijnt hij onderaan —
            # niet omdat hij slecht is, maar omdat wij het niet kunnen meten.
            #
            # Het aantal hits weegt zwaar: één video die toevallig #thrifting
            # gebruikte zegt niets, vijftien video's over meerdere zoektermen
            # zeggen dat dit account écht in de niche zit. De engagement-ratio is
            # afgetopt op 25%, want daarboven gaat het bijna altijd om een kleine
            # video waarbij de ratio wiskundig opblaast in plaats van iets te
            # bewijzen.
            "score": round(
                len(vs) * 25 + min(med_ratio, 25) * 2 + (med_views ** 0.35) / 5, 1)
            if c["platform"] != "YouTube" else
            round(len(vs) * 25 + (med_views ** 0.35), 1),
        })
    # Per platform sorteren en pas daarna samenvoegen, zodat platforms met minder
    # meetbare velden niet stelselmatig onderaan belanden.
    uit.sort(key=lambda c: (c["platform"], -c["score"]))
    return uit



# ── Goedkeurpagina ──────────────────────────────────────────────────────────
# De verkenningsronde levert honderden accounts op, maar de meeste zijn ruis:
# één video die toevallig een hashtag gebruikte. Deze pagina toont alleen wat
# minstens twee keer opdook, met het bewijs erbij, zodat goedkeuren neerkomt op
# wegstrepen wat niet klopt in plaats van alles nalopen.
_KOP = """<title>Creatorlijst Omnivaleur</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Newsreader:opsz,wght@6..72,400;6..72,600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{
  --papier:#EEF1F1; --kaart:#F8FAFA; --rand:#D2DAD9;
  --inkt:#151B1B; --zacht:#5A6867; --accent:#0E6F6B; --accent-zacht:#DCEAE8;
  --waarschuwing:#A8441C;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --papier:#0D1212; --kaart:#151D1D; --rand:#293636;
    --inkt:#E9EFEE; --zacht:#93A3A1; --accent:#5FD3C8; --accent-zacht:#16302E;
    --waarschuwing:#E08A5F;
  }
}
:root[data-theme="dark"]{
  --papier:#0D1212; --kaart:#151D1D; --rand:#293636;
  --inkt:#E9EFEE; --zacht:#93A3A1; --accent:#5FD3C8; --accent-zacht:#16302E;
  --waarschuwing:#E08A5F;
}
*{box-sizing:border-box}
body{background:var(--papier);color:var(--inkt);
  font-family:"Newsreader",Georgia,serif;font-size:17px;line-height:1.6;
  margin:0;padding:clamp(20px,4vw,56px)}
.wrap{max-width:1080px;margin:0 auto;display:flex;flex-direction:column;gap:40px}
h1,h2,h3{font-family:"Bricolage Grotesque",system-ui,sans-serif;
  text-wrap:balance;margin:0;line-height:1.15;font-weight:700}
h1{font-size:clamp(30px,4.4vw,46px);letter-spacing:-.02em}
h2{font-size:22px;letter-spacing:-.01em}
.lead{max-width:62ch;color:var(--zacht);margin:0}
.eyebrow{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin:0}
header{display:flex;flex-direction:column;gap:12px;
  border-bottom:2px solid var(--inkt);padding-bottom:24px}
.cijfers{display:flex;flex-wrap:wrap;gap:28px;margin-top:6px}
.cijfer{display:flex;flex-direction:column;gap:2px}
.cijfer b{font-family:"JetBrains Mono",monospace;font-size:26px;font-weight:600;
  font-variant-numeric:tabular-nums}
.cijfer span{font-size:12px;color:var(--zacht);text-transform:uppercase;
  letter-spacing:.09em;font-family:"Bricolage Grotesque",sans-serif}
section{display:flex;flex-direction:column;gap:16px}
.sectiekop{display:flex;flex-direction:column;gap:4px}
.tabelbox{overflow-x:auto;border:1px solid var(--rand);border-radius:3px;
  background:var(--kaart)}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:15px}
th{font-family:"Bricolage Grotesque",sans-serif;font-size:11px;font-weight:500;
  text-transform:uppercase;letter-spacing:.09em;color:var(--zacht);
  text-align:left;padding:11px 14px;border-bottom:1px solid var(--rand);
  white-space:nowrap}
td{padding:12px 14px;border-bottom:1px solid var(--rand);vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-family:"JetBrains Mono",monospace;
  font-variant-numeric:tabular-nums;font-size:14px;white-space:nowrap}
.handle{font-family:"JetBrains Mono",monospace;font-size:14px;font-weight:600}
.handle a{color:var(--inkt);text-decoration:none;
  border-bottom:1px solid var(--accent)}
.handle a:hover,.handle a:focus-visible{color:var(--accent)}
.naam{display:block;font-size:13px;color:var(--zacht);margin-top:2px;
  max-width:34ch}
.hits{display:inline-flex;align-items:center;justify-content:center;
  min-width:30px;padding:2px 7px;border-radius:2px;background:var(--accent-zacht);
  color:var(--accent);font-family:"JetBrains Mono",monospace;font-weight:600;
  font-size:13px}
.vlag{font-family:"Bricolage Grotesque",sans-serif;font-size:11px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--zacht)}
.bewijs{font-size:13px;color:var(--zacht);max-width:40ch}
.bewijs a{color:var(--accent)}
.let{border-left:3px solid var(--waarschuwing);padding:2px 0 2px 16px;
  color:var(--zacht);max-width:62ch}
footer{border-top:1px solid var(--rand);padding-top:20px;font-size:14px;
  color:var(--zacht);max-width:62ch}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
"""


def _rij(c: dict) -> str:
    naam = (c["naam"] or "").replace("<", "&lt;")
    tekst = (c["top_tekst"] or "").replace("<", "&lt;")[:90]
    volgers = f"{c['volgers']:,}".replace(",", ".") if c["volgers"] else "—"
    views = f"{c['mediaan_views']:,}".replace(",", ".")
    bron = ", ".join(c["bronnen"][:3])
    return f"""<tr>
  <td><span class="hits">{c['aantal_hits']}</span></td>
  <td class="handle"><a href="{c['top_url']}" target="_blank" rel="noopener">@{c['handle']}</a>
      <span class="naam">{naam}</span></td>
  <td class="vlag">{c['taal']}</td>
  <td class="num">{volgers}</td>
  <td class="num">{views}</td>
  <td class="num">{c['mediaan_engagement_pct'] or '—'}</td>
  <td class="bewijs">{bron}<br>&ldquo;{tekst}&rdquo;</td>
</tr>"""


def _tabel(rijen: list[dict]) -> str:
    if not rijen:
        return '<p class="lead">Niets gevonden in deze hoek.</p>'
    return ('<div class="tabelbox"><table><thead><tr>'
            '<th>Hits</th><th>Account</th><th>Taal</th>'
            '<th class="num">Volgers</th><th class="num">Med. views</th>'
            '<th class="num">Eng. %</th><th>Bewijs</th>'
            '</tr></thead><tbody>'
            + "".join(_rij(c) for c in rijen)
            + "</tbody></table></div>")


def schrijf_pagina(data: dict, pad: Path) -> Path:
    creators = data["creators"]
    kern = [c for c in creators if c["aantal_hits"] >= 2]
    kern.sort(key=lambda c: -c["score"])
    ruis = len(creators) - len(kern)

    delen = [_KOP, '<div class="wrap"><header>',
             '<p class="eyebrow">Verkenningsronde &middot; '
             + datetime.now().strftime("%d-%m-%Y") + '</p>',
             '<h1>Wie volgen we structureel?</h1>',
             '<p class="lead">Uit ' + f"{data['aantal_videos']:,}".replace(",", ".")
             + " gescande video's kwamen "
             + f"{data['aantal_creators']:,}".replace(",", ".")
             + " accounts. Hieronder staan alleen de "
             + str(len(kern)) + " die <strong>minstens twee keer</strong> opdoken "
             "onder verschillende zoektermen — dat is het bewijs dat ze in de niche "
             "zitten en er niet per ongeluk in vielen. Streep weg wat niet klopt; "
             "wat blijft staan wordt de vaste kern.</p>",
             '<div class="cijfers">'
             f'<div class="cijfer"><b>{data["aantal_videos"]:,}</b><span>video&rsquo;s gemeten</span></div>'
             f'<div class="cijfer"><b>{len(kern)}</b><span>kandidaten</span></div>'
             f'<div class="cijfer"><b>{ruis}</b><span>eenmalig, weggelaten</span></div>'
             '</div>'.replace(",", "."),
             '</header>']

    for niche, cfg in NICHES.items():
        rijen = [c for c in kern if c["niche"] == niche]
        delen.append('<section><div class="sectiekop">'
                     f'<p class="eyebrow">{len(rijen)} accounts</p>'
                     f'<h2>{cfg["titel"]}</h2></div>'
                     + _tabel(rijen) + '</section>')

    delen.append(
        '<section><h2>Wat hier nog niet in staat</h2>'
        '<p class="let">Instagram ontbreekt. Hashtagpagina&rsquo;s zijn daar alleen na '
        'inloggen te zien, dus dat loopt via Apify — en die gratis maandlimiet is '
        'op. Zodra die reset komt Instagram erbij.</p>'
        '<p class="let">De engagement-kolom is bij YouTube leeg. De zoekpagina geeft '
        'daar alleen views, geen likes of reacties. YouTube wordt daarom apart '
        'gerangschikt en niet tegen TikTok afgezet.</p></section>')

    delen.append('<footer>Alle cijfers zijn rechtstreeks van het platform '
                 'afgelezen op ' + datetime.now().strftime("%d-%m-%Y om %H:%M")
                 + '. Niets is geschat. &ldquo;Hits&rdquo; is het aantal keer dat '
                 'dit account opdook onder onze zoektermen; &ldquo;med. views&rdquo; '
                 'is de mediaan, niet het gemiddelde, zodat één uitschieter het '
                 'beeld niet vertekent.</footer></div>')

    pad.write_text("\n".join(delen), encoding="utf-8")
    return pad

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snel", action="store_true",
                    help="kleine testronde: 1 hashtag en 1 zoekterm per hoek")
    ap.add_argument("--geen-youtube", action="store_true")
    ap.add_argument("--geen-tiktok", action="store_true")
    ap.add_argument("--pagina", metavar="JSON",
                    help="maak alleen de goedkeurpagina uit een eerdere ronde")
    args = ap.parse_args()

    if args.pagina:
        bron = Path(args.pagina)
        data = json.loads(bron.read_text(encoding="utf-8"))
        data["creators"] = bundel_per_creator(data["videos"])
        data["aantal_creators"] = len(data["creators"])
        uit = schrijf_pagina(data, bron.with_suffix(".html"))
        print(f"goedkeurpagina → {uit}")
        return 0

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

    schrijf_pagina({"aantal_videos": len(videos), "aantal_creators": len(creators),
                    "creators": creators}, pad.with_suffix(".html"))
    print(f"\n{len(videos)} video's, {len(creators)} creators → {pad}")
    print(f"goedkeurpagina → {pad.with_suffix('.html')}")
    for platform in sorted({c["platform"] for c in creators}):
        rij = [c for c in creators if c["platform"] == platform][:25]
        print(f"\n── {platform} — top {len(rij)} ──")
        print(f"{'#':>3} {'handle':26} {'views':>10} {'eng%':>6} {'hits':>4}  niche")
        for i, c in enumerate(rij, 1):
            print(f"{i:>3} @{c['handle'][:25]:25} {c['mediaan_views']:>10,} "
                  f"{c['mediaan_engagement_pct']:>6} {c['aantal_hits']:>4}  {c['niche']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
