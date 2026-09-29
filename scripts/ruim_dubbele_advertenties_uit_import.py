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
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BROK = 200
LEVEND = ("active", "hidden", "pending", "relisting")


def _db():
    """De servicesleutel als die er is. Met de gewone sleutel ziet een script
    lokaal door de rijbeveiliging niets, en meldt het "geen artikelen"."""
    from backend import database
    from backend.config import settings
    if settings.supabase_service_key:
        from supabase import create_client
        # Ook voor de backendfuncties die zelf get_db() aanroepen.
        database._client = create_client(settings.supabase_url, settings.supabase_service_key)
    return database.get_db()


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
    from backend.services.crosslist import _last_listed_title, EXTENSION_PLATFORMS

    db = _db()
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

    for r in te_verwijderen:
        _verwijderopdracht(db, user_id, r)
    print(f"Klaar: {len(te_verwijderen)} verwijderopdracht(en) klaargezet.")


def _verwijderopdracht(db, user_id: str, r: dict) -> None:
    """Een verwijderopdracht op advertentienummer, met de titel waaronder hij
    online staat (daarop zoekt de extensie hem in het overzicht)."""
    from backend.services.crosslist import _last_listed_title
    item = db.table("items").select("*").eq("id", r["item_id"]).single().execute().data
    db.table("jobs").insert({
        "user_id": user_id,
        "item_id": r["item_id"],
        "platform": r["platform"],
        "action": "delete",
        "status": "pending",
        "payload": {
            **item,
            "title": _last_listed_title(db, r["item_id"], r["platform"],
                                        item.get("title", "")),
            "platform_listing_id": r["platform_listing_id"],
            "platform_listing_url": r.get("platform_listing_url"),
        },
    }).execute()


# ---------------------------------------------------------------------------
# TWEELINGEN OP DE EIGEN CODE IN DE OMSCHRIJVING (29-09-2026, De Juiste Toon)
# ---------------------------------------------------------------------------
# "Oude foto's, vermoedelijk van 2dehands, worden op Marktplaats gebruikt terwijl
# we de foto's op Vinted vernieuwen. Voorbeeld kleed Azteken A07."
#
# GEMETEN. Toon las zijn voorraad drie keer in: op 28-08 uit Vinted, op 05-09
# uit 2dehands en Marktplaats. Elk kleed werd zo twee tot vijf losse rijen, elk
# met de foto's van zijn eigen bron. A07 staat twee keer live op Marktplaats:
# m2443172233 met de acht Vinted-foto's (kleed op een stoel, dezelfde als nu op
# Vinted) en m2442933492 met de oude 2dehands-foto's (kleed buiten op de grond).
#
# Waarom de bestaande controles het misten: tweelingen.py herkent een tweeling
# aan het nummer VÓÓR de titel, en _families hierboven aan titel plus gedeelde
# foto. Toon zet zijn nummer in de OMSCHRIJVING ("A07", "Gf41", "TSL01"), de
# titels verschillen op "cm" na, en de foto's komen uit verschillende bronnen.
#
# De regel hier: dezelfde eigen code in de omschrijving ÉN dezelfde afmeting
# ("155/120"), plus de harde kleur/maat/merk/prijscontrole uit tweelingen.py.
# Codes worden hergebruikt (TXL30 is bij hem een tapijt van 183/124 én een van
# 150/96), dus de code alleen is niet genoeg. En twee rijen uit dezelfde bron
# (twee Vinted-advertenties met dezelfde code) kunnen twee exemplaren zijn: die
# groep blijft liggen.
#
# Wat er gebeurt: de rijen worden één rij, en dat is de Vinted-rij, want Vinted
# is waar hij zijn foto's bijhoudt. Per kanaal blijft één advertentie staan:
# die van de Vinted-rij als die echt live staat, anders de nieuwste. De rest
# krijgt een verwijderopdracht. Pas samengevoegd werkt een verkoop op het ene
# kanaal ook door naar de advertenties die bij de andere rij hoorden.

_CODE = re.compile(r"^[A-Za-z]{1,4}\d{1,4}$")
_AFMETING = re.compile(r"(?<!\d)(\d{2,3})\s*/\s*(\d{2,3})(?!\d)")
_CM = re.compile(r"(?<!\d)(\d{2,3})\s*cm\b", re.I)
_VERLOPEN = re.compile(r"expired-listing-root|expiredlisting-module"
                       r"|(advertentie|zoekertje)\s*(is)?\s*(helaas)?\s*verlopen")
_OPENBAAR = {"marktplaats": "https://www.marktplaats.nl/{}",
             "2dehands": "https://www.2dehands.be/{}"}


def eigen_codes(omschrijving: str | None) -> set[str]:
    """De losse codes die de verkoper in zijn omschrijving zet: A07, GF41, TSL01."""
    return {w.upper() for w in re.split(r"[\s,.;:!#()\[\]]+", omschrijving or "")
            if _CODE.match(w)}


def afmetingen(item: dict) -> set[str]:
    """"155/120" uit titel of omschrijving; anders "101cm" uit de titel."""
    tekst = f"{item.get('title') or ''}\n{item.get('description') or ''}"
    maten = {f"{a}/{b}" for a, b in _AFMETING.findall(tekst)}
    return maten or {f"{m}cm" for m in _CM.findall(item.get("title") or "")}


def bron(listings: list[dict]) -> str:
    """Het kanaal waaruit deze rij is ingelezen: dat van zijn oudste advertentierij."""
    rijen = sorted(listings, key=lambda l: str(l.get("created_at") or ""))
    return rijen[0]["platform"] if rijen else "?"


def families_op_code(items: list[dict]) -> list[list[dict]]:
    """Rijen die hetzelfde voorwerp zijn: zelfde eigen code én zelfde afmeting."""
    from backend.services.tweelingen import bekende_merken_van, plausibel
    merken = bekende_merken_van(items)
    maten = {it["id"]: afmetingen(it) for it in items}
    per_code = defaultdict(list)
    for it in items:
        if maten[it["id"]]:
            for c in eigen_codes(it.get("description")):
                per_code[c].append(it)
    ouder: dict[str, str] = {}

    def wortel(x: str) -> str:
        while ouder.get(x, x) != x:
            x = ouder[x]
        return x

    for rijen in per_code.values():
        for i, a in enumerate(rijen):
            for b in rijen[i + 1:]:
                if maten[a["id"]] & maten[b["id"]] and plausibel(a, b, merken) is None:
                    ouder[wortel(b["id"])] = wortel(a["id"])
    groepen = defaultdict(list)
    for it in items:
        if it["id"] in ouder or it["id"] in ouder.values():
            groepen[wortel(it["id"])].append(it)
    return [g for g in groepen.values() if len(g) > 1]


async def _live(listings: list[dict]) -> dict[str, bool | None]:
    """Per advertentierij: True = de advertentiepagina staat echt live, False =
    verlopen of weg, None = geen uitspraak. Rustig aan: MP en 2dehands kappen een
    snelle reeks af met 403."""
    import httpx
    from backend.services.verlopen_controle import UA
    uit: dict[str, bool | None] = {}
    async with httpx.AsyncClient(timeout=25, headers={"User-Agent": UA},
                                 follow_redirects=True) as c:
        for l in listings:
            nummer = str(l.get("platform_listing_id") or "")
            oordeel = None
            for poging in range(4):
                try:
                    r = await c.get(_OPENBAAR[l["platform"]].format(nummer))
                except Exception:  # noqa: BLE001 — geen verbinding is geen uitspraak
                    await asyncio.sleep(3)
                    continue
                if r.status_code in (403, 429, 503):
                    await asyncio.sleep(3 * (poging + 1))
                    continue
                tekst = (r.text or "").lower()
                if _VERLOPEN.search(tekst) or r.status_code in (404, 410):
                    oordeel = False
                elif r.status_code == 200 and nummer in str(r.url) and len(tekst) > 5000:
                    oordeel = True
                break
            uit[l["id"]] = oordeel
            await asyncio.sleep(1.5)
    return uit


def main_op_code(user_id: str, apply: bool) -> None:
    db = _db()
    items = _alle(db, "items", "id,user_id,title,description,price,price_marktplaats,"
                  "price_2dehands,photo_urls,created_at,sku,brand", user_id=user_id)
    ids = [it["id"] for it in items]
    listings = []
    for i in range(0, len(ids), BROK):
        listings += (db.table("listings")
                     .select("id,item_id,platform,status,platform_listing_id,"
                             "platform_listing_url,listed_at,created_at")
                     .in_("item_id", ids[i:i + BROK]).execute().data or [])
    per_item = defaultdict(list)
    for l in listings:
        per_item[l["item_id"]].append(l)

    fam = families_op_code(items)
    print(f"{len(items)} artikelen, {len(fam)} groepen met dezelfde eigen code én afmeting.")

    plannen, overgeslagen = [], []
    for groep in fam:
        bronnen = {it["id"]: bron(per_item[it["id"]]) for it in groep}
        dubbel = [b for b, n in Counter(bronnen.values()).items() if n > 1 and b != "?"]
        if dubbel:
            overgeslagen.append((groep, f"twee rijen uit {dubbel[0]}: mogelijk twee exemplaren"))
            continue
        if any(l.get("status") in ("sold", "sold_unconfirmed")
               for it in groep for l in per_item[it["id"]]):
            overgeslagen.append((groep, "verkoopgeschiedenis"))
            continue
        houden = (next((it for it in groep if bronnen[it["id"]] == "vinted"), None)
                  or min(groep, key=lambda i: str(i.get("created_at") or "")))
        plannen.append((groep, houden, bronnen))

    # Alleen waar een kanaal twee of meer 'levende' rijen heeft valt er iets te
    # kiezen; die advertentiepagina's kijken we echt na.
    na_te_kijken = []
    for groep, _, _ in plannen:
        per_kanaal = defaultdict(list)
        for it in groep:
            for l in per_item[it["id"]]:
                if l["status"] in LEVEND and l["platform"] in _OPENBAAR and l.get("platform_listing_id"):
                    per_kanaal[l["platform"]].append(l)
        na_te_kijken += [l for rijen in per_kanaal.values() if len(rijen) > 1 for l in rijen]
    print(f"{len(na_te_kijken)} advertentiepagina's nakijken…")
    live = asyncio.run(_live(na_te_kijken)) if na_te_kijken else {}

    te_verwijderen, oude_fotos, twijfel, prijzen = [], [], [], []
    for groep, houden, bronnen in plannen:
        ids_groep = {it["id"] for it in groep}
        print(f"\n{houden['title'][:60]!r}  ({'/'.join(sorted(eigen_codes(houden.get('description'))))})")
        for it in groep:
            print(f"   {'HOUDEN ' if it is houden else 'opgaan '} {bronnen[it['id']]:11} "
                  f"{len(it.get('photo_urls') or [])} foto's, {it.get('price')} euro, {it['id'][:8]}")
        for kanaal in _OPENBAAR:
            rijen = [l for i in ids_groep for l in per_item[i]
                     if l["platform"] == kanaal and l["status"] in LEVEND and l.get("platform_listing_id")]
            if not rijen:
                continue
            if len(rijen) > 1:
                echt = [l for l in rijen if live.get(l["id"]) is True]
                twijfel += [l for l in rijen if live.get(l["id"]) is None]
                if not echt:
                    continue
                echt.sort(key=lambda l: (l["item_id"] == houden["id"],
                                         str(l.get("listed_at") or l.get("created_at") or "")),
                          reverse=True)
                blijft, weg = echt[0], echt[1:]
                te_verwijderen += weg
            else:
                blijft = rijen[0]
            van = next(it for it in groep if it["id"] == blijft["item_id"])
            print(f"   {kanaal}: blijft {blijft['platform_listing_id']}"
                  + "".join(f", weg {l['platform_listing_id']}" for l in rijen
                            if l in te_verwijderen))
            if van is not houden and set(van.get("photo_urls") or []) != set(houden.get("photo_urls") or []):
                oude_fotos.append((kanaal, blijft, houden))
                print(f"      LET OP: die advertentie draagt de foto's van de {bronnen[van['id']]}-rij")
            veld = f"price_{kanaal}"
            if (van is not houden and van.get("price") and van.get("price") != houden.get("price")
                    and not houden.get(veld)):
                prijzen.append((houden["id"], veld, van["price"]))

    # WAT ER AL IN DE WACHTRIJ STAAT. Een herplaatsing van een advertentie die
    # weg moet zou hem met de oude foto's terugzetten, en een tweede
    # verwijderopdracht op hetzelfde nummer komt terug als "al weg" en dus als
    # verkoopvraag. Daarom: geen tweede verwijdering, en plaatsingen en
    # verlengingen voor een advertentie die weg moet gaan uit de rij.
    wachtend = []
    for i in range(0, len(ids), BROK):
        wachtend += (db.table("jobs")
                     .select("id,item_id,platform,action,status,payload->>platform_listing_id")
                     .in_("item_id", ids[i:i + BROK])
                     .in_("status", ["pending", "claimed", "running"]).execute().data or [])
    onderweg = {str(j.get("platform_listing_id")) for j in wachtend if j["action"] == "delete"}
    weg_nummers = {str(l["platform_listing_id"]) for l in te_verwijderen}
    weg_plekken = {(l["item_id"], l["platform"]) for l in te_verwijderen}
    nieuw = [l for l in te_verwijderen if str(l["platform_listing_id"]) not in onderweg]
    annuleren = [j["id"] for j in wachtend if j["status"] == "pending" and (
        (j["action"] == "extend" and str(j.get("platform_listing_id")) in weg_nummers)
        or (j["action"] == "create" and (j["item_id"], j["platform"]) in weg_plekken))]
    # Een rij waarvan een advertentie nog weg moet voegen we pas samen als die weg
    # is (tweede keer draaien). Anders heeft één artikel tijdelijk twee
    # advertenties op hetzelfde kanaal, en herplaatsen pakt dan zomaar de eerste.
    later = {l["item_id"] for l in te_verwijderen} | {
        j["item_id"] for j in wachtend if j["action"] == "delete"
        and any(str(l.get("platform_listing_id")) == str(j.get("platform_listing_id"))
                and l["status"] in LEVEND for l in per_item[j["item_id"]])
        and j["item_id"] not in {h["id"] for _, h, _ in plannen}}

    for groep, reden in overgeslagen:
        print(f"\novergeslagen: {groep[0]['title'][:55]!r}: {reden}")
    print(f"\n{len(plannen)} groepen worden één rij ({sum(len(g) - 1 for g, _, _ in plannen)} rijen gaan op, "
          f"waarvan {len(later)} pas bij de tweede keer draaien).")
    print(f"{len(te_verwijderen)} dubbele advertenties weg ({len(te_verwijderen) - len(nieuw)} al onderweg), "
          f"{len(twijfel)} zonder uitspraak blijven staan.")
    print(f"{len(annuleren)} wachtende plaatsingen/verlengingen van die advertenties uit de rij.")
    print(f"{len(oude_fotos)} advertenties houden de oude foto's tot ze herplaatst worden.")
    print(f"{len(prijzen)} kanaalprijzen overgenomen van de rij waarvan de advertentie blijft.")
    if not apply:
        print("(Proefdraai: er is niets gewijzigd. Draai met --apply om het echt te doen.)")
        return

    # 1. Eerst de verwijderopdrachten, zolang de rij van de advertentie nog bestaat.
    for l in nieuw:
        _verwijderopdracht(db, user_id, l)
    for jid in annuleren:
        db.table("jobs").update({"status": "cancelled"}).eq("id", jid).eq("status", "pending").execute()
    # 2. Samenvoegen zoals backend/api/items.merge_items dat doet: advertenties en
    #    opdrachten naar de Vinted-rij, de andere rijen weg. Foto's blijven staan.
    samengevoegd, geweigerd = 0, []
    for groep, houden, _ in plannen:
        for it in groep:
            if it is houden or it["id"] in later:
                continue
            try:
                db.table("listings").update({"item_id": houden["id"]}).eq("item_id", it["id"]).execute()
            except Exception as e:  # noqa: BLE001 — unieke sleutel: deze rij laten staan
                geweigerd.append((it["id"], str(e)[:120]))
                continue
            # Een wachtende plaatsing draagt een kopie van de oude rij, en dus de
            # oude foto's. Die krijgt de foto's van de rij die blijft.
            for j in (db.table("jobs").select("id,payload").eq("item_id", it["id"])
                      .eq("action", "create").eq("status", "pending").execute().data or []):
                db.table("jobs").update({"payload": {**(j.get("payload") or {}),
                                                     "photo_urls": houden.get("photo_urls")}}
                                        ).eq("id", j["id"]).execute()
            db.table("jobs").update({"item_id": houden["id"]}).eq("item_id", it["id"]).execute()
            db.table("items").delete().eq("id", it["id"]).eq("user_id", user_id).execute()
            samengevoegd += 1
    # 3. De prijs die op dat kanaal al stond blijft de prijs op dat kanaal.
    for item_id, veld, prijs in prijzen:
        db.table("items").update({veld: prijs}).eq("id", item_id).is_(veld, "null").execute()
    print(f"Klaar: {len(te_verwijderen)} verwijderopdrachten, {samengevoegd} rijen samengevoegd, "
          f"{len(geweigerd)} geweigerd {geweigerd[:3]}.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--op-code", action="store_true",
                   help="tweelingen op de eigen code in de omschrijving plus afmeting")
    a = p.parse_args()
    (main_op_code if a.op_code else main)(a.user, a.apply)
