"""
Vier manieren om aan Instagram-handles te komen, met één uitvoervorm.

WAAROM VIER
Apify's keyword-discovery is op een gratis account gelimiteerd tot 5 kandidaten per
run. Die limiet zit op de DISCOVERY-actor, niet op Instagram-data in het algemeen —
en dat is precies het gat waar deze module doorheen kruipt.

WAT ER LIVE UIT KWAM (2026-07, allemaal echt gedraaid, niet aangenomen):

  hashtag  WINNAAR. 30 posts op #tweedehandskleding gaven 22 unieke auteurs, vrijwel
           allemaal exact de doelgroep (Kringloopwinkel La Vida, Ratjetoe Leiden,
           Vintique, Appel & Ei Enschede, Vincentshop Tilburg). Geen 5-limiet, ~$0,05
           per hashtag. Volgersaantal komt niet mee — vandaar de losse enrich-stap.

  local    Betrouwbare vermenigvuldiger. De limiet geldt PER RUN, dus tien losse runs
           met stadsspecifieke termen geven 10 x 5 in plaats van 5. Trager en per
           lead iets duurder, maar het werkt en de leads zijn geografisch gespreid.

  dork     Gratis, maar mager. DuckDuckGo geeft ~2 handles per zoekterm en blokkeert
           na ongeveer zes queries met HTTP 202. Bing gaf 0 (JS-gerenderde HTML).
           Bruikbaar als gratis aanvulling, niet als motor.

  keyword  De bestaande route. Werkt, maar is dus die 5 per run.

BEWUST NIET GEBOUWD: instaloader. Anoniem profielen ophalen is stuk — Instagram gaf
op elk van drie testaccounts een 400 ("ig_business_category_subvertical"). Werkend
krijg je het alleen met ingelogde sessie, en dan zet je je eigen account op het spel
voor data die hier $0,001 per profiel kost. Die ruil is het niet waard.

Elke functie geeft dezelfde vorm terug, zodat de pijplijn de bron niet hoeft te kennen:
    {"handle": str, "method": str, "source": str,
     "full_name": str, "followers": int|None, "hint": str}
"""
from __future__ import annotations

import re
import time

APIFY_SYNC = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

KEYWORD_ACTOR = "afanasenko~instagram-profile-scraper"
# Bewust de OFFICIËLE Apify-actor. coderx/instagram-hashtag-scraper is goedkoper
# ($0,0015 vs $0,0026 per post) en gaf net zulke goede resultaten, maar knijpt een
# gratis account af tot één run per dag — en dat blijkt pas uit een 'error'-rij in
# de dataset, niet uit een foutcode. Deze heeft dat plafond niet.
HASHTAG_ACTOR = "apify~instagram-hashtag-scraper"

# Nederlandstalige termen zijn zelf het landfilter: wie zijn winkel "kringloop" of
# "tweedehands kleding" noemt zit in NL/BE. Engelse termen als "thrift" halen de
# halve wereld binnen.
QUERIES = [
    "vintage kleding", "tweedehands kleding", "kringloop", "kringloopwinkel",
    "vintage winkel", "tweedehands winkel", "vintage shop nederland",
    "thriftshop nl", "vintage meubels", "brocante", "curiosa",
    "preloved kleding", "vintage sieraden", "retro winkel",
]

HASHTAGS = [
    "tweedehandskleding", "kringloopwinkel", "vintagekleding", "kringloopgeluk",
    "vintagenederland", "tweedehandswinkel", "kringloopvondst", "tweedehandsmode",
    "vintagewinkel", "brocante", "vintagemeubels", "secondhandnederland",
]

CITIES = [
    "amsterdam", "rotterdam", "utrecht", "den haag", "eindhoven", "groningen",
    "tilburg", "breda", "nijmegen", "haarlem", "arnhem", "almere",
    "antwerpen", "gent",
]
# Bewust ÉÉN woord per term, want de stad komt er nog achteraan. Live gemeten:
# "kringloop rotterdam" gaf 5 echte Rotterdamse kringloopwinkels, terwijl
# "vintage winkel utrecht" er 0 gaf — Instagram's profielzoek valt om bij drie
# woorden. Twee woorden is hier het plafond.
LOCAL_TERMS = ["kringloop", "vintage", "tweedehands"]

# Instagram-paden die geen account zijn. Zonder deze lijst haalt de dork-regex
# "instagram.com/p/CxYz" binnen als handle "p".
NOT_A_HANDLE = {
    "p", "reel", "reels", "explore", "accounts", "tv", "stories", "directory",
    "about", "legal", "developer", "instagram", "help", "press", "api", "privacy",
    "terms", "web", "graphql", "challenge", "emails", "s",
}

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def _run(actor: str, payload: dict, token: str, timeout: float = 900.0) -> list[dict]:
    """Draai een actor en geef de dataset terug. Faalt ZACHT: bij een reeks van
    veertien losse runs mag één kapotte run de andere dertien niet meenemen."""
    import httpx

    try:
        r = httpx.post(APIFY_SYNC.format(actor=actor),
                       params={"token": token}, json=payload, timeout=timeout)
        if r.status_code >= 400:
            print(f"    ! HTTP {r.status_code}: {r.text[:160]}")
            return []
        return r.json() or []
    except Exception as e:  # noqa: BLE001
        print(f"    ! {type(e).__name__}: {str(e)[:160]}")
        return []


def _rec(handle: str, method: str, source: str, **extra) -> dict | None:
    handle = (handle or "").strip().lstrip("@").rstrip("/").lower()
    if not handle or handle in NOT_A_HANDLE or not re.fullmatch(r"[a-z0-9._]{2,30}", handle):
        return None
    return {"handle": handle, "method": method, "source": source,
            "full_name": extra.get("full_name") or "",
            "followers": extra.get("followers"),
            "hint": (extra.get("hint") or "")[:300]}


# ------------------------------------------------------------------ 1. dork


def from_dork(queries: list[str] | None = None, pages: int = 2,
              delay: float = 4.0) -> list[dict]:
    """Zoekmachine-dorking op site:instagram.com. Gratis, geen token.

    DuckDuckGo begint na ongeveer zes queries met HTTP 202 terug te geven — dat is
    geen fout maar een zachte blokkade. We stoppen dan netjes in plaats van door te
    rammen, want doorrammen levert alleen een langer durende blokkade op.
    """
    import httpx

    queries = queries or [f'site:instagram.com "{q}"' for q in QUERIES[:6]]
    out: list[dict] = []
    seen: set[str] = set()

    with httpx.Client(headers={"User-Agent": _UA}, timeout=25.0,
                      follow_redirects=True) as c:
        for q in queries:
            found = 0
            for page in range(pages):
                params = {"q": q}
                if page:
                    params["s"] = page * 30
                try:
                    r = c.get("https://html.duckduckgo.com/html/", params=params)
                except Exception as e:  # noqa: BLE001
                    print(f"    ! {q}: {e}")
                    break
                if r.status_code == 202:
                    print(f"    · DuckDuckGo blokkeert (202) — dork-bron gestopt")
                    return out
                if r.status_code != 200:
                    break
                hits = re.findall(r"instagram\.com/([A-Za-z0-9._]{2,30})", r.text)
                new = 0
                for h in hits:
                    rec = _rec(h, "dork", q)
                    if rec and rec["handle"] not in seen:
                        seen.add(rec["handle"])
                        out.append(rec)
                        new += 1
                found += new
                if not new:
                    break
                time.sleep(delay)
            print(f"    {found:3d}  {q}")
            time.sleep(delay)
    return out


# --------------------------------------------------------------- 2. hashtag


def from_hashtag(hashtags: list[str] | None = None, per_tag: int = 40,
                 token: str = "") -> list[dict]:
    """Auteurs van posts onder Nederlandse tweedehands-hashtags.

    Dit is de enige bron die zowel volume als precisie geeft: wie post onder
    #kringloopwinkel IS een kringloopwinkel, terwijl wie post onder #thrifthaul een
    koper is. De hashtagkeuze doet dus het meeste werk — kies woorden die een
    verkoper gebruikt en een koper niet.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for tag in (hashtags or HASHTAGS):
        rows = _run(HASHTAG_ACTOR, {
            "hashtags": [tag], "resultsType": "posts", "resultsLimit": per_tag,
        }, token)
        new = 0
        for row in rows:
            # Sommige actors melden een quotum-overschrijding als gewone datarij in
            # plaats van als HTTP-fout. Stil nul posts teruggeven zou hier lijken op
            # "hashtag levert niets op", wat iets heel anders is.
            if row.get("error"):
                print(f"    ! {tag}: {row.get('message') or row['error']}")
                break
            author = row.get("author") or {}
            if author.get("is_private"):
                continue
            rec = _rec(row.get("ownerUsername") or author.get("username"),
                       "hashtag", f"#{tag}",
                       full_name=row.get("ownerFullName") or author.get("full_name"),
                       followers=author.get("follower_count"),
                       hint=" ".join(x for x in (row.get("locationName"),
                                                 row.get("caption")) if x))
            if rec and rec["handle"] not in seen:
                seen.add(rec["handle"])
                out.append(rec)
                new += 1
        print(f"    {new:3d} nieuw uit {len(rows):3d} posts  #{tag}")
    return out


# --------------------------------------------------------------- 3. keyword


def _from_keyword_run(queries: list[str], max_count: int, token: str,
                      exclude: list[str], label: str) -> list[dict]:
    rows = _run(KEYWORD_ACTOR, {
        "operationMode": "keywordDiscovery",
        "searchQueries": queries,
        "maxCountDiscovery": max_count,
        "maxSearchPagesPerQuery": 3,
        "extractEmail": True,
        "excludeAccounts": exclude,
        "clearSavedData": True,
    }, token)
    out = []
    for row in rows:
        handle = (row.get("Account") or "").rstrip("/").rsplit("/", 1)[-1]
        rec = _rec(handle, "keyword", label,
                   full_name=row.get("Full Name"),
                   followers=row.get("Followers Count"),
                   hint=row.get("Biography") or "")
        if rec:
            out.append(rec)
    return out


def from_keyword(queries: list[str] | None = None, max_count: int = 40,
                 token: str = "", exclude: list[str] | None = None) -> list[dict]:
    """De bestaande route: één run over alle zoektermen tegelijk."""
    out = _from_keyword_run(queries or QUERIES, max_count, token, exclude or [], "keyword")
    print(f"    {len(out):3d} kandidaten")
    if len(out) <= 5:
        print("    · 5 of minder = de gratis-plan-limiet. Gebruik 'local' of 'hashtag'.")
    return out


# ----------------------------------------------------------------- 4. local


def from_local(cities: list[str] | None = None, terms: list[str] | None = None,
               max_per_run: int = 5, token: str = "",
               exclude: list[str] | None = None, delay: float = 2.0) -> list[dict]:
    """Dezelfde keyword-discovery, maar opgeknipt in losse runs per stad.

    De gratis-limiet is een plafond PER RUN, niet per dag. Veertien steden x vijf
    kandidaten is zeventig in plaats van vijf, voor dezelfde prijs per kandidaat.
    Traag (elke run kost een minuut of wat) maar volledig binnen de regels van het
    plan — we omzeilen geen betaalmuur, we stellen gewoon kleinere vragen.
    """
    out: list[dict] = []
    seen: set[str] = set()
    exclude = list(exclude or [])
    combos = [(c, t) for c in (cities or CITIES) for t in (terms or LOCAL_TERMS)]

    for city, term in combos:
        query = f"{term} {city}"
        rows = _from_keyword_run([query], max_per_run, token, exclude, query)
        new = 0
        for rec in rows:
            if rec["handle"] in seen:
                continue
            seen.add(rec["handle"])
            rec["method"] = "local"
            out.append(rec)
            new += 1
        # Binnen dezelfde reeks niet twee keer hetzelfde account betalen.
        exclude.extend(r["handle"] for r in rows)
        print(f"    {new:3d} nieuw  {query}")
        time.sleep(delay)
    return out


SOURCES = {
    "dork": from_dork,
    "hashtag": from_hashtag,
    "keyword": from_keyword,
    "local": from_local,
}
