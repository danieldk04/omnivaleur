#!/usr/bin/env python3
"""Dubbele advertenties opruimen die uit een dubbele import zijn ontstaan.

WAAROM (07-09-2026, De Juiste Toon). "Ook zie ik continue dubbele advertenties
verschijnen." Gemeten op zijn echte gegevens: vier artikelrijen met de titel
"Oosters tapijt klein 60/38 cm", alle vier 20 euro, alle vier met exact dezelfde
vijf foto-adressen, en alle vier met een eigen advertentie die live op
Marktplaats staat. Geplaatst op 05-09 (twee), 06-09 en 07-09: er kwam er elke
dag een bij. Dat is precies wat hij beschreef.

De oorzaak is gerepareerd (`_zelfde_artikel_al_online` in
backend/services/crosslist.py blokkeert sinds 07-09-2026 het publiceren van een
artikel waarvan de tweeling al online staat), maar de advertenties die er al
staan gaan daar niet vanzelf van weg.

WAAROM NIET OP TITEL. Toon heeft acht verschillende dameslederhosen die allemaal
"Lederhosen dames" heten en die allemaal los te koop moeten kunnen staan. Op de
titel alleen zouden we er zeven weggooien. Het bewijs zit in de foto: twee rijen
die letterlijk hetzelfde foto-adres delen komen uit dezelfde bron en zijn
hetzelfde voorwerp.

WAAROM TWEE METINGEN. Onze eigen administratie klopt hier niet: gemeten stonden
er 434 rijen op "live op Marktplaats" tegen 366 echte advertenties, en van 57
artikelen met twee actieve rijen had er geen ENKELE er echt twee online staan.
Een verwijderopdracht op een advertentienummer dat niet meer bestaat is
verspilde moeite. Daarom kijken we niet in onze database maar in het openbare
aanbod van de verkoper zelf, en wel twee keer los van elkaar: pas wat in beide
metingen ontbreekt geldt als weg. Dezelfde regel die de gewone controleronde
hanteert (twee keer niet gezien, zie backend/services/polling.py).

Wat dit script doet, en niets anders:

  1. Groepeert de artikelen van deze verkoper op titel EN gedeeld foto-adres.
  2. Kijkt in het openbare aanbod welke advertenties van die groep echt live
     staan (twee metingen).
  3. Houdt per groep en per kanaal de NIEUWSTE live advertentie aan — die staat
     het hoogst in de zoekresultaten — en zet voor elke oudere een
     verwijderopdracht klaar, op advertentienummer.
  4. Raakt niets aan bij een groep waarvan een advertentie verkocht is.

Zonder --apply verandert er niets.

Gebruik:
    python3 scripts/ruim_dubbele_advertenties_uit_import.py --user <uuid>
    python3 scripts/ruim_dubbele_advertenties_uit_import.py --user <uuid> --apply
"""
import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BROK = 200
LEVEND = ("active", "hidden", "pending", "relisting")


def _alle(db, tabel, kolommen, **eq):
    uit, start = [], 0
    while True:
        q = db.table(tabel).select(kolommen)
        for k, v in eq.items():
            q = q.eq(k, v)
        rijen = q.range(start, start + 999).execute().data or []
        uit += rijen
        if len(rijen) < 1000:
            return uit
        start += 1000


async def _openbaar_aanbod(verkopers: dict[str, int]) -> dict[str, set[str]]:
    """De advertentienummers die nu echt online staan, twee keer gemeten.

    De tweede meting bladert met een andere paginagrootte, zodat het geen
    herhaling van dezelfde vraag is maar een losse waarneming.
    """
    import httpx
    from backend.services.mp_enrich import UA, ZOEK_PER_PLATFORM

    uit: dict[str, set[str]] = {}
    async with httpx.AsyncClient(timeout=40, headers={"User-Agent": UA},
                                 follow_redirects=True) as c:
        for kanaal, vid in verkopers.items():
            adressen = ZOEK_PER_PLATFORM.get(kanaal)
            if not adressen or not vid:
                continue
            gezien: set[str] = set()
            for grootte in (100, 50):
                for pagina in range(0, 40):
                    r = await c.get(adressen[0], params={
                        "sellerIds[]": vid, "limit": grootte,
                        "offset": pagina * grootte})
                    rijen = (r.json().get("listings") or [])
                    gezien |= {str(l.get("itemId")) for l in rijen if l.get("itemId")}
                    if len(rijen) < grootte:
                        break
                await asyncio.sleep(0.5)
            uit[kanaal] = gezien
            print(f"{kanaal}: {len(gezien)} advertenties echt online")
    return uit


def _families(items: list[dict]) -> list[list[dict]]:
    """Artikelen die hetzelfde voorwerp zijn: zelfde titel én een gedeelde foto."""
    per_titel = defaultdict(list)
    for it in items:
        titel = (it.get("title") or "").strip().lower()
        if titel:
            per_titel[titel].append(it)

    uit = []
    for rijen in per_titel.values():
        if len(rijen) < 2:
            continue
        # Binnen één titel: alles wat via een gedeeld foto-adres aan elkaar hangt
        # in dezelfde groep. Twee rijen zonder foto's horen nergens bij.
        groepen: list[tuple[set, list]] = []
        for it in rijen:
            fotos = {u for u in (it.get("photo_urls") or []) if u}
            if not fotos:
                continue
            raak = [g for g in groepen if g[0] & fotos]
            if not raak:
                groepen.append((set(fotos), [it]))
                continue
            samen_f, samen_i = set(fotos), [it]
            for g in raak:
                samen_f |= g[0]
                samen_i += g[1]
                groepen.remove(g)
            groepen.append((samen_f, samen_i))
        uit += [g[1] for g in groepen if len(g[1]) > 1]
    return uit


def main(user_id: str, apply: bool) -> None:
    from backend.database import get_db
    from backend.services.crosslist import _last_listed_title, EXTENSION_PLATFORMS

    db = get_db()
    items = _alle(db, "items", "id,title,price,photo_urls,created_at", user_id=user_id)
    if not items:
        print(f"Geen artikelen gevonden voor {user_id}.")
        return
    item_van = {it["id"]: it for it in items}

    listings = []
    ids = list(item_van)
    for i in range(0, len(ids), BROK):
        listings += (db.table("listings")
                     .select("id,item_id,platform,status,platform_listing_id,"
                             "platform_listing_url,listed_at,created_at")
                     .in_("item_id", ids[i:i + BROK]).execute().data or [])

    fam = _families(items)
    print(f"{len(items)} artikelen, {len(listings)} advertentieregels, "
          f"{len(fam)} groepen met meer dan één rij voor hetzelfde voorwerp.")
    if not fam:
        return

    in_families = {it["id"] for groep in fam for it in groep}
    kanalen = {l["platform"] for l in listings
               if l["item_id"] in in_families and l["platform"] in EXTENSION_PLATFORMS}

    # Verkopersnummer per kanaal opzoeken via de eigen titels, net als mp_enrich.
    async def _nummers():
        import httpx
        from backend.services.mp_enrich import UA, ZOEK_PER_PLATFORM, zoek_verkoper_id
        titels = [it["title"] for it in items[:200] if it.get("title")]
        uit = {}
        async with httpx.AsyncClient(timeout=40, headers={"User-Agent": UA},
                                     follow_redirects=True) as c:
            for kanaal in kanalen:
                adressen = ZOEK_PER_PLATFORM.get(kanaal)
                if not adressen:
                    continue
                uit[kanaal] = await zoek_verkoper_id(c, titels, zoek_url=adressen[0])
                print(f"{kanaal}: verkopersnummer {uit[kanaal]}")
        return uit

    verkopers = asyncio.run(_nummers())
    live = asyncio.run(_openbaar_aanbod({k: v for k, v in verkopers.items() if v}))
    if not live:
        print("Geen openbaar aanbod kunnen lezen — niets gedaan.")
        return

    per_item = defaultdict(list)
    for l in listings:
        per_item[l["item_id"]].append(l)

    te_verwijderen, overgeslagen = [], []
    for groep in fam:
        verkocht = [l for it in groep for l in per_item[it["id"]]
                    if l.get("status") in ("sold", "sold_unconfirmed")]
        if verkocht:
            overgeslagen.append((groep[0]["title"], "verkoopgeschiedenis"))
            continue
        per_kanaal = defaultdict(list)
        for it in groep:
            for l in per_item[it["id"]]:
                nummer = str(l.get("platform_listing_id") or "")
                if (l.get("status") in LEVEND and nummer
                        and l["platform"] in EXTENSION_PLATFORMS
                        and nummer in live.get(l["platform"], set())):
                    per_kanaal[l["platform"]].append(l)
        for kanaal, rijen in per_kanaal.items():
            if len(rijen) < 2:
                continue
            rijen.sort(key=lambda r: str(r.get("listed_at") or r.get("created_at") or ""),
                       reverse=True)
            houden, weg = rijen[0], rijen[1:]
            print(f"\n{groep[0]['title'][:55]!r} op {kanaal}: "
                  f"{len(rijen)} advertenties van hetzelfde voorwerp")
            print(f"   blijft staan: {houden['platform_listing_id']} "
                  f"({str(houden.get('listed_at'))[:19]})")
            for r in weg:
                print(f"   weghalen    : {r['platform_listing_id']} "
                      f"({str(r.get('listed_at'))[:19]})")
                te_verwijderen.append(r)

    for titel, reden in overgeslagen:
        print(f"\novergeslagen: {titel[:55]!r} — {reden}")

    print(f"\n{len(te_verwijderen)} advertentie(s) om weg te halen.")
    if not apply:
        print("(Proefdraai — er is niets gewijzigd. Draai met --apply om het echt te doen.)")
        return

    gezet = 0
    for r in te_verwijderen:
        item = db.table("items").select("*").eq("id", r["item_id"]).single().execute().data
        payload = {
            **item,
            "title": _last_listed_title(db, r["item_id"], r["platform"],
                                        item.get("title", "")),
            "platform_listing_id": r["platform_listing_id"],
            "platform_listing_url": r.get("platform_listing_url"),
        }
        db.table("jobs").insert({
            "user_id": user_id,
            "item_id": r["item_id"],
            "platform": r["platform"],
            "action": "delete",
            "status": "pending",
            "payload": payload,
        }).execute()
        gezet += 1
    print(f"Klaar: {gezet} verwijderopdracht(en) klaargezet.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    main(a.user, a.apply)
