#!/usr/bin/env python3
"""
Geeft elke blogpagina waar geen enkel ander artikel naar linkt ("wees") een
link vanuit hooguit drie verwante oudere pagina's in dezelfde taal. Zelfde
functie als de dagelijkse pijplijn sinds 25-09-2026 bij elk nieuw artikel
gebruikt (pipeline.link_back); dit script haalt de achterstand in.

    python3 scripts/backfill_terugkoppelingen.py            # alleen tonen
    python3 scripts/backfill_terugkoppelingen.py --schrijf  # echt bijwerken

Veilig herhaalbaar: een pagina die al naar de wees linkt, wordt overgeslagen.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.content.pipeline import _url_path, link_back  # noqa: E402
from backend.database import get_db  # noqa: E402


def main() -> None:
    schrijf = "--schrijf" in sys.argv
    db = get_db()
    rijen = []
    for off in range(0, 2000, 25):
        deel = (db.table("content_pages").select("slug,pillar,language,primary_keyword,title,body_html")
                .eq("status", "published").order("created_at").range(off, off + 24).execute().data) or []
        rijen += deel
        if len(deel) < 25:
            break

    paden = {_url_path(r.get("language", "en"), r["pillar"], r["slug"]): r for r in rijen}
    binnen = Counter()
    for r in rijen:
        eigen = _url_path(r.get("language", "en"), r["pillar"], r["slug"])
        for href in set(re.findall(r'href="(?:https?://(?:www\.)?omnivaleur\.com)?(/[^"#?]+)"', r.get("body_html") or "")):
            if href in paden and href != eigen:
                binnen[href] += 1

    wezen = [p for p in paden if binnen[p] == 0]
    print(f"{len(rijen)} pagina's, {len(wezen)} zonder inkomende link")
    totaal = 0
    for pad in wezen:
        r = paden[pad]
        bronnen = link_back(db, language=r.get("language", "en"), url_path=pad, title=r["title"],
                            keyword=r.get("primary_keyword") or "", dry_run=not schrijf)
        totaal += len(bronnen)
        print(f"  {pad}  ←  {', '.join(bronnen) or '(geen verwante pagina)'}")
    print(f"{'Geschreven' if schrijf else 'Zou schrijven'}: {totaal} links")


if __name__ == "__main__":
    main()
