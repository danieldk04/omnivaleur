#!/usr/bin/env python3
"""
Past de volledige blog-upgrade toe op ALLE al gepubliceerde artikelen.

Nieuwe artikelen krijgen dit alles automatisch via run_pipeline(); dit script is
er voor de pagina's die al live stonden. Wat het per pagina doet:

  1. Markdown-restanten (**vet**, *cursief*) omzetten naar echte HTML — die
     stonden als letterlijke sterretjes in de lopende tekst.
  2. Merknaam-als-werkwoord repareren ("Omnivaleur from Vinted to eBay" →
     "Cross-list from Vinted to eBay"), ook in de meta-description.
  3. Oude, irrelevante en ongecomprimeerde beelden eruit: de .jpg-platformshots
     en de vaste vijf /assets/comparisons/-PNG's die in elk artikel hetzelfde
     waren.
  4. Verse app-screenshots erin die bij het ONDERWERP passen, per slug geroteerd,
     plus platform-screenshots van alleen de platforms uit titel/keyword.
  5. Een eigen hero-/deelafbeelding genereren en als featured_image_url zetten.
  6. Interne links aanvullen tot 5.
  7. Article-schema bijwerken (auteur, uitgever, datePublished blijft staan).

Idempotent en niet-destructief: draait het twee keer, dan verandert er de tweede
keer niets. De tekst zelf wordt nooit herschreven — alleen opmaak, beeld, links
en metadata. Voor een echte inhoudelijke herschrijving is er de evaluator.

Gebruik:
    python3 scripts/backfill_blog_upgrade.py --dry-run    # tonen wat er zou gebeuren
    python3 scripts/backfill_blog_upgrade.py              # toepassen
    python3 scripts/backfill_blog_upgrade.py --slug vinted-to-ebay
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SITE_URL = "https://omnivaleur.com"


def _link_candidates(db, rows: list[dict], self_intent_key: str, language: str) -> list[dict]:
    """Interne-linkkandidaten in dezelfde taal, gesorteerd op echte
    Search Console-clicks, plus de vaste sitebrede links."""
    from backend.content.pipeline import STATIC_LINK_CANDIDATES, _link_terms_for, _url_path
    from backend.services.search_console import get_top_pages

    candidates = [
        {
            "intent_key": f'{p["region"]}:{p["pillar"]}:{p["slug"]}',
            "title": p["title"],
            "url_path": _url_path(p.get("language", "en"), p["pillar"], p["slug"]),
            "link_terms": _link_terms_for(p),
        }
        for p in rows
        if p.get("language", "en") == language and f'{p["region"]}:{p["pillar"]}:{p["slug"]}' != self_intent_key
    ]

    clicks = {p["url"]: p["clicks"] for p in get_top_pages(days=90, row_limit=200)}
    candidates.sort(key=lambda c: clicks.get(f"{SITE_URL}{c['url_path']}", 0), reverse=True)
    return candidates + STATIC_LINK_CANDIDATES


def upgrade_row(db, row: dict, all_rows: list[dict]) -> dict | None:
    """Berekent de nieuwe waarden voor één rij, of None als er niets verandert."""
    from backend.content.figures import strip_figures
    from backend.content.generator import clean_generated, inject_article_screenshots
    from backend.content.hero import generate_hero
    from backend.content.linking import apply_internal_links
    from backend.content.web_images import inject_platform_images, strip_platform_images

    language = row.get("language", "en")
    pillar = row["pillar"]
    slug = row["slug"]
    keyword = row.get("primary_keyword", "")
    intent_key = f'{row["region"]}:{pillar}:{slug}'

    original = {
        "title": row.get("title", ""),
        "meta_description": row.get("meta_description", ""),
        "h1": row.get("h1", ""),
        "quick_answer": row.get("quick_answer", ""),
        "takeaways": list(row.get("takeaways") or []),
        "body_html": row.get("body_html") or "",
        "faq": [dict(f) for f in (row.get("faq") or [])],
    }

    cleaned = clean_generated({k: (list(v) if isinstance(v, list) else v) for k, v in original.items()})

    # Oude beeldsets eruit vóór de nieuwe erin — anders stapelen ze op.
    body = strip_platform_images(cleaned["body_html"])
    body = strip_figures(body, "/assets/comparisons/")
    body = strip_figures(body, "/assets/dashboard/")
    # Ook de concurrent-screenshots: die worden bij het opnieuw injecteren
    # meegenomen, dus zonder deze regel kwam er bij elke run een extra set bij.
    # Strippen op de host van de beeld-URL, niet op de CSS-klasse: figuren van
    # vóór deze wijziging dragen die klasse nog niet.
    body = strip_figures(body, "cdn.prod.website-files.com")

    body = inject_article_screenshots(body, pillar, keyword, cleaned["h1"], slug, language=language)
    body = inject_platform_images(body, keyword, language=language, title=cleaned["h1"])

    body, linked = apply_internal_links(body, _link_candidates(db, all_rows, intent_key, language), intent_key)

    featured = row.get("featured_image_url")
    # Een handmatig gezette afbeelding blijft staan — tenzij hij 404't (dat was
    # het geval bij /blog/vinted-to-ebay.png) of het al onze eigen hero is.
    hero_slot = (
        not featured
        or "/assets/blog/hero/" in featured
        or featured.startswith(f"{SITE_URL}/blog/")
    )
    if hero_slot:
        hero = generate_hero(slug, cleaned["h1"], pillar, keyword)
        if hero:
            featured = f"{SITE_URL}{hero}"

    now_iso = datetime.now(timezone.utc).isoformat()
    article_json_ld = dict(row.get("article_json_ld") or {})
    article_json_ld.update({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": cleaned["h1"],
        "description": cleaned["meta_description"],
        "image": featured or f"{SITE_URL}/logo.png",
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
        "inLanguage": language,
        # wordCount: schema.org-signaal van diepgang, én de reden dat de
        # blog-index de body_html niet meer hoeft op te halen voor de leestijd.
        "wordCount": len(__import__("re").findall(r"\S+", __import__("re").sub(r"<[^>]+>", " ", body))),
        # datePublished behouden: een herschrijving is geen nieuwe publicatie.
        "datePublished": article_json_ld.get("datePublished") or row.get("published_at") or now_iso,
        "dateModified": now_iso,
    })

    changes = {
        "title": cleaned["title"],
        "meta_description": cleaned["meta_description"],
        "h1": cleaned["h1"],
        "quick_answer": cleaned["quick_answer"],
        "takeaways": cleaned["takeaways"],
        "faq": cleaned["faq"],
        "body_html": body,
        "featured_image_url": featured,
        "article_json_ld": article_json_ld,
        "related_slugs": sorted(set((row.get("related_slugs") or []) + linked)),
    }

    # Alleen echt gewijzigde velden terugsturen; article_json_ld verandert altijd
    # (dateModified), dus die telt niet mee als "er is iets gebeurd".
    meaningful = {k: v for k, v in changes.items() if k != "article_json_ld" and v != row.get(k)}
    if not meaningful:
        return None
    return changes


def main(argv: list[str]) -> int:
    from backend.database import get_db

    dry_run = "--dry-run" in argv
    only_slug = None
    if "--slug" in argv:
        only_slug = argv[argv.index("--slug") + 1]

    db = get_db()
    rows = db.table("content_pages").select("*").eq("status", "published").execute().data or []
    targets = [r for r in rows if not only_slug or r["slug"].startswith(only_slug)]
    print(f"{len(rows)} gepubliceerde pagina('s); {len(targets)} in scope\n")

    updated = skipped = 0
    for row in sorted(targets, key=lambda r: (r.get("language", "en"), r["slug"])):
        try:
            changes = upgrade_row(db, row, rows)
        except Exception as e:
            print(f"  ❌ {row['slug']} ({row.get('language')}) — mislukt: {e}")
            continue

        if not changes:
            skipped += 1
            continue

        body = changes["body_html"]
        summary = (
            f"{body.count('/assets/dashboard/')} app-shot(s), "
            f"{body.count('/assets/platforms/')} platform-shot(s), "
            f"{len(changes['related_slugs'])} interne link(s)"
        )
        print(f"  ✅ {row['slug']:52s} ({row.get('language')}) {summary}")

        if not dry_run:
            db.table("content_pages").update(changes).eq("id", row["id"]).execute()
        updated += 1

    verb = "zou bijwerken" if dry_run else "bijgewerkt"
    print(f"\n{updated} pagina('s) {verb}, {skipped} al up-to-date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
