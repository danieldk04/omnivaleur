"""
Wekelijkse scrape van de eigen social-profielen via Apify, voor per-post prestaties
in het marketingrapport. Beantwoordt 'welke content sloeg deze week het beste aan'
op postniveau — iets wat GA4/Search Console niet kunnen (die meten site-verkeer, niet
on-platform bereik/engagement).

Elk platform heeft een eigen Apify-actor met een eigen output-vorm; we normaliseren
alles naar één schema (views/likes/comments/shares/saves/datum/tekst/url/duur) zodat
het rapport ze naast elkaar kan zetten. Omdat overal dezelfde content wordt gepost,
groeperen we ook per 'contentdag' over platforms heen ('welk idee scoorde totaal het
best, en op welk platform').

Faalt overal ZACHT: geen apify_token → lege sectie; één kapotte actor → dat platform
leeg, de rest gaat door. De scrape is traag (~10-20s per platform) dus platforms
draaien parallel, en het rapport roept dit alleen aan wanneer expliciet gevraagd
(zondagse mail + handmatige dashboard-knop) — nooit bij elke paginaweergave.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from backend.config import settings

logger = logging.getLogger(__name__)

# Apify REST: run-sync-get-dataset-items draait de actor en geeft direct de dataset
# terug. Actor-fullnames gebruiken hier '~' i.p.v. '/'.
_APIFY_BASE = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(settings.apify_token)


def _first(item: dict, keys: list[str], default=0):
    """Eerste niet-lege waarde uit een lijst kandidaat-veldnamen (actors verschillen)."""
    for k in keys:
        v = item.get(k)
        if v not in (None, "", []):
            return v
    return default


def _deep(item: dict, path: str, default=0):
    """Geneste waarde via dot-pad (bv. 'pin.repin_count'). Faalt zacht naar default."""
    cur = item
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return cur if cur not in (None, "", []) else default


def _to_int(v) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _iso_date(v) -> str:
    """Normaliseert diverse datumvormen naar 'YYYY-MM-DD' (leeg als onparseerbaar)."""
    if not v:
        return ""
    s = str(v)
    # Unix-timestamp?
    if s.isdigit() and len(s) >= 10:
        try:
            return datetime.fromtimestamp(int(s[:10]), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""
    return s[:10]


def _run_actor(actor: str, payload: dict, timeout: int = 90) -> list[dict]:
    """Draait één Apify-actor synchroon en geeft de dataset-items terug. Zacht falend."""
    import requests

    url = _APIFY_BASE.format(actor=actor.replace("/", "~"))
    try:
        r = requests.post(
            url,
            params={"token": settings.apify_token, "timeout": timeout, "format": "json"},
            json=payload,
            timeout=timeout + 15,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Apify-actor {actor} mislukt: {e}")
        return []


# ---------------------------------------------------------------------------
# Per-platform adapters — geven een lijst genormaliseerde posts terug
# ---------------------------------------------------------------------------
def _norm(platform, *, id, text, url, date, views=0, likes=0, comments=0,
          shares=0, saves=0, duration=0) -> dict:
    eng = likes + comments + shares + saves
    return {
        "platform": platform,
        "id": str(id),
        "text": (text or "").strip(),
        "url": url or "",
        "date": _iso_date(date),
        "views": _to_int(views),
        "likes": _to_int(likes),
        "comments": _to_int(comments),
        "shares": _to_int(shares),
        "saves": _to_int(saves),
        "duration": _to_int(duration),
        "engagement": eng,
        "engagement_rate": round(eng / views * 100, 1) if _to_int(views) else 0.0,
    }


def _fetch_tiktok(handle: str, limit: int) -> list[dict]:
    items = _run_actor("clockworks/tiktok-profile-scraper", {
        "profiles": [handle.lstrip("@")],
        "resultsPerPage": limit,
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadAvatars": False,
        "excludePinnedPosts": False,
    })
    out = []
    for it in items:
        if it.get("text") is None and not it.get("webVideoUrl"):
            continue
        vm = it.get("videoMeta") or {}
        out.append(_norm(
            "TikTok", id=it.get("id"), text=it.get("text"), url=it.get("webVideoUrl"),
            date=it.get("createTimeISO"), views=it.get("playCount"), likes=it.get("diggCount"),
            comments=it.get("commentCount"), shares=it.get("shareCount"),
            saves=it.get("collectCount"), duration=vm.get("duration"),
        ))
    return out


def _fetch_instagram(handle: str, limit: int) -> list[dict]:
    items = _run_actor("apify/instagram-profile-scraper", {"usernames": [handle.lstrip("@")]})
    out = []
    for profile in items:
        for p in (profile.get("latestPosts") or [])[:limit]:
            out.append(_norm(
                "Instagram", id=p.get("id"), text=p.get("caption"), url=p.get("url"),
                date=p.get("timestamp"), views=p.get("videoViewCount"),
                likes=p.get("likesCount"), comments=p.get("commentsCount"),
            ))
    return out


def _fetch_youtube(handle: str, limit: int) -> list[dict]:
    items = _run_actor("grow_media/youtube-channel-video-scraper", {
        "channelHandle": handle if handle.startswith("@") else f"@{handle}",
        "maxResults": limit,
        "sortOrder": "latest",
        "videoType": "all",
    })
    out = []
    for it in items:
        out.append(_norm(
            "YouTube", id=_first(it, ["id", "videoId", "url"], ""),
            text=_first(it, ["title", "text"], ""),
            url=_first(it, ["url", "videoUrl"], ""),
            date=_first(it, ["date", "publishedAt", "uploadDate", "publishDate"], ""),
            views=_first(it, ["viewCount", "views", "numberOfViews"], 0),
            likes=_first(it, ["likes", "likeCount", "numberOfLikes"], 0),
            comments=_first(it, ["comments", "commentsCount", "commentCount", "numberOfComments"], 0),
            duration=_first(it, ["duration", "durationSeconds", "lengthSeconds"], 0),
        ))
    return out


def _fetch_pinterest(handle: str, limit: int) -> list[dict]:
    # Best-effort: Pinterest-scrapers geven doorgaans saves/repins + comments, geen
    # 'views'. Faalt zacht naar leeg als de actor niets bruikbaars teruggeeft.
    items = _run_actor("apify/pinterest-scraper", {
        "startUrls": [{"url": f"https://www.pinterest.com/{handle}/"}],
        "maxItems": limit,
    })
    out = []
    for it in items:
        out.append(_norm(
            "Pinterest", id=_first(it, ["id", "pinId", "url"], ""),
            text=_first(it, ["title", "description", "grid_title"], ""),
            url=_first(it, ["url", "link", "pinUrl"], ""),
            date=_first(it, ["created_at", "date", "createdAt"], ""),
            saves=_first(it, ["repin_count", "saveCount", "saves", "repinCount"], 0),
            comments=_first(it, ["comment_count", "commentCount", "comments"], 0),
        ))
    return out


_ADAPTERS = {
    "TikTok": (_fetch_tiktok, lambda: settings.social_tiktok),
    "Instagram": (_fetch_instagram, lambda: settings.social_instagram),
    "YouTube": (_fetch_youtube, lambda: settings.social_youtube),
    "Pinterest": (_fetch_pinterest, lambda: settings.social_pinterest),
}


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------
def weekly(this_start: str, this_end: str, limit_per_platform: int = 25) -> dict:
    """
    Scrapt alle geconfigureerde platforms (parallel), filtert op de posts van deze
    week (this_start..this_end, ISO 'YYYY-MM-DD'), en bouwt de social-contentsectie:
    top posts, per-platform-totalen en een cross-platform 'per contentdag'-overzicht.
    """
    if not is_configured():
        return {"connected": False}

    handles = {p: fn() for p, (_, fn) in _ADAPTERS.items() if fn()}
    results: dict[str, list[dict]] = {}
    errors: list[str] = []

    def _job(platform: str):
        fetch, _ = _ADAPTERS[platform]
        return platform, fetch(handles[platform], limit_per_platform)

    with ThreadPoolExecutor(max_workers=len(handles) or 1) as ex:
        futures = [ex.submit(_job, p) for p in handles]
        for f in as_completed(futures):
            try:
                platform, posts = f.result()
                results[platform] = posts
            except Exception as e:
                errors.append(str(e))

    # Alleen posts binnen het weekvenster (op datum).
    week_posts: list[dict] = []
    per_platform: list[dict] = []
    for platform, posts in results.items():
        wk = [p for p in posts if p["date"] and this_start <= p["date"] <= this_end]
        per_platform.append({
            "platform": platform,
            "posts_count": len(wk),
            "views": sum(p["views"] for p in wk),
            "engagement": sum(p["engagement"] for p in wk),
        })
        week_posts.extend(wk)

    per_platform.sort(key=lambda x: (x["views"], x["engagement"]), reverse=True)
    top_posts = sorted(week_posts, key=lambda p: (p["views"], p["engagement"]), reverse=True)

    return {
        "connected": True,
        "period": [this_start, this_end],
        "per_platform": per_platform,
        "top_posts": top_posts[:15],
        "by_content": _group_by_content(week_posts),
        "total_posts": len(week_posts),
        "errors": errors,
    }


def _group_by_content(posts: list[dict]) -> list[dict]:
    """
    Overal dezelfde content → groepeer op contentdag en tel bereik/engagement over
    alle platforms op. Zo zie je welk idee totaal het best scoorde en op welk platform.
    """
    groups: dict[str, dict] = {}
    for p in posts:
        key = p["date"] or "onbekend"
        g = groups.setdefault(key, {
            "date": p["date"], "text": p["text"],
            "total_views": 0, "total_engagement": 0, "per_platform": {},
        })
        if len(p["text"]) > len(g["text"]):
            g["text"] = p["text"]
        g["total_views"] += p["views"]
        g["total_engagement"] += p["engagement"]
        g["per_platform"][p["platform"]] = {"views": p["views"], "engagement": p["engagement"], "url": p["url"]}
    out = list(groups.values())
    out.sort(key=lambda g: (g["total_views"], g["total_engagement"]), reverse=True)
    return out[:10]


def patterns(section: dict) -> list[str]:
    """Beslissingswaardige inzichten uit de social-sectie."""
    out: list[str] = []
    if not section.get("connected"):
        return out
    pp = section.get("per_platform") or []
    if pp and pp[0]["views"]:
        out.append(f"📱 Beste social-platform deze week: {pp[0]['platform']} "
                   f"({pp[0]['views']} views over {pp[0]['posts_count']} posts).")
    bc = section.get("by_content") or []
    if bc and bc[0]["total_views"]:
        best = bc[0]
        title = (best["text"][:70] + "…") if len(best["text"]) > 70 else best["text"]
        plats = "/".join(best["per_platform"].keys())
        out.append(f"🏆 Best presterende post ({best['date']}, {plats}): "
                   f"{best['total_views']} views totaal — “{title}”")
    tp = section.get("top_posts") or []
    engaging = [p for p in tp if p["engagement_rate"]]
    if engaging:
        b = max(engaging, key=lambda p: p["engagement_rate"])
        out.append(f"💬 Hoogste engagement-ratio: {b['platform']} "
                   f"({b['engagement_rate']}% op {b['views']} views).")
    elif section.get("total_posts") == 0:
        out.append("📱 Nog geen social-posts met bereik deze week — blijf posten, "
                   "de data bouwt zich op naarmate je account groeit.")
    return out
