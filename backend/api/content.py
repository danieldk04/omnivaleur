"""
Server-side rendered programmatic SEO/GEO pages. All content and metadata
must be in the initial HTML — no client-side rendering — so these routes
render Jinja2 templates directly from `content_pages`, no JS involved.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.content.pipeline import run_pipeline
from backend.database import get_db

router = APIRouter(tags=["content"])
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
        },
    )


@router.get("/{region}/crosslisten/{slug}", response_class=HTMLResponse)
async def combo_page(request: Request, region: str, slug: str):
    return _render_page(request, region, "A", slug)


@router.get("/{region}/reseller-tools/{slug}", response_class=HTMLResponse)
async def niche_page(request: Request, region: str, slug: str):
    return _render_page(request, region, "B", slug)


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
async def generate_content_page(body: dict):
    """
    Internal trigger for the content pipeline — called by the scheduled
    generation script (scripts/generate_content.py / GitHub Actions cron),
    not exposed to end users.
    """
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
