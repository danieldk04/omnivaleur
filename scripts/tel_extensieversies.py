#!/usr/bin/env python3
"""
Wie draait welke extensieversie, en loopt er iemand achter?

WAAROM DIT ER IS (05-09-2026). Uit de foutmeldingen bleek dat geen van de negen
afleesbare verkopers de versie uit de Web Store draaide; de oudste zat 43
versies achter. Sindsdien werkt de extensie zichzelf bij (1.0.304) en schrijft
de server de versie mee in extension_heartbeat. Dit script is de nameting: doet
dat bijwerken echt zijn werk, of blijven mensen hangen.

Draaien:  python3 scripts/tel_extensieversies.py
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Dezelfde vraag die Chrome stelt om te kijken of er een update is; het antwoord
# is een doorverwijzing met de versie in de bestandsnaam.
_WEBSTORE_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect&acceptformat=crx3&prodversion=126.0"
    "&x=id%3Dgfaogapbhaacfbpdppdcmnkjndlphleh%26installsource%3Dondemand%26uc"
)


def winkelversie() -> str | None:
    try:
        import httpx
        r = httpx.get(_WEBSTORE_URL, follow_redirects=False, timeout=10.0)
        m = re.search(r"_(\d+)_(\d+)_(\d+)(?:_\d+)?\.crx", r.headers.get("location") or "", re.I)
        return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}" if m else None
    except Exception as e:  # noqa: BLE001
        print(f"(versie uit de Web Store ophalen mislukt: {e})")
        return None


def main() -> None:
    from backend.database import get_db

    db = get_db()
    winkel = winkelversie()
    print(f"In de Chrome Web Store staat: {winkel or 'onbekend'}\n")

    rijen = (db.table("extension_heartbeat")
             .select("user_id,last_seen,ext_version")
             .order("last_seen", desc=True).execute().data or [])
    nu = datetime.now(timezone.utc)

    def uren(ts: str | None) -> float | None:
        try:
            d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return (nu - d).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            return None

    def nummer(v: str | None):
        try:
            return tuple(int(x) for x in str(v).split("."))
        except Exception:  # noqa: BLE001
            return None

    winkel_n = nummer(winkel)
    achter = gelijk = onbekend = 0
    print(f"{'versie':11s}{'laatst gezien':>18s}   computer")
    for r in rijen:
        u = uren(r.get("last_seen"))
        # Wie een week niets van zich liet horen zegt niets over het bijwerken:
        # zijn computer stond gewoon uit.
        if u is None or u > 24 * 7:
            continue
        v = r.get("ext_version")
        vn = nummer(v)
        # Vergelijken op volgorde, niet op "anders dan de winkel": een met de
        # hand geladen kopie kan NIEUWER zijn dan wat er gepubliceerd staat, en
        # die als achterlopend tellen maakt de meting onzin.
        if not vn:
            onbekend += 1
            merk = "  <-- geen versie"
        elif winkel_n and vn < winkel_n:
            achter += 1
            merk = "  <-- achter"
        elif winkel_n and vn > winkel_n:
            gelijk += 1
            merk = "  (voor de winkel uit)"
        else:
            gelijk += 1
            merk = ""
        print(f"{str(v or '-'):11s}{u:14.1f} uur   {r['user_id'][:8]}{merk}")

    totaal = achter + gelijk + onbekend
    print(f"\nActief in de laatste week: {totaal}")
    print(f"  bij: {gelijk}   achter: {achter}   versie onbekend: {onbekend}")
    if onbekend:
        print("\n'Versie onbekend' betekent meestal een kopie van vóór 1.0.304, of een\n"
              "server die opstartte voordat de kolom ext_version bestond.")


if __name__ == "__main__":
    main()
