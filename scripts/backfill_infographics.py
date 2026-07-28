#!/usr/bin/env python3
"""
Voegt infographics toe aan al gepubliceerde content_pages. Nieuwe artikelen
krijgen ze automatisch via de pijplijn; dit script haalt de bestaande voorraad bij.

Puur ADDITIEF: er wordt alleen een <figure> ingevoegd vóór de tabel of lijst waar
hij uit voortkomt. Er wordt nooit tekst vervangen of verwijderd, en de injectie is
idempotent (een artikel dat al een infographic heeft, wordt overgeslagen), dus het
script kan veilig meerdere keren draaien.

Gebruik:
    python3 scripts/backfill_infographics.py            # dry run: laat alleen zien wat er zou gebeuren
    python3 scripts/backfill_infographics.py --apply    # schrijf de wijzigingen weg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    from backend.content.infographics import inject_infographics
    from backend.database import get_db

    apply = "--apply" in sys.argv
    db = get_db()
    pages = (
        db.table("content_pages")
        .select("id,title,language,body_html")
        .eq("status", "published")
        .execute()
        .data
        or []
    )

    changed = 0
    for page in pages:
        original = page["body_html"]
        updated = inject_infographics(original, page.get("language") or "en")
        if updated == original:
            continue

        added = updated.count('class="infographic"')
        changed += 1
        print(f"{'✅' if apply else '·'} {page['title']} — {added} infographic(s)")
        if apply:
            db.table("content_pages").update({"body_html": updated}).eq("id", page["id"]).execute()

    print(f"\n{changed}/{len(pages)} artikelen {'bijgewerkt' if apply else 'zouden worden bijgewerkt'}.")
    if not apply and changed:
        print("Draai opnieuw met --apply om het weg te schrijven.")


if __name__ == "__main__":
    main()
