"""Staan de advertenties die wij "live" noemen ook echt op Marktplaats?

WAAROM DIT ER IS (05-09-2026, De Juiste Toon)

Zijn dashboard zei van 274 artikelen dat ze op Marktplaats stonden. Zijn eigen
openbare verkoperspagina toonde er 317, maar twintig van onze 274 zaten daar
niet bij, en hun advertentiepagina gaf 404. Ze bestonden dus niet meer, terwijl
hij ze in het overzicht groen zag staan. Dat is de duurste soort stilte: hij
denkt dat iets te koop staat en dat is het niet, en als zo'n artikel intussen
verkocht is blijft het ondertussen wél op Vinted en 2dehands staan.

De verkoopcontrole op de server kon dit niet zien. Die vraagt een pagina op met
de cookies van de verkoper (`polling.POLL_PLATFORMS`), en Toon heeft geen
Marktplaats-koppeling: zijn advertenties krijgen wel een stempel maar worden
nooit echt nagekeken. De controle die de extensie zelf doet leest zijn eigen
"Mijn advertenties", en dat overzicht is bij een zakelijk account leeg — precies
waarom een lege uitkomst daar nooit als "weg" mag tellen.

De openbare zoek-API van Marktplaats heeft die bezwaren geen van beide: geen
login nodig, en hij toont alles van één verkoper. Dat is de bron die dit script
gebruikt.

DIT SCRIPT SCHRIJFT NIETS. Het meldt alleen wat het ziet. Een advertentie op
"weg" zetten op grond van één ronde is precies de fout waar `not_found_count`
en de scanbeveiliging tegen beschermen; die afweging hoort niet in een
losse controle thuis.

Gebruik:
    python scripts/controleer_advertenties_online.py --email djt@dejuistetoon.eu
    python scripts/controleer_advertenties_online.py --email ... --alles
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv

IN_BROK = 200


def _norm(t: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def vergelijk(actief: list[dict], lijst: dict[str, str],
              titel_van: dict[str, str], gekoppeld: set[str]):
    """Wat er mis is tussen onze administratie en zijn openbare lijst.

    Losgetrokken van de rest zodat de vergelijking te beproeven is zonder
    Marktplaats en zonder database.

    - verdwenen  : wij noemen hem live, het nummer staat er niet, en er staat ook
                   niets met dezelfde titel. Dit is het dure geval.
    - hernummerd : het nummer klopt niet meer maar de advertentie staat er wél,
                   onder een nieuw nummer. Administratie, geen verkoopprobleem.
    - los        : staat op zijn lijst, hangt bij ons aan geen enkel artikel.
    """
    op_titel: dict[str, list[str]] = {}
    for nummer, titel in lijst.items():
        op_titel.setdefault(_norm(titel), []).append(nummer)

    verdwenen, hernummerd = [], []
    for r in actief:
        if r["platform_listing_id"] in lijst:
            continue
        titel = titel_van.get(r["item_id"], "")
        elders = op_titel.get(_norm(titel))
        if elders:
            hernummerd.append((titel, r["platform_listing_id"], elders))
        else:
            verdwenen.append((titel, r["platform_listing_id"], None))
    los = [(n, t) for n, t in lijst.items() if n not in gekoppeld]
    return verdwenen, hernummerd, los


async def openbare_lijst(client: httpx.AsyncClient, verkoper_id: int) -> dict[str, str]:
    """Alle advertenties van deze verkoper: {advertentienummer: titel}."""
    from backend.services.mp_enrich import ZOEK, PAGINA, MAX_PAGINAS, _json
    uit: dict[str, str] = {}
    for pagina in range(MAX_PAGINAS):
        data = await _json(client, ZOEK, {"sellerIds[]": verkoper_id,
                                          "limit": PAGINA, "offset": pagina * PAGINA})
        rijen = data.get("listings") or []
        for r in rijen:
            if r.get("itemId"):
                uit[r["itemId"]] = r.get("title") or ""
        totaal = data.get("totalResultCount") or 0
        if not rijen or len(uit) >= totaal:
            break
        await asyncio.sleep(1.0)   # beleefd blijven, zie de 403-throttling in mp_enrich
    return uit


async def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", help="het e-mailadres van de verkoper")
    ap.add_argument("--user-id", help="of meteen zijn account-id, als het opzoeken niet mag")
    ap.add_argument("--platform", default="marktplaats")
    ap.add_argument("--alles", action="store_true",
                    help="ook tonen wat er op zijn lijst staat zonder koppeling bij ons")
    args = ap.parse_args()

    from backend.database import get_db
    from backend.services.mp_enrich import BASIS, UA, zoek_verkoper_id
    db = get_db()

    uid = args.user_id
    if not uid:
        if not args.email:
            print("Geef --email of --user-id op.")
            return 1
        # Het opzoeken van een adres vraagt de servicesleutel; de gewone client
        # draait op de anon-sleutel en krijgt daar "User not allowed" terug.
        sleutel = os.environ.get("SUPABASE_SERVICE_KEY")
        if not sleutel:
            print("Zonder SUPABASE_SERVICE_KEY kan ik geen adres opzoeken. "
                  "Geef --user-id op.")
            return 1
        from supabase import create_client
        beheer = create_client(os.environ["SUPABASE_URL"], sleutel)
        for gebruiker in beheer.auth.admin.list_users():
            if (gebruiker.email or "").lower() == args.email.lower():
                uid = gebruiker.id
                break
        if not uid:
            print(f"Geen account gevonden voor {args.email}")
            return 1

    items, off = [], 0
    while True:
        blok = db.table("items").select("id,title").eq("user_id", uid).range(off, off + 999).execute().data
        items += blok
        off += len(blok)
        if len(blok) < 1000:
            break
    titel_van = {r["id"]: r["title"] for r in items}
    if not items:
        print("Dit account heeft geen artikelen.")
        return 0

    rijen = []
    ids = list(titel_van)
    for i in range(0, len(ids), IN_BROK):
        rijen += (db.table("listings")
                  .select("item_id,status,platform_listing_id")
                  .in_("item_id", ids[i:i + IN_BROK])
                  .eq("platform", args.platform)
                  .not_.is_("platform_listing_id", "null")
                  .execute().data or [])
    actief = [r for r in rijen if r["status"] == "active"]
    print(f"{args.email or uid}: {len(items)} artikelen, {len(actief)} advertenties die wij "
          f"'live op {args.platform}' noemen.")

    async with httpx.AsyncClient(base_url=BASIS, headers={"User-Agent": UA},
                                 timeout=30, follow_redirects=True) as client:
        titels = [titel_van[r["item_id"]] for r in actief[:40] if titel_van.get(r["item_id"])]
        verkoper_id = await zoek_verkoper_id(client, titels)
        if not verkoper_id:
            print("Zijn verkopersnummer is niet te vinden op de openbare zoekpagina. "
                  "Zonder dat nummer is er niets te vergelijken; dit is geen uitspraak "
                  "over zijn advertenties.")
            return 2
        lijst = await openbare_lijst(client, verkoper_id)

    print(f"Openbare verkoperspagina (nummer {verkoper_id}): {len(lijst)} advertenties.\n")
    if not lijst:
        print("De lijst kwam leeg terug. Dat is een reden om de meting te wantrouwen, "
              "geen reden om te denken dat er niets meer online staat.")
        return 2

    gekoppeld = {r["platform_listing_id"] for r in rijen}
    verdwenen, hernummerd, los = vergelijk(actief, lijst, titel_van, gekoppeld)

    print(f"STAAT ER NIET MEER: {len(verdwenen)}")
    for t, nummer, _ in sorted(verdwenen):
        print(f"   {t[:56]:56s} {nummer}")
    if hernummerd:
        print(f"\nSTAAT ER WEL, MAAR ONDER EEN ANDER NUMMER: {len(hernummerd)}")
        for t, oud, nieuw in sorted(hernummerd):
            print(f"   {t[:46]:46s} wij: {oud}  daar: {', '.join(nieuw)}")

    print(f"\nOP ZIJN LIJST ZONDER KOPPELING BIJ ONS: {len(los)}"
          + ("" if args.alles else "   (--alles toont welke)"))
    if args.alles:
        for n, t in sorted(los, key=lambda x: x[1]):
            print(f"   {t[:56]:56s} {n}")

    print("\nEr is niets gewijzigd; dit script kijkt alleen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
