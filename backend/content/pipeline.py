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

from backend.content.generator import generate_page_content, needs_dutch_translation, translate_to_dutch, inject_article_screenshots
from backend.content.hero import generate_hero
from backend.content.web_images import inject_platform_images
from backend.content.infographics import inject_infographics
from backend.content.linking import apply_internal_links
from backend.content.research import research_competitors
from backend.content.schema_validate import validate_page
from backend.database import get_db
from backend.services.email import notify_published
from backend.services.indexnow import submit_url
from backend.services.search_console import get_top_pages

logger = logging.getLogger(__name__)

SITE_URL = "https://omnivaleur.com"


def _afgekapt(generated: dict) -> list[str]:
    """De publicatienorm meldt van alles, maar afgekapte tekst is geen nalatigheid
    maar kapotte content: die mag nooit live. Daarom hier apart en blokkerend,
    terwijl de overige normpunten waarschuwingen blijven.

    Aanleiding: vijf artikelen stonden live die middenin een zin ophielden en één
    FAQ-antwoord bestond uit het woord "It"."""
    from backend.content.quality import check_article

    return [p for p in check_article(generated) if p.startswith("AFGEKAPT")]


def _word_count(body_html: str) -> int:
    return len(re.findall(r"\S+", re.sub(r"<[^>]+>", " ", body_html or "")))

# Altijd-beschikbare interne linkkandidaten, ook als er nog geen andere
# content_pages bestaan — zo heeft zelfs de allereerste pagina al zinvolle
# interne links in plaats van een orphan page.
STATIC_LINK_CANDIDATES = [
    {"intent_key": "static:home", "title": "Omnivaleur", "url_path": "/", "link_terms": ["Omnivaleur"]},
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
        "name": "Omnivaleur",
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
    candidates.sort(key=lambda c: clicks_by_url.get(f"https://omnivaleur.com{c['url_path']}", 0), reverse=True)
    candidates += STATIC_LINK_CANDIDATES
    body_with_links, linked_intents = apply_internal_links(generated["body_html"], candidates, intent_key)

    existing_row = db.table("content_pages").select("id,featured_image_url,published_at").eq("intent_key", intent_key).execute().data
    featured_image_url = existing_row[0].get("featured_image_url") if existing_row else None

    # Elke pagina krijgt een eigen hero-/deelafbeelding. Voorheen had 24 van de 25
    # pagina's helemaal geen og:image (leeg blok bij delen) en toonde de pagina
    # zelf bij iedereen hetzelfde kleurvlak. Een handmatig gezette afbeelding via
    # /api/content/set-image blijft leidend — die overschrijven we nooit.
    if not featured_image_url or "/assets/blog/hero/" in (featured_image_url or ""):
        hero = generate_hero(slug, generated["h1"], pillar, keyword)
        if hero:
            featured_image_url = f"{SITE_URL}{hero}"

    now_iso = datetime.now(timezone.utc).isoformat()
    # datePublished mag bij een herschrijving NIET meeschuiven: dat maakt van elk
    # ververst artikel een "nieuw" artikel, en Google ziet dan een pagina die
    # steeds opnieuw zogenaamd net gepubliceerd is. Alleen dateModified beweegt.
    published_iso = (existing_row[0].get("published_at") if existing_row else None) or now_iso
    canonical = f"{SITE_URL}{_url_path(language, pillar, slug)}"
    article_json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": generated["h1"],
        "description": generated["meta_description"],
        "image": featured_image_url or f"{SITE_URL}/logo.png",
        "author": {
            "@type": "Person",
            "name": "Daniel de Koning",
            "jobTitle": "Founder, Omnivaleur",
            "url": SITE_URL,
            "knowsAbout": ["cross-listing", "reselling", "Marktplaats", "Vinted", "eBay", "Etsy", "Shopify"],
        },
        "publisher": {
            "@type": "Organization",
            "name": "Omnivaleur",
            "url": SITE_URL,
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/logo.png"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "inLanguage": language,
        # wordCount is een echte schema.org-eigenschap (signaal van diepgang), en
        # tegelijk de reden dat de blog-index de body_html niet meer hoeft op te
        # halen om de leestijd te tonen — dat scheelde 0,57 MB Supabase-verkeer
        # per bezoek aan /blog.
        "wordCount": _word_count(generated["body_html"]),
        "datePublished": published_iso,
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

    # `row` meegeven zodat de kwaliteitscontrole de pagina toetst zoals hij
    # daadwerkelijk is opgeslagen — mét interne links en hero. Die twee worden
    # hier pas toegevoegd, dus toetsen op het ruwe generatorresultaat zou altijd
    # onterecht "geen hero" en "te weinig interne links" melden.
    return {"success": True, "action": action, "url_path": url_path, "linked": linked_intents, "intent_key": intent_key, "row": row}


async def run_pipeline(
    keyword: str,
    region: str,
    pillar: str,
    slug: str,
    nl_slug: str | None = None,
    refresh_context: dict | None = None,
) -> dict:
    """
    `refresh_context` is alleen gezet wanneer de evaluator een bestaande, slecht
    presterende pagina laat herschrijven (backend/content/evaluator.py). De slug
    blijft dan gelijk, dus `_save_page_row` werkt de bestaande rij bij en de URL
    verandert niet — er komt geen concurrerend duplicaat bij.
    """
    db = get_db()

    logger.info(f"Research voor '{keyword}' ({region})")
    research = research_competitors(keyword, region)

    logger.info(f"Content genereren (Engels) voor '{keyword}'")
    existing_for_prompt_rows = db.table("content_pages").select("title,language,pillar,slug").eq("status", "published").limit(50).execute().data or []
    existing_for_prompt = [{"title": p["title"], "url_path": _url_path(p.get("language", "en"), p["pillar"], p["slug"])} for p in existing_for_prompt_rows]

    generated = generate_page_content(keyword, region, pillar, slug, research, existing_for_prompt, refresh_context)
    if not generated:
        return {"success": False, "error": "content generation failed"}
    kapot = _afgekapt(generated)
    if kapot:
        logger.error(f"'{keyword}' is afgekapt en wordt NIET gepubliceerd: {'; '.join(kapot)}")
        return {"success": False, "error": f"afgekapte tekst: {'; '.join(kapot)}"}
    generated["body_html"] = inject_article_screenshots(
        generated["body_html"], pillar, keyword, generated["h1"], slug, language="en"
    )
    generated["body_html"] = inject_platform_images(
        generated["body_html"], keyword, language="en", title=generated["h1"]
    )
    generated["body_html"] = inject_infographics(generated["body_html"], language="en")

    result = _save_page_row(
        db, region=region, pillar=pillar, slug=slug, keyword=keyword,
        language="en", translation_of=None, generated=generated, research=research,
    )

    # Toetsen ná het opslaan, tegen de rij zoals hij live gaat staan.
    schema_warnings = validate_page(result.get("row") or generated)
    if schema_warnings:
        logger.warning(f"Publicatienorm niet volledig gehaald voor '{keyword}': {'; '.join(schema_warnings)}")

    if needs_dutch_translation(keyword, region):
        nl_path = publish_dutch_companion(
            db, region=region, pillar=pillar, keyword=keyword,
            db_nl_slug=f"{nl_slug or slug}-nl", source=generated,
            source_intent_key=result["intent_key"], inject_media=True,
        )
        if nl_path:
            # No reverse pointer needed on the English row — content.py looks up the
            # NL companion by querying translation_of = <this row's intent_key>.
            result["nl_translation"] = nl_path

    try:
        notify_published(keyword, result["url_path"], result["action"], schema_warnings)
    except Exception as e:
        logger.error(f"Publicatie-melding mislukt (niet-blokkerend): {e}")

    return result


def publish_dutch_companion(
    db,
    *,
    region: str,
    pillar: str,
    keyword: str,
    db_nl_slug: str,
    source: dict,
    source_intent_key: str,
    inject_media: bool,
) -> str | None:
    """Vertaalt één Engels artikel naar het Nederlands en publiceert het.

    Twee pogingen: de vertaling faalde in de praktijk vooral doordat het antwoord
    halverwege afbrak, en dat is bij een tweede poging meestal over. Lukt het dan
    nog niet, dan pakt de dagelijkse inhaalronde (`translate_missing_pages`) het
    artikel later alsnog op — vroeger bleef het voorgoed zonder NL-versie.

    `inject_media` staat alleen aan bij een vers gegenereerd artikel; bij de
    inhaalronde zitten de beelden al in de opgeslagen tekst en zou opnieuw
    injecteren ze dubbel zetten.
    """
    translated = None
    for poging in (1, 2):
        kandidaat = translate_to_dutch(source)
        if kandidaat and _afgekapt(kandidaat):
            logger.error(f"NL-vertaling van '{keyword}' is afgekapt (poging {poging})")
            kandidaat = None
        if kandidaat:
            translated = kandidaat
            break

    if not translated:
        logger.warning(f"NL-vertaling mislukt voor '{keyword}' — Engelse pagina blijft voorlopig zonder companion")
        return None

    if inject_media:
        translated["body_html"] = inject_article_screenshots(
            translated["body_html"], pillar, keyword, translated["h1"], db_nl_slug, language="nl"
        )
        translated["body_html"] = inject_platform_images(
            translated["body_html"], keyword, language="nl", title=translated["h1"]
        )
        translated["body_html"] = inject_infographics(translated["body_html"], language="nl")

    nl_result = _save_page_row(
        db, region=region, pillar=pillar, slug=db_nl_slug, keyword=keyword,
        language="nl", translation_of=source_intent_key, generated=translated, research=None,
    )
    return nl_result["url_path"]


def translate_missing_pages(limit: int = 3) -> dict:
    """Inhaalronde: Engelse artikelen zonder Nederlandse tweeling alsnog vertalen.

    Elke mislukte vertaling liet tot nu toe een gat achter dat nooit meer werd
    gedicht. Deze ronde loopt dagelijks en pakt de oudste gaten eerst; `limit`
    houdt het aantal Claude-aanroepen per ronde in de hand.
    """
    db = get_db()
    rows = (
        db.table("content_pages")
        .select("*")
        .eq("status", "published")
        .eq("language", "en")
        .is_("translation_of", "null")
        .order("published_at", desc=False)
        .execute()
        .data
        or []
    )
    vertaald = (
        db.table("content_pages")
        .select("translation_of")
        .eq("status", "published")
        .eq("language", "nl")
        .execute()
        .data
        or []
    )
    heeft_nl = {r["translation_of"] for r in vertaald if r.get("translation_of")}

    ontbreekt = [r for r in rows if f'{r["region"]}:{r["pillar"]}:{r["slug"]}' not in heeft_nl]
    logger.info(f"NL-inhaalronde: {len(ontbreekt)} Engelse pagina's zonder vertaling")

    gedaan: list[str] = []
    for row in ontbreekt[:limit]:
        intent_key = f'{row["region"]}:{row["pillar"]}:{row["slug"]}'
        try:
            path = publish_dutch_companion(
                db,
                region=row["region"],
                pillar=row["pillar"],
                keyword=row.get("primary_keyword") or row["slug"],
                db_nl_slug=f'{row["slug"]}-nl',
                source=row,
                source_intent_key=intent_key,
                inject_media=False,
            )
        except Exception as e:
            logger.error(f"NL-inhaalronde mislukt voor {intent_key}: {e}")
            continue
        if path:
            gedaan.append(path)

    return {"ontbrak": len(ontbreekt), "vertaald": gedaan}
