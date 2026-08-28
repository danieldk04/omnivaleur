"""
Ontbrekende omschrijvingen aanvullen vanuit de eigen webshop van de verkoper.

WAAROM DIT ER IS (28-08-2026, Jaap van zilverwebsite.nl)
Advertenties die uit de zoeklijst van Marktplaats zijn geïmporteerd komen binnen
met titel, prijs en het omslagplaatje — zonder omschrijving. Het plaatsformulier
van Marktplaats WEIGERT een advertentie zonder tekst. Bij het automatisch
herplaatsen (eerst weg, dan opnieuw) betekende dat: de oude advertentie was weg
en de nieuwe kwam er nooit. Op één dag verdwenen zo 60 advertenties, en omdat
Marktplaats een verwijderde advertentie meteen op 410 zet was de tekst zelf ook
onherstelbaar weg.

De teksten staan wél nog ergens: in zijn eigen webshop, met dezelfde titels.
Dit script haalt ze daar op en vult ALLEEN lege omschrijvingen aan.

Werkt voor elke Shopify-winkel (`/products.json` is daar openbaar). Koppelen
gaat op genormaliseerde titel, en alleen binnen het aanbod van deze ene
verkoper — twee verkopers kunnen dezelfde titel hebben, één verkoper vrijwel
nooit. Bij twee producten met exact dezelfde titel slaan we het item over in
plaats van te gokken.

Gebruik:
    python scripts/backfill_beschrijving_uit_webshop.py \
        --email info@zilverwebsite.nl --shop www.zilverwebsite.nl        # proef
    python scripts/backfill_beschrijving_uit_webshop.py ... --schrijf    # echt
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata

import json
import subprocess

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.platforms.shopify_importer import _platte_tekst  # noqa: E402

# WAAROM CURL EN NIET httpx.
# De winkel staat achter Cloudflare, en die geeft een Python-client een
# "Verifying your connection..."-pagina (429, cf-mitigated: challenge) — ook mét
# een browser-User-Agent, want de herkenning zit in het TLS-handtekeningetje van
# de client zelf. Dezelfde aanvraag via curl, met de headers die een echte
# browser meestuurt, komt er gewoon door. Gemeten 28-08-2026 op
# www.zilverwebsite.nl: httpx 429, curl 200.
BROWSER_HEADERS = [
    "-H", ("User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "-H", "Accept: application/json,text/plain,*/*",
    "-H", "Accept-Language: nl-NL,nl;q=0.9,en;q=0.8",
    "-H", ('sec-ch-ua: "Chromium";v="140", "Not=A?Brand";v="24", '
           '"Google Chrome";v="140"'),
    "-H", "sec-ch-ua-mobile: ?0",
    "-H", 'sec-ch-ua-platform: "macOS"',
    "-H", "Sec-Fetch-Dest: empty",
    "-H", "Sec-Fetch-Mode: cors",
    "-H", "Sec-Fetch-Site: same-origin",
]
PER_PAGINA = 250
PAUZE = 2.0          # de winkel van een klant is niet van ons: rustig aan
MAX_PAGINAS = 60


def _json_via_curl(url: str):
    """De JSON van één pagina, of None als het niet lukte."""
    uit = subprocess.run(
        ["curl", "-s", "--http2", "--compressed", "--max-time", "40", *BROWSER_HEADERS, url],
        capture_output=True, text=True)
    if uit.returncode != 0 or not uit.stdout.strip().startswith("{"):
        return None
    try:
        return json.loads(uit.stdout)
    except json.JSONDecodeError:
        return None


def sleutel(titel: str) -> str:
    """Zelfde normalisatie als mp_enrich: zonder accenten, leestekens, dubbele spaties."""
    t = unicodedata.normalize("NFKD", str(titel or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t.lower())).strip()


def haal_producten(shop: str) -> dict[str, str]:
    """Titel -> platte omschrijving. Dubbele titels vallen af (te onzeker)."""
    basis = shop if shop.startswith("http") else f"https://{shop}"
    per_titel: dict[str, str] = {}
    dubbel: set[str] = set()
    pagina = 1
    while pagina <= MAX_PAGINAS:
        data = None
        for poging in range(5):
            data = _json_via_curl(f"{basis}/products.json?limit={PER_PAGINA}&page={pagina}")
            if data is not None:
                break
            time.sleep(5 * (poging + 1))
        if data is None:
            print(f"  pagina {pagina}: blijft weigeren, gestopt")
            break
        producten = data.get("products") or []
        if not producten:
            break
        for p in producten:
            s = sleutel(p.get("title"))
            tekst = _platte_tekst(p.get("body_html") or "")
            if not s or not tekst:
                continue
            if s in per_titel and per_titel[s] != tekst:
                dubbel.add(s)
            per_titel.setdefault(s, tekst)
        print(f"  pagina {pagina}: {len(producten)} producten ({len(per_titel)} met tekst)")
        pagina += 1
        time.sleep(PAUZE)
    for s in dubbel:
        per_titel.pop(s, None)
    if dubbel:
        print(f"  {len(dubbel)} titel(s) kwamen dubbel voor met verschillende tekst — overgeslagen")
    return per_titel


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--shop", required=True, help="bv. www.zilverwebsite.nl")
    ap.add_argument("--schrijf", action="store_true", help="zonder deze vlag: alleen tellen")
    args = ap.parse_args()

    from supabase import create_client
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    gebruiker = next((u for u in db.auth.admin.list_users()
                      if (u.email or "").lower() == args.email.lower()), None)
    if not gebruiker:
        print(f"Geen gebruiker met e-mailadres {args.email}")
        return 1

    items, start = [], 0
    while True:
        rij = (db.table("items").select("id,title,description")
               .eq("user_id", gebruiker.id).range(start, start + 999).execute().data or [])
        items += rij
        if len(rij) < 1000:
            break
        start += 1000
    leeg = [i for i in items if not str(i.get("description") or "").strip()]
    print(f"{len(items)} items, {len(leeg)} zonder omschrijving")
    if not leeg:
        return 0

    print(f"Webshop {args.shop} uitlezen...")
    teksten = haal_producten(args.shop)
    print(f"{len(teksten)} producten met een omschrijving gevonden")

    gevuld, niet_gevonden = 0, []
    for item in leeg:
        tekst = teksten.get(sleutel(item.get("title")))
        if not tekst:
            niet_gevonden.append(item.get("title"))
            continue
        if args.schrijf:
            db.table("items").update({"description": tekst}).eq("id", item["id"]).execute()
        gevuld += 1

    print(f"\n{'GEVULD' if args.schrijf else 'ZOU VULLEN'}: {gevuld}")
    print(f"Niet teruggevonden op de webshop: {len(niet_gevonden)}")
    for t in niet_gevonden[:15]:
        print(f"  - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
