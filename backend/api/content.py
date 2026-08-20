"""
Server-side rendered programmatic SEO/GEO pages. All content and metadata
must be in the initial HTML — no client-side rendering — so these routes
render Jinja2 templates directly from `content_pages`, no JS involved.

URL scheme is LANGUAGE-based, not region-based: English (the default) has no
prefix (/crosslisten/{slug}), only a genuine translation gets a language
prefix (/nl/crosslisten/{slug}). See backend/content/pipeline.py's
`_url_path()` for the canonical implementation this mirrors.
"""
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.config import settings
from backend.content.pipeline import run_pipeline
from backend.database import get_db

router = APIRouter(tags=["content"])


def _require_admin(x_admin_secret: str | None) -> None:
    """
    These two endpoints publish/modify live site content, so they must not be
    left wide open — anyone who found the URL could otherwise overwrite a
    published page. Uses the existing SECRET_KEY env var as a shared secret,
    passed as the X-Admin-Secret header.
    """
    if not settings.secret_key or settings.secret_key == "change-me" or x_admin_secret != settings.secret_key:
        raise HTTPException(status_code=401, detail="unauthorized")


templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "frontend" / "templates"))

import re as _re

_HTML_TAG_RE = _re.compile(r"<[^>]+>")
# A bare URL NOT already part of an attribute (href="…") or an anchor's text
# (>…<). Anything preceded by " ' > or = is inside markup already.
_BARE_URL_RE = _re.compile(r'(?<![\"\'>=])(https?://[^\s<>"\']+)')


def _answer_plain(text: str) -> str:
    """Plain-text form of an FAQ answer, for JSON-LD structured data — no tags."""
    return _HTML_TAG_RE.sub("", text or "").strip()


def _answer_html(text: str) -> str:
    """FAQ answers may carry authority-source links from the generator. These
    must render as real anchors, never as escaped raw ``<a href…>`` tags shown
    to the reader. Existing ``<a>`` tags are kept as-is; a bare URL the model
    emitted without an anchor is wrapped so a raw URL is never printed either.

    Rendered with ``| safe`` in the template — the same trust level as
    ``body_html`` (both come from our own admin-gated generator, not visitors)."""
    return _BARE_URL_RE.sub(r'<a href="\1">\1</a>', text or "")


REGIONS = {"nl", "be-nl", "be-fr", "fr", "de"}
LANGUAGES = {"nl", "fr", "de"}  # non-English language prefixes this site currently serves
SITE_URL = "https://omnivaleur.com"


def _url_path(language: str, pillar: str, slug: str) -> str:
    if pillar == "A":
        folder = "crosslisten" if language and language != "en" else "crosslisting"
    elif pillar == "C":
        folder = "vergelijking" if language and language != "en" else "vs"
    else:
        folder = "reseller-tools"
    if language and language != "en":
        suffix = f"-{language}"
        public_slug = slug[: -len(suffix)] if slug.endswith(suffix) else slug
        return f"/{language}/{folder}/{public_slug}"
    return f"/{folder}/{slug}"


def _get_page(language: str, pillar: str, slug: str) -> dict | None:
    db = get_db()
    db_slug = slug if language == "en" else f"{slug}-{language}"
    result = (
        db.table("content_pages")
        .select("*")
        .eq("pillar", pillar)
        .eq("slug", db_slug)
        .eq("language", language)
        .eq("status", "published")
        .execute()
    )
    return result.data[0] if result.data else None


def _language_switch(page: dict) -> dict | None:
    """
    Returns the URL of the sibling-language page if one exists, so the
    template can render an EN/NL toggle. Works in both directions: an
    English row finds its Dutch companion via translation_of pointing at it;
    a translated row finds its English source directly via its own translation_of.
    """
    db = get_db()

    if page.get("translation_of"):
        source_region, source_pillar, source_slug = page["translation_of"].split(":")
        return {"language": "en", "url": _url_path("en", source_pillar, source_slug)}

    own_intent = f"{page['region']}:{page['pillar']}:{page['slug']}"
    sibling = db.table("content_pages").select("pillar,slug,language").eq("translation_of", own_intent).eq("status", "published").execute().data
    if sibling:
        s = sibling[0]
        return {"language": s["language"], "url": _url_path(s["language"], s["pillar"], s["slug"])}
    return None


def _table_of_contents(body_html: str) -> list[dict]:
    """
    Bouwt een inhoudsopgave uit de H2's, en geeft de body terug met id's erop.
    Twee redenen: lezers kunnen springen naar wat ze zoeken (scheelt bounces op
    artikelen van 2000 woorden), en Google gebruikt zulke ankers voor sitelinks
    onder het zoekresultaat.
    """
    items = []
    for match in _re.finditer(r"<h2[^>]*>(.*?)</h2>", body_html or "", _re.S | _re.I):
        text = _HTML_TAG_RE.sub("", match.group(1)).strip()
        if not text:
            continue
        anchor = _re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
        if anchor and anchor not in {i["anchor"] for i in items}:
            items.append({"anchor": anchor, "text": text})
    return items


def _body_with_anchors(body_html: str, toc: list[dict]) -> str:
    """Zet id="…" op de H2's die in de inhoudsopgave staan, in dezelfde volgorde.
    Bewust string-splicing i.p.v. een HTML-parser — herserialiseren van de body
    heeft in dit project al eens img-src'en beschadigd."""
    if not toc:
        return body_html

    result, cursor, index = [], 0, 0
    for match in _re.finditer(r"<h2([^>]*)>(.*?)</h2>", body_html, _re.S | _re.I):
        if index >= len(toc):
            break
        text = _HTML_TAG_RE.sub("", match.group(2)).strip()
        if text != toc[index]["text"]:
            continue
        attrs = match.group(1)
        if "id=" in attrs:
            index += 1
            continue
        result.append(body_html[cursor:match.start()])
        result.append(f'<h2 id="{toc[index]["anchor"]}"{attrs}>{match.group(2)}</h2>')
        cursor = match.end()
        index += 1
    result.append(body_html[cursor:])
    return "".join(result)


def _related_pages(page: dict, limit: int = 3) -> list[dict]:
    """
    Drie verwante artikelen voor onderaan de pagina. Eerst uit dezelfde pillar
    (die gaan over hetzelfde type vraag), aangevuld met andere. Zonder zo'n blok
    hing elk artikel aan alleen zijn inline links, en dat is te dun om pagina's
    elkaar te laten versterken.
    """
    db = get_db()
    language = page.get("language", "en")
    rows = (
        db.table("content_pages")
        .select("pillar,slug,title,h1,language,primary_keyword,featured_image_url")
        .eq("status", "published")
        .eq("language", language)
        .neq("slug", page["slug"])
        .limit(60)
        .execute()
        .data
        or []
    )
    same_pillar = [r for r in rows if r["pillar"] == page["pillar"]]
    other = [r for r in rows if r["pillar"] != page["pillar"]]
    picked = (same_pillar + other)[:limit]
    for r in picked:
        r["url_path"] = _url_path(r.get("language", "en"), r["pillar"], r["slug"])
    return picked


def _render_page(request: Request, language: str, pillar: str, slug: str) -> HTMLResponse:
    page = _get_page(language, pillar, slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    canonical = f"{SITE_URL}{_url_path(language, pillar, slug)}"

    toc = _table_of_contents(page.get("body_html"))
    page["body_html"] = _body_with_anchors(page.get("body_html") or "", toc)

    # Pre-render FAQ answers so embedded/authority links show as real anchors
    # instead of escaped raw tags, and keep a tag-free version for JSON-LD.
    for item in (page.get("faq") or []):
        item["answer_html"] = _answer_html(item.get("answer", ""))

    faq_json_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": _answer_plain(item["answer"])},
            }
            for item in (page.get("faq") or [])
        ],
    }

    language_switch = _language_switch(page)
    hreflang_variants = [{"region": page.get("language", "en"), "url": canonical}]
    if language_switch:
        hreflang_variants.append({"region": language_switch["language"], "url": f"{SITE_URL}{language_switch['url']}"})

    # x-default hoort naar de ENGELSE versie te wijzen, altijd. Voorheen zette
    # elke taalversie zichzelf als x-default, dus de NL- en de EN-pagina claimden
    # allebei de standaardversie te zijn — een tegenstrijdig signaal waar Google
    # er willekeurig één van kiest.
    if page.get("translation_of") and language_switch:
        x_default = f"{SITE_URL}{language_switch['url']}"
    else:
        x_default = canonical

    # Het kruimelpad hoort naar de index in dezelfde taal te wijzen: een
    # Nederlands artikel dat "Blog" naar de Engelse index laat wijzen stuurt de
    # lezer (en Google) de verkeerde taal in.
    blog_index_path = BLOG_INDEX_PATHS.get(page.get("language", "en"), "/blog")

    breadcrumb_json_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{SITE_URL}{blog_index_path}"},
            {"@type": "ListItem", "position": 3, "name": page["h1"], "item": canonical},
        ],
    }

    article_json_ld = page.get("article_json_ld") or {}
    og_image = page.get("featured_image_url") or article_json_ld.get("image") or f"{SITE_URL}/logo.png"

    return templates.TemplateResponse(
        request,
        "content_page.html",
        {
            "page": page,
            "canonical": canonical,
            "blog_index_path": blog_index_path,
            "hreflang_variants": hreflang_variants,
            "x_default": x_default,
            "faq_json_ld": faq_json_ld,
            "software_json_ld": page.get("software_application_json_ld") or {},
            "article_json_ld": article_json_ld,
            "breadcrumb_json_ld": breadcrumb_json_ld,
            "language_switch": language_switch,
            "toc": toc,
            "related_pages": _related_pages(page),
            "og_image": og_image,
            "published_at": (article_json_ld.get("datePublished") or page.get("published_at") or "")[:10],
            "modified_at": (article_json_ld.get("dateModified") or page.get("updated_at") or "")[:10],
        },
    )


@router.get("/crosslisting/{slug}", response_class=HTMLResponse)
async def combo_page_en(request: Request, slug: str):
    return _render_page(request, "en", "A", slug)


@router.get("/reseller-tools/{slug}", response_class=HTMLResponse)
async def niche_page_en(request: Request, slug: str):
    return _render_page(request, "en", "B", slug)


@router.get("/{language}/crosslisten/{slug}", response_class=HTMLResponse)
async def combo_page_lang(request: Request, language: str, slug: str):
    if language not in LANGUAGES:
        raise HTTPException(status_code=404, detail="Unknown language")
    return _render_page(request, language, "A", slug)


@router.get("/{language}/reseller-tools/{slug}", response_class=HTMLResponse)
async def niche_page_lang(request: Request, language: str, slug: str):
    if language not in LANGUAGES:
        raise HTTPException(status_code=404, detail="Unknown language")
    return _render_page(request, language, "B", slug)


# 301 redirects for comparison slugs that were renamed during the Omnivaleur
# rebrand (old public slug -> new public slug). Keeps indexed URLs and external
# links alive after the brand name left the slug.
_COMPARISON_SLUG_REDIRECTS = {
    "crosslisteu-vs-vendoo": "omnivaleur-vs-vendoo",
    "crosslisteu-vs-list-perfectly": "omnivaleur-vs-list-perfectly",
    # Kannibalisatie opgeruimd: de keyword-planner stelde "Omnivaleur vs List
    # Perfectly comparison 2026" voor terwijl "crosslist eu vs list perfectly" al
    # gepubliceerd was. Twee pagina's om exact dezelfde zoekopdracht laten
    # vechten kost ze allebei posities. De oudste, schoonste URL blijft; de
    # jongere duplicaat wijst er permanent naartoe.
    "omnivaleur-vs-list-perfectly-comparison-2026": "omnivaleur-vs-list-perfectly",
}


@router.get("/vs/{slug}", response_class=HTMLResponse)
async def comparison_page_en(request: Request, slug: str):
    new_slug = _COMPARISON_SLUG_REDIRECTS.get(slug)
    if new_slug:
        return RedirectResponse(url=f"/vs/{new_slug}", status_code=301)
    return _render_page(request, "en", "C", slug)


@router.get("/{language}/vergelijking/{slug}", response_class=HTMLResponse)
async def comparison_page_lang(request: Request, language: str, slug: str):
    if language not in LANGUAGES:
        raise HTTPException(status_code=404, detail="Unknown language")
    new_slug = _COMPARISON_SLUG_REDIRECTS.get(slug)
    if new_slug:
        return RedirectResponse(url=f"/{language}/vergelijking/{new_slug}", status_code=301)
    return _render_page(request, language, "C", slug)


def word_count(body_html: str) -> int:
    return len(_re.findall(r"\S+", _re.sub(r"<[^>]+>", " ", body_html or "")))


def _reading_minutes(words: int) -> int:
    return max(1, round((words or 0) / 200))


BLOG_INDEX_COPY = {
    "en": {
        "title": "Blog — Omnivaleur",
        "meta": "Guides on cross-listing across Marktplaats, 2dehands, Vinted, eBay, Etsy and Shopify.",
        "h1": "Cross-listing guides",
        "subtitle": "Platform comparisons, DAC7 rules and reselling tips — updated for 2026.",
        "filters": {"all": "All guides", "A": "Platform comparisons", "B": "Reseller guides", "C": "Vs. competitors"},
        "read": "Read article",
        "read_time": "min read",
        "empty": "No guides published yet.",
        "no_match": "No guides in this category yet.",
        "switch": "Lees deze gidsen in het Nederlands",
    },
    "nl": {
        "title": "Blog — Omnivaleur",
        "meta": "Gidsen over crosslisten naar Marktplaats, 2dehands, Vinted, eBay, Etsy en Shopify.",
        "h1": "Crosslist-gidsen",
        "subtitle": "Platformvergelijkingen, DAC7-regels en verkooptips — bijgewerkt voor 2026.",
        "filters": {"all": "Alle gidsen", "A": "Platformvergelijkingen", "B": "Verkopersgidsen", "C": "Vs. concurrenten"},
        "read": "Lees het artikel",
        "read_time": "min lezen",
        "empty": "Nog geen gidsen gepubliceerd.",
        "no_match": "Nog geen gidsen in deze categorie.",
        "switch": "Read these guides in English",
    },
}

# Elke taal heeft zijn eigen indexpagina. Zonder de Nederlandse index stonden de
# 40+ vertaalde artikelen wel in de sitemap, maar linkte geen enkele pagina op de
# site ernaartoe — verweesde pagina's, die Google structureel lager zet.
BLOG_INDEX_PATHS = {"en": "/blog", "nl": "/nl/blog"}


def _render_blog_index(request: Request, language: str = "en") -> HTMLResponse:
    db = get_db()
    # Bewust GEEN select("*"): dat haalde van elke pagina de volledige body_html
    # op — 0,57 MB per bezoek aan deze pagina, terwijl er alleen een titel, datum
    # en samenvatting van getoond wordt. Het aantal woorden (voor de leestijd)
    # staat in article_json_ld als `wordCount`, dat is een paar honderd bytes.
    query = (
        db.table("content_pages")
        .select("pillar,slug,language,title,h1,meta_description,published_at,featured_image_url,article_json_ld")
        .eq("status", "published")
        .eq("language", language)
    )
    if language == "en":
        # Engelse rijen zijn altijd de bron, nooit een vertaling.
        query = query.is_("translation_of", "null")
    rows = query.order("published_at", desc=True).execute().data or []

    for r in rows:
        r["url_path"] = _url_path(r.get("language", "en"), r["pillar"], r["slug"])
        r["reading_minutes"] = _reading_minutes((r.get("article_json_ld") or {}).get("wordCount"))

    canonical = f"{SITE_URL}{BLOG_INDEX_PATHS[language]}"
    item_list_json_ld = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": f"{SITE_URL}{r['url_path']}", "name": r["h1"]}
            for i, r in enumerate(rows)
        ],
    }
    hreflang_variants = [{"region": lang, "url": f"{SITE_URL}{path}"} for lang, path in BLOG_INDEX_PATHS.items()]
    other = "nl" if language == "en" else "en"

    return templates.TemplateResponse(
        request,
        "blog_index.html",
        {
            "pages": rows,
            "region": language,
            "blog_index_path": BLOG_INDEX_PATHS[language],
            "language": language,
            "canonical": canonical,
            "hreflang_variants": hreflang_variants,
            # x-default wijst altijd naar de Engelse index, net als bij de artikelen.
            "x_default": f"{SITE_URL}{BLOG_INDEX_PATHS['en']}",
            "language_switch": {"language": other, "url": BLOG_INDEX_PATHS[other]},
            "copy": BLOG_INDEX_COPY[language],
            "item_list_json_ld": item_list_json_ld,
        },
    )


@router.get("/blog", response_class=HTMLResponse)
async def blog_index_default(request: Request):
    return _render_blog_index(request, "en")


@router.get("/{language}/blog", response_class=HTMLResponse)
async def blog_index_lang(request: Request, language: str):
    if language not in BLOG_INDEX_PATHS or language == "en":
        raise HTTPException(status_code=404, detail="Page not found")
    return _render_blog_index(request, language)


STATIC_SITEMAP_URLS = [
    ("/", "weekly", "1.0"),
    ("/blog", "daily", "0.9"),
    ("/nl/blog", "daily", "0.8"),
    ("/marketplaces", "monthly", "0.8"),
    ("/register", "monthly", "0.9"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
]


@router.get("/sitemap.xml")
def content_sitemap():
    db = get_db()
    rows = db.table("content_pages").select("language,pillar,slug,updated_at").eq("status", "published").execute().data or []
    urls = [
        f"<url><loc>{SITE_URL}{path}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for path, freq, prio in STATIC_SITEMAP_URLS
    ]
    for r in rows:
        loc = f"{SITE_URL}{_url_path(r.get('language', 'en'), r['pillar'], r['slug'])}"
        urls.append(f"<url><loc>{loc}</loc><lastmod>{r['updated_at']}</lastmod></url>")
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{"".join(urls)}</urlset>'
    return HTMLResponse(content=xml, media_type="application/xml")


@router.post("/api/content/generate")
async def generate_content_page(body: dict, x_admin_secret: str | None = Header(default=None)):
    """
    Internal trigger for the content pipeline — called by the scheduled
    generation script (scripts/generate_content.py / GitHub Actions cron),
    not exposed to end users.
    """
    _require_admin(x_admin_secret)
    keyword = body.get("keyword")
    region = body.get("region")
    pillar = body.get("pillar")
    slug = body.get("slug")
    if not all([keyword, region, pillar, slug]):
        raise HTTPException(status_code=400, detail="keyword, region, pillar and slug are required")
    if region not in REGIONS or pillar not in {"A", "B", "C"}:
        raise HTTPException(status_code=400, detail="invalid region or pillar")

    result = await run_pipeline(keyword, region, pillar, slug)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "generation failed"))
    return result


@router.post("/api/content/set-image")
def set_content_image(body: dict, x_admin_secret: str | None = Header(default=None)):
    """
    Attaches a manually-designed featured image to an existing page — the
    pipeline no longer generates images itself (see pipeline.py docstring).
    """
    _require_admin(x_admin_secret)
    region = body.get("region")
    pillar = body.get("pillar")
    slug = body.get("slug")
    image_url = body.get("image_url")
    if not all([region, pillar, slug, image_url]):
        raise HTTPException(status_code=400, detail="region, pillar, slug and image_url are required")

    db = get_db()
    intent_key = f"{region}:{pillar}:{slug}"
    existing = db.table("content_pages").select("id").eq("intent_key", intent_key).execute().data
    if not existing:
        raise HTTPException(status_code=404, detail="page not found")

    db.table("content_pages").update({"featured_image_url": image_url}).eq("id", existing[0]["id"]).execute()
    return {"success": True, "intent_key": intent_key, "image_url": image_url}


# ---------------------------------------------------------------------------
# Wekelijks marketing-dashboard
# ---------------------------------------------------------------------------
def _require_dashboard_token(token: str | None) -> None:
    """Beschermt het dashboard + de handmatige rapport-trigger met een los token
    (?token=...), zodat de URL niet publiek te openen is. Leeg token = uit."""
    if not settings.analytics_dashboard_token or token != settings.analytics_dashboard_token:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, token: str | None = None):
    _require_dashboard_token(token)
    from backend.services.analytics_report import build_report
    report = build_report()
    return templates.TemplateResponse(
        "analytics_dashboard.html",
        {"request": request, "report": report, "token": token, "site_url": SITE_URL},
    )


@router.get("/api/analytics/diag")
async def analytics_diagnostics(token: str | None = None):
    """Definitieve koppelingscheck (auth vs geen-data) voor GSC + GA4."""
    _require_dashboard_token(token)
    from backend.services import search_console as gsc
    from backend.services import ga4
    from datetime import date, timedelta
    dag = lambda n: (date.today() - timedelta(days=n)).isoformat()

    # Niet alleen "is hij gekoppeld", maar ook "wat komt er dan uit". Een lege
    # grafiek op het beheerscherm kan twee dingen betekenen — geen verkeer, of
    # een geweigerde metriek — en dat verschil was van buitenaf niet te zien.
    ga4_uit: dict = {"configured": ga4.is_configured()}
    if ga4.is_configured():
        ga4_uit["property"] = settings.ga4_property_id
        try:
            ga4_uit["totals_7d"] = ga4.totals(dag(7), dag(1))
            ga4_uit["sessies_zonder_conversies"] = ga4._run(
                dimensions=[], metrics=["sessions"], start=dag(7), end=dag(1), limit=1)
            ga4_uit["dagen"] = len(ga4.sessions_by_day(dag(29), dag(0)))
            # Rechtstreeks, zonder de zachte val van _run: die vangt elke fout af
            # en geeft een lege lijst terug, waardoor "geen toegang" er precies
            # zo uitziet als "geen bezoekers".
            try:
                from google.analytics.data_v1beta.types import (
                    DateRange, Metric, RunReportRequest,
                )
                client = ga4._get_client()
                if client is None:
                    ga4_uit["rauw"] = "client kon niet worden opgebouwd"
                else:
                    antwoord = client.run_report(RunReportRequest(
                        property=f"properties/{settings.ga4_property_id}",
                        metrics=[Metric(name="sessions")],
                        date_ranges=[DateRange(start_date=dag(7), end_date=dag(1))],
                    ))
                    ga4_uit["rauw"] = [r.metric_values[0].value for r in antwoord.rows] or "geen rijen"
                    # Nul sessies kan twee dingen zijn: een stille website, of
                    # de verkeerde property. Een ruim venster maakt dat verschil
                    # zichtbaar zonder te hoeven gokken.
                    lang = client.run_report(RunReportRequest(
                        property=f"properties/{settings.ga4_property_id}",
                        metrics=[Metric(name="sessions")],
                        date_ranges=[DateRange(start_date=dag(365), end_date=dag(0))],
                    ))
                    ga4_uit["sessies_365d"] = (
                        int(lang.rows[0].metric_values[0].value) if lang.rows else 0)
            except Exception as e:  # noqa: BLE001
                ga4_uit["rauw"] = f"{type(e).__name__}: {e}"[:400]
            # Welke properties horen er eigenlijk bij deze koppeling? Via de kale
            # REST-API, zodat hier geen extra pakket voor nodig is.
            try:
                import httpx as _httpx
                cid, csec = ga4._oauth_client()
                bewijs = _httpx.post("https://oauth2.googleapis.com/token", data={
                    "client_id": cid, "client_secret": csec,
                    "refresh_token": settings.ga4_refresh_token,
                    "grant_type": "refresh_token"}, timeout=20).json()
                sleutel = bewijs.get("access_token")
                if not sleutel:
                    ga4_uit["properties"] = f"geen toegangstoken: {bewijs}"
                else:
                    r = _httpx.get(
                        "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                        headers={"Authorization": f"Bearer {sleutel}"}, timeout=20)
                    if r.status_code >= 300:
                        ga4_uit["properties"] = f"fout {r.status_code}: {r.text[:200]}"
                    else:
                        ga4_uit["properties"] = [
                            {"property": p.get("property"), "titel": p.get("displayName")}
                            for a in (r.json().get("accountSummaries") or [])
                            for p in (a.get("propertySummaries") or [])][:20]
            except Exception as e:  # noqa: BLE001
                ga4_uit["properties"] = f"{type(e).__name__}: {e}"[:300]
        except Exception as e:  # noqa: BLE001
            ga4_uit["fout"] = f"{type(e).__name__}: {e}"

    gsc_uit = gsc.diagnostics()
    try:
        for naam, (a, b) in {"laatste_7": (dag(10), dag(3)),
                             "laatste_30": (dag(33), dag(3))}.items():
            rijen = gsc.query_window(["query"], a, b, row_limit=500)
            gsc_uit[naam] = {
                "venster": [a, b],
                "klikken": sum(r.get("clicks", 0) for r in rijen),
                "vertoningen": sum(r.get("impressions", 0) for r in rijen),
                "termen": len(rijen),
            }
    except Exception as e:  # noqa: BLE001
        gsc_uit["venster_fout"] = f"{type(e).__name__}: {e}"

    return {"gsc": gsc_uit, "ga4": ga4_uit, "ga4_configured": ga4.is_configured()}


@router.get("/api/analytics/social")
async def analytics_social(token: str | None = None):
    """On-demand social-scrape (traag: ~10-30s). Los endpoint zodat de dashboard-pagina
    zelf snel blijft — de social-tabel wordt via een knop async geladen."""
    _require_dashboard_token(token)
    from backend.services import social_scrape
    from backend.services.analytics_report import _windows
    if not social_scrape.is_configured():
        return {"connected": False}
    win = _windows()
    section = social_scrape.weekly(*win["this"])
    section["insights"] = social_scrape.patterns(section)
    return section


@router.post("/api/analytics/send-report")
async def analytics_send_report_now(token: str | None = None):
    """Handmatig het wekelijkse rapport nu opbouwen + mailen (om te testen)."""
    _require_dashboard_token(token)
    from backend.services.analytics_report import build_report
    from backend.services.analytics_email import render
    from backend.services.email import send_email
    # Mét social: anders test je een andere mail dan er zondag verstuurd wordt.
    report = build_report(include_social=True)
    subject, body, html = render(report)
    sent = send_email(subject, body, html=html)
    return {"ok": True, "emailed": sent, "actions": report["actions"]}
