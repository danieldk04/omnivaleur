"""
Orkestreert de volledige contentpijplijn voor één keyword/pagina:
research → generatie → featured image → interne links → opslaan/updaten.

Cannibalisatie-guard: `intent_key` (region:pillar:slug) is UNIQUE in de
database. Als de intent al bestaat, wordt de bestaande rij overschreven met
de nieuwe concurrentie-inzichten in plaats van een duplicaat aan te maken —
dit is de enige plek waar dat besluit wordt genomen.
"""
import logging
import re

from backend.content.generator import generate_page_content
from backend.content.linking import apply_internal_links
from backend.content.research import research_competitors
from backend.database import get_db

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


def _url_path(region: str, pillar: str, slug: str) -> str:
    folder = "crosslisten" if pillar == "A" else "reseller-tools"
    return f"/{region}/{folder}/{slug}"


def _link_terms_for(page: dict) -> list[str]:
    # Simpele, robuuste ankerwoord-set: de pagina-titel zelf plus de eerste
    # 2-3 woorden van het primaire keyword (platform/niche-namen zitten daar altijd in).
    words = re.findall(r"[A-Za-zÀ-ÿ]+", page.get("primary_keyword", ""))
    return [page["title"]] + words[:3]


async def run_pipeline(keyword: str, region: str, pillar: str, slug: str) -> dict:
    db = get_db()
    intent_key = f"{region}:{pillar}:{slug}"

    existing = db.table("content_pages").select("*").eq("status", "published").neq("intent_key", intent_key).limit(50).execute().data or []
    existing_for_prompt = [
        {"title": p["title"], "url_path": _url_path(p["region"], p["pillar"], p["slug"])}
        for p in existing
    ]

    logger.info(f"Research voor '{keyword}' ({region})")
    research = research_competitors(keyword, region)

    logger.info(f"Content genereren voor '{keyword}'")
    generated = generate_page_content(keyword, region, pillar, slug, research, existing_for_prompt)
    if not generated:
        return {"success": False, "error": "content generation failed"}

    # Geen AI-gegenereerde featured images meer (zelfde aanpak als Revaleur):
    # Daniel ontwerpt de afbeeldingen zelf en levert ze handmatig aan, wat
    # constantere kwaliteit geeft dan AI-generatie. Bij een update wordt een
    # eventueel al ingesteld image niet overschreven — zie preserve-logica onder.
    featured_image_url = None

    candidates = [
        {
            "intent_key": f'{p["region"]}:{p["pillar"]}:{p["slug"]}',
            "title": p["title"],
            "url_path": _url_path(p["region"], p["pillar"], p["slug"]),
            "link_terms": _link_terms_for(p),
        }
        for p in existing
    ] + STATIC_LINK_CANDIDATES
    body_with_links, linked_intents = apply_internal_links(generated["body_html"], candidates, intent_key)

    software_json_ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "CrossList EU",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "description": "Automatisch crosslisten en synchroniseren van advertenties tussen Marktplaats, 2dehands, Vinted, eBay, Etsy en Shopify, inclusief achtergrond-synchronisatie van voorraad en status.",
        "offers": {"@type": "Offer", "priceCurrency": "EUR"},
        "featureList": [
            "Automatisch crosslisten naar meerdere platforms",
            "Achtergrond-synchronisatie van verkochte items",
            "Bulk import van bestaande advertenties",
        ],
    }

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    canonical = f"{SITE_URL}{_url_path(region, pillar, slug)}"
    article_json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": generated["h1"],
        "description": generated["meta_description"],
        "image": featured_image_url or f"{SITE_URL}/Logo Crosslist EU.png",
        "author": {"@type": "Person", "name": "Daniel", "url": f"{SITE_URL}/nl/reseller-tools/over-de-auteur"},
        "publisher": {"@type": "Organization", "name": "CrossList EU", "url": SITE_URL},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "datePublished": now_iso,
        "dateModified": now_iso,
    }

    row = {
        "pillar": pillar,
        "region": region,
        "slug": slug,
        "primary_keyword": keyword,
        "title": generated["title"],
        "meta_description": generated["meta_description"],
        "h1": generated["h1"],
        "quick_answer": generated["quick_answer"],
        "takeaways": generated.get("takeaways") or [],
        "body_html": body_with_links,
        "faq": generated["faq"],
        "featured_image_url": featured_image_url,
        "software_application_json_ld": software_json_ld,
        "competitor_research": research,
        "related_slugs": linked_intents,
        "status": "published",
    }

    existing_row = db.table("content_pages").select("id,published_at").eq("intent_key", intent_key).execute().data
    if existing_row:
        row_id = existing_row[0]["id"]
        article_json_ld["dateModified"] = now_iso
        row["article_json_ld"] = article_json_ld
        db.table("content_pages").update(row).eq("id", row_id).execute()
        logger.info(f"Bestaande pagina bijgewerkt (cannibalisatie voorkomen): {intent_key}")
        action = "updated"
    else:
        row["published_at"] = now_iso
        row["article_json_ld"] = article_json_ld
        db.table("content_pages").insert(row).execute()
        logger.info(f"Nieuwe pagina aangemaakt: {intent_key}")
        action = "created"

    return {"success": True, "action": action, "url_path": _url_path(region, pillar, slug), "linked": linked_intents}
