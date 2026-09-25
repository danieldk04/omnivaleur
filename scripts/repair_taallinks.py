#!/usr/bin/env python3
"""
Laat in alle gepubliceerde blogs elke link wijzen naar de pagina in de taal van
dat artikel (linking.herschrijf_taallinks). Nieuwe artikelen krijgen dit sinds
25-09-2026 vanzelf in pipeline._save_page_row; dit script haalt de achterstand in.

    python3 scripts/repair_taallinks.py            # alleen tellen
    python3 scripts/repair_taallinks.py --schrijf  # echt bijwerken

Veilig herhaalbaar. Raakt alleen <a>-tags naar blogpagina's; het aantal
afbeeldingen en alinea's wordt per pagina gecontroleerd voor het wegschrijven.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.content.linking import herschrijf_taallinks  # noqa: E402
from backend.content.pipeline import link_index  # noqa: E402
from backend.database import get_db  # noqa: E402


def main() -> None:
    schrijf = "--schrijf" in sys.argv
    db = get_db()
    index = link_index(db)
    totaal_om = totaal_weg = paginas = 0
    for off in range(0, 2000, 25):
        deel = (db.table("content_pages").select("id,slug,language,body_html")
                .eq("status", "published").order("created_at").range(off, off + 24).execute().data) or []
        for r in deel:
            oud = r.get("body_html") or ""
            nieuw, om, weg = herschrijf_taallinks(oud, r.get("language", "en"), index)
            if nieuw == oud:
                continue
            assert nieuw.count("<img") == oud.count("<img") and nieuw.count("</p>") == oud.count("</p>"), r["slug"]
            paginas += 1
            totaal_om += om
            totaal_weg += weg
            if schrijf:
                db.table("content_pages").update({"body_html": nieuw}).eq("id", r["id"]).execute()
        if len(deel) < 25:
            break
    print(f"{paginas} pagina's, {totaal_om} links omgezet, {totaal_weg} weggehaald"
          f"{'' if schrijf else ' (niets geschreven)'}")


if __name__ == "__main__":
    main()
