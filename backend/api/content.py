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


def _render_page(request: Request, language: str, pillar: str, slug: str) -> HTMLResponse:
    page = _get_page(language, pillar, slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    canonical = f"{SITE_URL}{_url_path(language, pillar, slug)}"

    faq_json_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in (page.get("faq") or [])
        ],
    }

    language_switch = _language_switch(page)
    hreflang_variants = [{"region": page.get("language", "en"), "url": canonical}]
    if language_switch:
        hreflang_variants.append({"region": language_switch["language"], "url": f"{SITE_URL}{language_switch['url']}"})

    return templates.TemplateResponse(
        request,
        "content_page.html",
        {
            "page": page,
            "canonical": canonical,
            "hreflang_variants": hreflang_variants,
            "faq_json_ld": faq_json_ld,
            "software_json_ld": page.get("software_application_json_ld") or {},
            "article_json_ld": page.get("article_json_ld") or {},
            "language_switch": language_switch,
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


@router.get("/vs/{slug}", response_class=HTMLResponse)
async def comparison_page_en(request: Request, slug: str):
    return _render_page(request, "en", "C", slug)


@router.get("/{language}/vergelijking/{slug}", response_class=HTMLResponse)
async def comparison_page_lang(request: Request, language: str, slug: str):
    if language not in LANGUAGES:
        raise HTTPException(status_code=404, detail="Unknown language")
    return _render_page(request, language, "C", slug)


def _reading_minutes(body_html: str) -> int:
    import re as _re

    words = len(_re.findall(r"\S+", _re.sub(r"<[^>]+>", " ", body_html or "")))
    return max(1, round(words / 200))


def _render_blog_index(request: Request, canonical: str) -> HTMLResponse:
    # The blog index only ever lists primary (English) articles — a Dutch
    # translation is reachable via the language toggle on its English page,
    # never as its own index card (that would look like duplicate content).
    db = get_db()
    rows = db.table("content_pages").select("*").eq("status", "published").is_("translation_of", "null").order("published_at", desc=True).execute().data or []
    for r in rows:
        r["url_path"] = _url_path(r.get("language", "en"), r["pillar"], r["slug"])
        r["reading_minutes"] = _reading_minutes(r.get("body_html"))

    item_list_json_ld = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": f"{SITE_URL}{r['url_path']}", "name": r["h1"]}
            for i, r in enumerate(rows)
        ],
    }

    return templates.TemplateResponse(
        request,
        "blog_index.html",
        {"pages": rows, "region": "nl", "canonical": canonical, "item_list_json_ld": item_list_json_ld},
    )


@router.get("/blog", response_class=HTMLResponse)
async def blog_index_default(request: Request):
    return _render_blog_index(request, f"{SITE_URL}/blog")


STATIC_SITEMAP_URLS = [
    ("/", "weekly", "1.0"),
    ("/blog", "daily", "0.9"),
    ("/marketplaces", "monthly", "0.8"),
    ("/register", "monthly", "0.9"),
    ("/privacy", "yearly", "0.3"),
    ("/terms", "yearly", "0.3"),
]


@router.get("/sitemap.xml")
async def content_sitemap():
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
async def set_content_image(body: dict, x_admin_secret: str | None = Header(default=None)):
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
    return {"gsc": gsc.diagnostics(), "ga4_configured": ga4.is_configured()}


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
    from backend.services.analytics_report import build_report, render_email
    from backend.services.email import send_email
    report = build_report()
    subject, body = render_email(report)
    sent = send_email(subject, body)
    return {"ok": True, "emailed": sent, "patterns": report["patterns"]}
