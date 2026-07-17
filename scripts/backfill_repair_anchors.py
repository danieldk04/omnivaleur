"""
Eenmalige backfill: repareert content_pages waar de interne link-engine een
<a>…</a> ín een tag-attribuut heeft geïnjecteerd (kapotte <img src=...>).

Draai eerst als dry-run (default) om de schade te zien; pas met --apply schrijft
hij de gerepareerde body_html terug naar Supabase.

    python scripts/backfill_repair_anchors.py            # dry-run
    python scripts/backfill_repair_anchors.py --apply     # schrijf reparaties weg
"""
import sys

from backend.database import get_db
from backend.content.linking import repair_anchors_in_tags


def main(apply: bool) -> None:
    db = get_db()
    rows = db.table("content_pages").select("id,slug,language,body_html").execute().data or []
    print(f"{len(rows)} pagina's gescand\n")

    damaged = []
    for r in rows:
        body = r.get("body_html") or ""
        fixed = repair_anchors_in_tags(body)
        if fixed != body:
            damaged.append((r, fixed))

    if not damaged:
        print("Geen kapotte pagina's gevonden.")
        return

    print(f"{len(damaged)} kapotte pagina('s):\n")
    for r, _ in damaged:
        print(f"  - {r['slug']} ({r['language']})  id={r['id']}")

    if not apply:
        print("\nDRY-RUN — niets weggeschreven. Draai met --apply om te repareren.")
        return

    print("\nRepareren...")
    for r, fixed in damaged:
        db.table("content_pages").update({"body_html": fixed}).eq("id", r["id"]).execute()
        print(f"  gerepareerd: {r['slug']} ({r['language']})")
    print(f"\nKlaar — {len(damaged)} pagina('s) gerepareerd.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
