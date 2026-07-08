#!/usr/bin/env python3
"""
One-off backfill: generates the missing Dutch companion page for every already-
published English content_pages row that doesn't have one yet. Needed after
broadening needs_dutch_translation() from "Marktplaats/2dehands only" to "every
article" — existing pages published before that change need a companion added
retroactively; new pages get one automatically going forward via run_pipeline().

Usage:
    python3 scripts/backfill_nl_translations.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    from backend.content.generator import translate_to_dutch
    from backend.content.pipeline import _save_page_row, _url_path
    from backend.database import get_db

    db = get_db()
    rows = db.table("content_pages").select("*").eq("status", "published").eq("language", "en").execute().data or []
    nl_translation_of = {
        r["translation_of"]
        for r in db.table("content_pages").select("translation_of").eq("status", "published").execute().data or []
        if r.get("translation_of")
    }

    missing = [r for r in rows if f"{r['region']}:{r['pillar']}:{r['slug']}" not in nl_translation_of]
    print(f"{len(missing)} EN page(s) missing an NL companion")

    for row in missing:
        intent_key = f"{row['region']}:{row['pillar']}:{row['slug']}"
        print(f"→ {intent_key} ({row['title']})")
        generated = {
            "title": row["title"],
            "meta_description": row["meta_description"],
            "h1": row["h1"],
            "quick_answer": row["quick_answer"],
            "takeaways": row.get("takeaways") or [],
            "body_html": row["body_html"],
            "faq": row["faq"],
        }
        translated = translate_to_dutch(generated)
        if not translated:
            print("  ❌ vertaling mislukt, overgeslagen")
            continue

        nl_slug = f"{row['slug']}-nl"
        result = _save_page_row(
            db,
            region=row["region"],
            pillar=row["pillar"],
            slug=nl_slug,
            keyword=row["primary_keyword"],
            language="nl",
            translation_of=intent_key,
            generated=translated,
            research=None,
        )
        print(f"  ✅ {result['url_path']}")


if __name__ == "__main__":
    asyncio.run(main())
