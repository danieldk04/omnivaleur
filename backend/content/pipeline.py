"""
Orkestreert de volledige contentpijplijn voor één keyword/pagina:
research → generatie (Engels) → evt. NL-vertaling → interne links → opslaan/updaten.

Cannibalisatie-guard: `intent_key` (region:pillar:slug) is UNIQUE in de
database. Als de intent al bestaat, wordt de bestaande rij overschreven met
de nieuwe concurrentie-inzichten in plaats van een duplicaat aan te maken —
dit is de enige plek waar dat besluit wordt genomen.
"""
import logging
import re
from datetime import datetime, timezone

from backend.content.generator import generate_page_content, needs_dutch_translation, translate_to_dutch, inject_comparison_screenshots
from backend.content.linking import apply_internal_links
from backend.content.research import research_competitors
from backend.content.schema_validate import validate_page
from backend.database import get_db
from backend.services.email import notify_published
from backend.services.indexnow import submit_url
from backend.services.search_console import get_top_pages

logger = logging.getLogger(__name__)

SITE_URL = "https://crosslisteu.com"

# Altijd-beschikbare interne linkkandidaten, ook als er nog geen andere
# content_pages bestaan — zo heeft zelfs de allereerste pagina al zinvolle
# interne links in plaats van een orphan page.
STATIC_LINK_CANDIDATES = [
    {"intent_key": "static:home", "title": "CrossList EU", "url_path": "/", "link_terms": ["CrossList EU"]},
    {"intent_key": "static:register", "title": "Start gratis", "url_path": "/register", "link_terms": ["crosslist-tool", "cross-listing tool"]},
    {"intent_key": "static:marketplaces", "title": "Ondersteunde platforms", "url_path": "/marketplaces", "link_terms": ["Marktplaats", "Vinted", "eBay", "Etsy", "Shopify"]},
]


def _url_path(language: str, pillar: str, slug: str) -> str:
    """
    English (the default) gets no URL prefix at all — /crosslisting/{slug}.
    Only a translated page gets its language as a prefix, with the folder
    name in that language too — /nl/crosslisten/{slug}.
    Translated slugs carry an internal "-{language}" DB-only suffix (to stay
    unique from the English row, since they're independently-worded Dutch
    slugs, not just the English slug with a suffix); that suffix is stripped
    for the public URL.
    """
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


def _link_terms_for(page: dict) -> list[str]:
    # Simpele, robuuste ankerwoord-set: de pagina-titel zelf plus de eerste
    # 2-3 woorden van het primaire keyword (platform/niche-namen zitten daar altijd in).
    words = re.findall(r"[A-Za-zÀ-ÿ]+", page.get("primary_keyword", ""))
    return [page["title"]] + words[:3]


def _software_json_ld() -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "CrossList EU",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "description": "Automatically cross-list and sync listings across Marktplaats, 2dehands, Vinted, eBay, Etsy and Shopify, including background inventory sync.",
        "offers": {"@type": "Offer", "priceCurrency": "EUR"},
        "featureList": [
            "Automatic cross-listing to multiple platforms",
            "Background sync of sold items",
            "Bulk import of existing listings",
        ],
    }


def _save_page_row(
    db,
    *,
    region: str,
    pillar: str,
    slug: str,
    keyword: str,
    language: str,
    translation_of: str | None,
    generated: dict,
    research: dict | None,
) -> dict:
    """Shared save logic for both the primary (English) row and its Dutch translation."""
    intent_key = f"{region}:{pillar}:{slug}"

    existing = db.table("content_pages").select("*").eq("status", "published").neq("intent_key", intent_key).limit(50).execute().data or []
    candidates = [
        {
            "intent_key": f'{p["region"]}:{p["pillar"]}:{p["slug"]}',
            "title": p["title"],
            "url_path": _url_path(p.get("language", "en"), p["pillar"], p["slug"]),
            "link_terms": _link_terms_for(p),
        }
        for p in existing
    ]
    # Prioritize linking to pages that already get real Search Console traffic —
    # falls back to the existing (unordered) sequence if GSC isn't configured.
    clicks_by_url = {p["url"]: p["clicks"] for p in get_top_pages(days=90, row_limit=200)}
    candidates.sort(key=lambda c: clicks_by_url.get(f"https://crosslisteu.com{c['url_path']}", 0), reverse=True)
    candidates += STATIC_LINK_CANDIDATES
    body_with_links, linked_intents = apply_internal_links(generated["body_html"], candidates, intent_key)

    existing_row = db.table("content_pages").select("id,featured_image_url").eq("intent_key", intent_key).execute().data
    featured_image_url = existing_row[0].get("featured_image_url") if existing_row else None

    now_iso = datetime.now(timezone.utc).isoformat()
    canonical = f"{SITE_URL}{_url_path(language, pillar, slug)}"
    article_json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": generated["h1"],
        "description": generated["meta_description"],
        "image": featured_image_url or f"{SITE_URL}/Logo Crosslist EU.png",
        "author": {"@type": "Person", "name": "Daniel"},
        "publisher": {"@type": "Organization", "name": "CrossList EU", "url": SITE_URL},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "inLanguage": language,
        "datePublished": now_iso,
        "dateModified": now_iso,
    }

    row = {
        "pillar": pillar,
        "region": region,
        "slug": slug,
        "language": language,
        "translation_of": translation_of,
        "primary_keyword": keyword,
        "title": generated["title"],
        "meta_description": generated["meta_description"],
        "h1": generated["h1"],
        "quick_answer": generated["quick_answer"],
        "takeaways": generated.get("takeaways") or [],
        "body_html": body_with_links,
        "faq": generated["faq"],
        "featured_image_url": featured_image_url,
        "software_application_json_ld": _software_json_ld(),
        "article_json_ld": article_json_ld,
        "related_slugs": linked_intents,
        "status": "published",
    }
    if research is not None:
        row["competitor_research"] = research

    if existing_row:
        db.table("content_pages").update(row).eq("id", existing_row[0]["id"]).execute()
        logger.info(f"Bestaande pagina bijgewerkt (cannibalisatie voorkomen): {intent_key}")
        action = "updated"
    else:
        row["published_at"] = now_iso
        db.table("content_pages").insert(row).execute()
        logger.info(f"Nieuwe pagina aangemaakt: {intent_key}")
        action = "created"

    url_path = _url_path(language, pillar, slug)
    submit_url(url_path)

    return {"success": True, "action": action, "url_path": url_path, "linked": linked_intents, "intent_key": intent_key}


async def run_pipeline(keyword: str, region: str, pillar: str, slug: str, nl_slug: str | None = None) -> dict:
    db = get_db()

    logger.info(f"Research voor '{keyword}' ({region})")
    research = research_competitors(keyword, region)

    logger.info(f"Content genereren (Engels) voor '{keyword}'")
    existing_for_prompt_rows = db.table("content_pages").select("title,language,pillar,slug").eq("status", "published").limit(50).execute().data or []
    existing_for_prompt = [{"title": p["title"], "url_path": _url_path(p.get("language", "en"), p["pillar"], p["slug"])} for p in existing_for_prompt_rows]

    generated = generate_page_content(keyword, region, pillar, slug, research, existing_for_prompt)
    if not generated:
        return {"success": False, "error": "content generation failed"}

    schema_warnings = validate_page(generated)

    result = _save_page_row(
        db, region=region, pillar=pillar, slug=slug, keyword=keyword,
        language="en", translation_of=None, generated=generated, research=research,
    )

    if needs_dutch_translation(keyword, region):
        logger.info(f"NL-vertaling genereren voor '{keyword}'")
        translated = translate_to_dutch(generated)
        if translated:
            db_nl_slug = f"{nl_slug or slug}-nl"
            nl_result = _save_page_row(
                db, region=region, pillar=pillar, slug=db_nl_slug, keyword=keyword,
                language="nl", translation_of=result["intent_key"], generated=translated, research=None,
            )
            # No reverse pointer needed on the English row — content.py looks up the
            # NL companion by querying translation_of = <this row's intent_key>.
            result["nl_translation"] = nl_result["url_path"]
        else:
            logger.warning(f"NL-vertaling mislukt voor '{keyword}' — Engelse pagina blijft zonder companion")

    try:
        notify_published(keyword, result["url_path"], result["action"], schema_warnings)
    except Exception as e:
        logger.error(f"Publicatie-melding mislukt (niet-blokkerend): {e}")

    return result
