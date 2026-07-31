#!/usr/bin/env python3
"""
Toetst álle gepubliceerde blogartikelen aan de publicatienorm
(backend/content/quality.py) en zet de uitkomst op een rij.

Waarvoor: de norm zit ingebakken in de pijplijn, maar een norm die niemand
nameet zakt vanzelf weg. Dit script maakt zichtbaar of het niveau vasthoudt —
en welke pagina's achterblijven. De dagelijkse GitHub Action draait 'm na elke
publicatie, dus een terugval valt binnen een dag op.

Gebruik:
    python3 scripts/check_blog_quality.py            # overzicht
    python3 scripts/check_blog_quality.py --verbose  # ook wat er goed gaat
    python3 scripts/check_blog_quality.py --strict   # exitcode 1 als iets zakt

Exitcode is standaard 0 (een waarschuwing mag de cron niet laten omvallen);
met --strict wordt het 1 zodra één artikel niet aan de norm voldoet.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main(argv: list[str]) -> int:
    from backend.content.quality import check_article
    from backend.database import get_db

    verbose = "--verbose" in argv
    strict = "--strict" in argv

    db = get_db()
    rows = (
        db.table("content_pages")
        .select("slug,language,pillar,title,meta_description,h1,quick_answer,takeaways,body_html,faq,featured_image_url")
        .eq("status", "published")
        .execute()
        .data
        or []
    )

    failing = []
    reasons: Counter[str] = Counter()

    for row in sorted(rows, key=lambda r: (r.get("language", "en"), r["slug"])):
        problems = check_article(row)
        label = f"{row['slug']} ({row.get('language', 'en')})"
        if problems:
            failing.append((label, problems))
            # Het eerste woord van elke melding als categorie, voor de samenvatting.
            for p in problems:
                reasons[p.split(":")[0].split("(")[0].strip()] += 1
        elif verbose:
            print(f"  ok      {label}")

    for label, problems in failing:
        print(f"  ONDER NORM  {label}")
        for p in problems:
            print(f"      - {p}")

    total = len(rows)
    good = total - len(failing)
    print(f"\n{good}/{total} artikelen voldoen aan de publicatienorm")
    if reasons:
        print("\nMeest voorkomende tekortkomingen:")
        for reason, count in reasons.most_common(8):
            print(f"  {count:3d}x  {reason}")

    return 1 if (strict and failing) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
