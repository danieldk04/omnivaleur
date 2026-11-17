#!/usr/bin/env python3
"""Meting: kan de GRATIS Google-sleutel de groepsvraag voor rubrieken aan?

UITKOMST (17-11-2026, 's middags, al gemeten): zelfde 80 artikelen, Haiku 99% geldig / 81% zelfde
tak / 54% exact gelijk aan de bestaande indeling; Google 98% / 82% / 42%. Op beide kiezen ze bij
slechts 44 van 80 dezelfde rubriek. Google kan het dus technisch (4 vragen, 28 s, geen mislukking),
maar kiest minder consistent. Het scheelt ~13 cent per import van 300 artikelen. Besluit: Haiku
blijft de enige weg, Google-eerst NIET bouwen tenzij Daniel erom vraagt. Het script blijft als
hulpmiddel om het opnieuw te meten (drempels hieronder zijn voor een eerlijke vergelijking te streng
voor "zelfde tak"; vergelijk liever met Haiku op dezelfde artikelen).

WAAROM (17-11-2026). backend/services/rubriek_groepen.py vraagt twintig artikelen per
vraag aan Claude Haiku ($0,0004 per artikel). Als Google de groepsvraag gratis kan
beantwoorden, kunnen de kosten naar nul, met Haiku als reserve. Google was bij het
schrijven op (429), dus dit is nooit gemeten.

WANNEER. Pas na 09:00 Nederlandse tijd (Google zet de gratis limiet dan terug) en
voordat de dag het weer opmaakt. Doe het als eerste klus.

HOE (de server draait op de gratis sleutel; Railway levert hem, geen bestand nodig):
    cd ~/Documents/omnivaleur
    npx -y @railway/cli run python3.13 scripts/meet_groepsvraag_gemini.py

UITSLAG. Alle vier moeten kloppen, anders blijft Haiku de enige weg:
    mislukte vragen = 0 van 4
    kreeg een geldige rubriek >= 90%
    zelfde tak als de bestaande indeling >= 85%   (Haiku haalde 86 tot 90%)
    binnen 60 seconden klaar
Klopt het, bouw dan in rubriek_groepen.deel_in: eerst Google per groep, en alleen de
groepen die mislukten of leeg bleven naar Haiku. Test en meet opnieuw. Klopt het niet,
zet het resultaat in docs/team-notes.md en laat het zo.
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.database import get_db  # noqa: E402
from backend.api import imports as I  # noqa: E402
from backend.services import gemini_vertaling as G  # noqa: E402
from backend.services import rubriek_groepen as R  # noqa: E402

N_ARTIKELEN, GROEP = 80, R.GROEP


def main() -> int:
    db = get_db()
    rijen = (db.table("items").select("id,title,description,brand,category")
             .neq("category", "").not_.is_("category", "null")
             .order("created_at", desc=True).limit(400).execute().data)
    rijen = [x for x in rijen if x["category"] in I._ALL_CATEGORIES and x.get("title")][:N_ARTIKELEN]
    if len(rijen) < 40:
        print("te weinig artikelen met rubriek om te meten"); return 2
    systeem = R._systeemtekst()
    t0 = time.time(); mislukt = geldig = zelfde_tak = 0
    for i in range(0, len(rijen), GROEP):
        groep = rijen[i:i + GROEP]
        raw = G.vraag(systeem + "\n\nListings:\n" + R._gebruikertekst(groep),
                      max_tokens=60 * len(groep) + 200, tijdslimiet=60, denken=False)
        uit = R._lees_antwoord(raw, groep) if raw else {}
        if not uit:
            mislukt += 1; continue
        for x in groep:
            a = uit.get(x["id"], {})
            if a.get("category"):
                geldig += 1
                zelfde_tak += I._TAK_VAN_RUBRIEK[x["category"]] == a["gender"]
    n, calls = len(rijen), -(-len(rijen) // GROEP)
    print(f"artikelen {n}, vragen {calls}, mislukt {mislukt}, geldige rubriek {geldig/n:.0%}, "
          f"zelfde tak {zelfde_tak/n:.0%}, {time.time()-t0:.0f}s")
    ok = mislukt == 0 and geldig / n >= 0.90 and zelfde_tak / n >= 0.85 and time.time() - t0 < 60
    print("UITSLAG:", "GOOGLE KAN HET, bouw Google-eerst" if ok else "NIET GENOEG, laat Haiku de enige weg")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
