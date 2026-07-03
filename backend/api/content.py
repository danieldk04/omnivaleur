"""
Server-side rendered programmatic SEO/GEO pages. All content and metadata
must be in the initial HTML — no client-side rendering — so these routes
render Jinja2 templates directly from `content_pages`, no JS involved.
"""
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
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
SITE_URL = "https://crosslisteu.com"


def _get_page(region: str, pillar: str, slug: str) -> dict | None:
    db = get_db()
    intent_key = f"{region}:{pillar}:{slug}"
    result = db.table("content_pages").select("*").eq("intent_key", intent_key).eq("status", "published").execute()
    return result.data[0] if result.data else None


def _hreflang_variants(pillar: str, slug: str) -> list[dict]:
    db = get_db()
    folder = "crosslisten" if pillar == "A" else "reseller-tools"
    rows = db.table("content_pages").select("region").eq("pillar", pillar).eq("slug", slug).eq("status", "published").execute().data or []
    return [{"region": r["region"], "url": f"{SITE_URL}/{r['region']}/{folder}/{slug}"} for r in rows]


def _language_switch(page: dict) -> dict | None:
    """
    Returns the URL of the sibling-language page if one exists, so the
    template can render an EN/NL toggle. Works in both directions: an
    English row finds its Dutch companion via translation_of pointing at it;
    a Dutch row finds its English source directly via its own translation_of.
    """
    db = get_db()
    folder = "crosslisten" if page["pillar"] == "A" else "reseller-tools"

    if page.get("translation_of"):
        source_intent = page["translation_of"]
        source_region, source_pillar, source_slug = source_intent.split(":")
        return {"language": "en", "url": f"/{source_region}/{folder}/{source_slug}"}

    own_intent = f"{page['region']}:{page['pillar']}:{page['slug']}"
    sibling = db.table("content_pages").select("region,pillar,slug,language").eq("translation_of", own_intent).eq("status", "published").execute().data
    if sibling:
        s = sibling[0]
        return {"language": "nl", "url": f"/{s['region']}/{folder}/{s['slug']}"}
    return None


def _render_page(request: Request, region: str, pillar: str, slug: str) -> HTMLResponse:
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail="Unknown region")
    page = _get_page(region, pillar, slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    folder = "crosslisten" if pillar == "A" else "reseller-tools"
    canonical = f"{SITE_URL}/{region}/{folder}/{slug}"

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

    return templates.TemplateResponse(
        request,
        "content_page.html",
        {
            "page": page,
            "canonical": canonical,
            "hreflang_variants": _hreflang_variants(pillar, slug),
            "faq_json_ld": faq_json_ld,
            "software_json_ld": page.get("software_application_json_ld") or {},
            "article_json_ld": page.get("article_json_ld") or {},
            "language_switch": _language_switch(page),
        },
    )


@router.get("/{region}/crosslisten/{slug}", response_class=HTMLResponse)
async def combo_page(request: Request, region: str, slug: str):
    return _render_page(request, region, "A", slug)


@router.get("/{region}/reseller-tools/{slug}", response_class=HTMLResponse)
async def niche_page(request: Request, region: str, slug: str):
    return _render_page(request, region, "B", slug)


def _reading_minutes(body_html: str) -> int:
    import re as _re

    words = len(_re.findall(r"\S+", _re.sub(r"<[^>]+>", " ", body_html or "")))
    return max(1, round(words / 200))


def _render_blog_index(request: Request, region: str | None, canonical: str) -> HTMLResponse:
    db = get_db()
    q = db.table("content_pages").select("*").eq("status", "published").is_("translation_of", "null")
    if region:
        q = q.eq("region", region)
    rows = q.order("published_at", desc=True).execute().data or []
    for r in rows:
        r["url_path"] = f"/{r['region']}/{'crosslisten' if r['pillar'] == 'A' else 'reseller-tools'}/{r['slug']}"
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
        {"pages": rows, "region": region or "nl", "canonical": canonical, "item_list_json_ld": item_list_json_ld},
    )


@router.get("/blog", response_class=HTMLResponse)
async def blog_index_default(request: Request):
    """Region-neutral canonical blog URL — used everywhere in nav/footer."""
    return _render_blog_index(request, None, f"{SITE_URL}/blog")


@router.get("/{region}/blog", response_class=HTMLResponse)
async def blog_index(request: Request, region: str):
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail="Unknown region")
    return _render_blog_index(request, region, f"{SITE_URL}/{region}/blog")


@router.get("/sitemap.xml")
async def content_sitemap():
    db = get_db()
    rows = db.table("content_pages").select("region,pillar,slug,updated_at").eq("status", "published").execute().data or []
    urls = []
    for r in rows:
        folder = "crosslisten" if r["pillar"] == "A" else "reseller-tools"
        urls.append(f"<url><loc>{SITE_URL}/{r['region']}/{folder}/{r['slug']}</loc><lastmod>{r['updated_at']}</lastmod></url>")
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
    if region not in REGIONS or pillar not in {"A", "B"}:
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
