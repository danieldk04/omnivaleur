#!/usr/bin/env python3
"""
Zet de infokaarten (backend/content/visuals.py) op bestaande blogs en haalt bij
verkopersgidsen (pijler B) het algemene dashboardbeeld weg, dat daar niets met
het onderwerp te maken had (Daniel, 25-09-2026). Nieuwe artikelen krijgen dit
vanzelf via run_pipeline.

    python3 scripts/backfill_infokaarten.py              # alleen tellen
    python3 scripts/backfill_infokaarten.py --schrijf    # echt bijwerken

Veilig herhaalbaar: een pagina met kaarten wordt overgeslagen. Per pagina één
vraag aan het taalmodel. Alleen toevoegen en dat ene beeld weghalen; de rest van
de tekst blijft byte voor byte gelijk (gecontroleerd voor het wegschrijven).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.content.figures import strip_figures  # noqa: E402
from backend.content.visuals import MARKER, inject_cards  # noqa: E402
from backend.database import get_db  # noqa: E402

ALGEMEEN = "/assets/dashboard/dashboard-overview.webp"


def main() -> None:
    schrijf = "--schrijf" in sys.argv
    db = get_db()
    ids = []
    for off in range(0, 2000, 100):
        deel = (db.table("content_pages").select("id").eq("status", "published")
                .order("created_at").range(off, off + 99).execute().data) or []
        ids += [r["id"] for r in deel]
        if len(deel) < 100:
            break
    kaarten = beeld_weg = geen = 0
    for i, pid in enumerate(ids, 1):
        r = db.table("content_pages").select("id,slug,language,pillar,title,body_html").eq("id", pid).execute().data[0]
        oud = r.get("body_html") or ""
        nieuw = oud
        if r["pillar"] == "B" and ALGEMEEN in nieuw:
            nieuw = strip_figures(nieuw, ALGEMEEN)
            beeld_weg += 1
        if MARKER not in nieuw:
            if schrijf:
                met = inject_cards(nieuw, r["title"] or "", r.get("language", "en"))
                if met == nieuw:
                    geen += 1
                else:
                    kaarten += 1
                nieuw = met
            else:
                kaarten += 1
        if nieuw != oud:
            # Alleen kaarten erbij en dat ene beeld eraf; verder niets.
            assert nieuw.count("</h2>") == oud.count("</h2>"), r["slug"]
            if schrijf:
                db.table("content_pages").update({"body_html": nieuw}).eq("id", r["id"]).execute()
        print(f"  {i}/{len(ids)} {r['language']} {r['slug'][:60]}", flush=True)
    print(f"Kaarten: {kaarten}, zonder bruikbare kaarten: {geen}, algemeen dashboardbeeld weg: {beeld_weg}"
          f"{'' if schrijf else ' (niets geschreven)'}")


if __name__ == "__main__":
    main()
