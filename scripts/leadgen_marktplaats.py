#!/usr/bin/env python3
"""
Leadgen voor Omnivaleur uit Marktplaats — verreweg de grootste bron.

WAAROM DEZE BRON BESTAAT
Instagram leverde live gemeten 411 handles, 194 profielen, 15 leads en NUL
e-mailadressen; er is daar alleen handmatig DM'en. Marktplaats gaf in vier minuten
scrapen 263.000 advertenties, 88.000 verkopers, 978 zakelijke verkopers en ruim
350 directe e-mailadressen. Dat is geen verbetering maar een andere orde van grootte.

DE DRIE DINGEN DIE DIT MOGELIJK MAKEN (alle drie live getest, 2026-08-10)
  1. De interne zoek-API van Marktplaats geeft 100 advertenties per verzoek als JSON:
     /lrp/api/search?l1CategoryId=..&l2CategoryId=..&limit=100&offset=..
     Dat is drie keer zoveel als een HTML-pagina en er is geen sleutel voor nodig.
  2. Elke advertentie draagt al een ZAKELIJK-SIGNAAL mee (showWebsiteUrl / isVerified).
     Met dat vlaggetje is 72% van de verkopers echt zakelijk, zonder is dat 3%.
     Dat filter kost geen enkel extra verzoek en scheelt een factor 25 aan werk.
  3. Van zakelijke verkopers staat het bedrijfsprofiel open: KvK bij 100%, telefoon
     bij 94%, e-mailadres bij 37%, plus handelsnaam, adres en een "over ons"-tekst.
     Particulieren hebben geen bedrijfsprofiel — dat het bestaat IS de zakelijk-toets.

TWEE VALKUILEN
  * De API stopt na 50 pagina's (5.000 advertenties) per categorie. Daarom sweept
    'discover' per SUBcategorie: elke subcategorie heeft zijn eigen plafond. Live
    gemeten leverde de subcategorie-ronde 451 nieuwe verkopers op 497 gevonden.
  * Categorie-ID's mag je niet gokken. 1032 lijkt kleding maar is Huizen en Kamers;
    een hele meting ging daardoor de eerste keer over verhuurbedrijven. De ID's
    hieronder komen uit `searchCategory` in de HTML van /l/{slug}/ en zijn nagelopen.

DE TRECHTER — zelfde vorm als leadgen_instagram.py
  discover  verkopers met zakelijk signaal uit de categorie-sweep
  enrich    bedrijfsprofiel erbij: KvK, telefoon, e-mail, adres, over-ons, aantal advertenties
  crosslist verkoopt hij al op meer plekken? eigen webshop, webshopsysteem, bol.com
  classify  Haiku beoordeelt op tweedehands, verzendbaar, winstmotief en NL/BE
  push      naar dezelfde Notion-Leadlist, met Platform "MP"
  run       alle vijf achter elkaar

Gebruik:
    export NOTION_TOKEN=...
    python3 scripts/leadgen_marktplaats.py run --dry-run
    python3 scripts/leadgen_marktplaats.py run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx  # noqa: E402

from scripts import leadgen_instagram as ig  # noqa: E402
from scripts import leadgen_notion as notion  # noqa: E402

OUT = Path(__file__).parent / "output" / "leads"
SELLERS = OUT / "mp_sellers.json"
MP_LEADS = OUT / "mp_leads.json"

API = "https://www.marktplaats.nl/lrp/api/search"
PROFILE = "https://www.marktplaats.nl/smb-profile/profile/{sid}"
SELLER_PAGE = "https://www.marktplaats.nl/u/x/{sid}/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# Alleen rubrieken met VERZENDBARE spullen. Huis-en-inrichting (1,6 miljoen
# advertenties) en antiek staan er bewust niet bij: banken en kasten gaan niet in
# een doos, en dat is precies de groep die de classificatie toch weer wegfiltert.
CATEGORIES = {
    "kleding-dames": 621,
    "kleding-heren": 1776,
    "sieraden-tassen-en-uiterlijk": 1826,
    "spelcomputers-en-games": 356,
    "audio-tv-en-foto": 31,
    "telecommunicatie": 820,
    "computers-en-software": 322,
    "sport-en-fitness": 784,
    "muziek-en-instrumenten": 728,
    "verzamelen": 895,
    "boeken": 201,
}

PAGE = 100
API_CAP = 5000          # 50 pagina's; daarboven geeft de API lege lijsten terug
MAX_FAILS = 3


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA}, timeout=30.0,
                        follow_redirects=True)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text()) if path.exists() else []


def _save(path: Path, rows: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- discover


def _search(client: httpx.Client, l1: int, l2: int | None, offset: int) -> list[dict]:
    params = {"l1CategoryId": l1, "limit": PAGE, "offset": offset}
    if l2:
        params["l2CategoryId"] = l2
    try:
        r = client.get(API, params=params)
        if r.status_code != 200:
            return []
        return r.json().get("listings") or []
    except Exception:  # noqa: BLE001 — één lege pagina mag de sweep niet stoppen
        return []


def _subcategories(client: httpx.Client, l1: int) -> list[tuple[int, str]]:
    try:
        d = client.get(API, params={"l1CategoryId": l1, "limit": 1}).json()
    except Exception:  # noqa: BLE001
        return []
    return [(o["id"], o.get("name") or "") for o in (d.get("searchCategoryOptions") or [])
            if o.get("id") and o["id"] != l1]


def discover(args) -> None:
    existing = _load(SELLERS)
    by_id = {r["seller_id"]: r for r in existing}
    print(f"{len(existing)} verkopers al verzameld\n")

    jobs: list[tuple[int, int | None, int, str]] = []
    with _client() as client:
        for slug, l1 in CATEGORIES.items():
            if args.categories and slug not in args.categories:
                continue
            jobs += [(l1, None, off, slug) for off in range(0, API_CAP, PAGE)]
            for l2, name in _subcategories(client, l1):
                jobs += [(l1, l2, off, f"{slug}/{name}")
                         for off in range(0, min(args.depth, API_CAP), PAGE)]
        print(f"{len(jobs)} verzoeken over "
              f"{len(args.categories or CATEGORIES)} rubrieken…")

        seen_ads = added = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_search, client, l1, l2, off): src
                       for l1, l2, off, src in jobs}
            for i, future in enumerate(as_completed(futures), 1):
                src = futures[future]
                for listing in future.result():
                    seen_ads += 1
                    s = listing.get("sellerInformation") or {}
                    sid = s.get("sellerId")
                    # Het gratis zakelijk-filter. Zonder deze regel verrijk je
                    # 25 particulieren voor elke handelaar.
                    if not sid or not (s.get("showWebsiteUrl") or s.get("isVerified")):
                        continue
                    row = by_id.get(sid)
                    if row:
                        row["ads_seen"] = row.get("ads_seen", 0) + 1
                        continue
                    row = {"seller_id": sid, "name": s.get("sellerName") or "",
                           "method": "marktplaats", "source": src, "ads_seen": 1,
                           # Doorklik-link van Marktplaats naar de eigen webshop.
                           # Bewaren loont: bij verkopers zonder e-mail in hun
                           # profiel staat het adres wél op hun contactpagina.
                           "site_link": s.get("sellerWebsiteUrl") or ""}
                    by_id[sid] = row
                    existing.append(row)
                    added += 1
                if i % 200 == 0:
                    print(f"  {i}/{len(jobs)} verzoeken, {seen_ads:,} advertenties, "
                          f"{added} nieuwe verkopers", flush=True)

    _save(SELLERS, existing)
    print(f"\n{seen_ads:,} advertenties bekeken → {added} nieuwe zakelijke verkopers "
          f"({len(existing)} totaal) → {SELLERS}")
    for row in existing[-12:]:
        print(f"  {row['name'][:34]:36s} {row['source']}")


# ------------------------------------------------------------------ enrich


def _plaatsnaam(ruw: str) -> str:
    """Plaatsnamen zijn hooguit drie woorden ("Wijk bij Duurstede"); wat daarna
    komt is opmaak van de pagina. Losse letters zijn een afgekapt volgend woord."""
    woorden = [w for w in ruw.split() if len(w) > 1 or w.isdigit()]
    return " ".join(woorden[:3]).strip(" -")


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def _profile(client: httpx.Client, sid: int) -> tuple[dict | None, bool]:
    """Bedrijfsprofiel ophalen. Geeft (gegevens, nog_eens_proberen) terug.

    Het verschil is belangrijk: een pagina die netjes laadt maar geen KvK of
    telefoon toont, gaat dat morgen ook niet doen — die verkoper vult het gewoon
    niet in. Alleen een netwerkfout of een serverfout is het opnieuw proberen waard.
    """
    try:
        r = client.get(PROFILE.format(sid=sid))
    except Exception:  # noqa: BLE001
        return None, True
    if r.status_code != 200:
        return None, r.status_code >= 500
    t = _text(r.text)
    kvk = re.search(r"KVK[- ]?nummer\s*:?\s*(\d{6,10})", t, re.I)
    btw = re.search(r"BTW[- ]?nummer\s*:?\s*([A-Z]{2}[\dA-Z]{9,14})", t, re.I)
    tel = re.search(r"(\+31\s?\d[\d\s\-]{7,12})", t)
    mail = re.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", t)
    # Achter de plaatsnaam komt op de profielpagina meteen de openingstijden, en
    # een gulzige regex maakte daar "Rotterdam Vandaag open van" van.
    plaats = re.search(r"(\d{4}\s?[A-Z]{2})\s+([A-Za-zÀ-ſ'\- ]{2,30}?)"
                       r"(?=\s+(?:Vandaag|Maandag|Dinsdag|Woensdag|Donderdag|Vrijdag|"
                       r"Zaterdag|Zondag|Bekijk|Bedrijfsinformatie|Contactgegevens|"
                       r"Vertel|Gesloten|Open|De verkoper|Deze verkoper)|\s*$)", t)
    if not (kvk or btw or tel):
        return None, False
    over = ""
    m = re.search(r"Over ons\s+Alle advertenties\s+Over ons\s+(.*?)"
                  r"(?:Vertel anderen|Contactgegevens|Bedrijfsinformatie)", t)
    if m:
        over = m.group(1).strip()[:900]
    naam = re.search(r"Handelsnaam\s+(.+?)\s+(?:BTW|KVK)", t)
    return {
        "kvk": kvk and kvk.group(1),
        "btw": btw and btw.group(1),
        "tel": tel and tel.group(1).strip(),
        "email": mail and mail.group(0).lower(),
        "handelsnaam": naam and naam.group(1).strip(),
        "postcode": plaats and plaats.group(1),
        "plaats": plaats and _plaatsnaam(plaats.group(2)),
        "over_ons": over,
    }, False


JUNK_MAIL = re.compile(r"\.(png|jpe?g|webp|gif|svg)$|^[a-f0-9]{16,}@|sentry|example\.",
                       re.I)
CONTACT_PATHS = ("", "/contact", "/contact/", "/pages/contact", "/contact-us",
                 "/over-ons", "/algemene-voorwaarden")
FREE_MAIL = {"gmail.com", "hotmail.com", "hotmail.nl", "outlook.com", "outlook.nl",
             "live.nl", "ziggo.nl", "kpnmail.nl", "home.nl", "telfort.nl",
             "yahoo.com", "icloud.com", "planet.nl", "xs4all.nl", "upcmail.nl"}


def _site_email(client: httpx.Client, link: str) -> tuple[str, str]:
    """(e-mailadres, domein) van de eigen webshop.

    Ruim de helft van de zakelijke verkopers vult in het Marktplaats-profiel geen
    e-mailadres in, maar heeft wel een webshop met een contactpagina. Live getest:
    verkopers zonder adres in hun profiel leverden alsnog info@... op hun eigen site.
    """
    if not link:
        return "", ""
    try:
        r = client.get(link, timeout=15.0)
    except Exception:  # noqa: BLE001
        return "", ""
    base = str(r.url).split("/")
    if len(base) < 3:
        return "", ""
    domain = f"{base[0]}//{base[2]}"
    for path in CONTACT_PATHS:
        try:
            page = r if path == "" else client.get(domain + path, timeout=15.0)
            if page.status_code != 200:
                continue
        except Exception:  # noqa: BLE001
            continue
        found = [e.lower() for e in
                 re.findall(r"[\w.+-]+@[\w.-]+\.\w{2,}", page.text)
                 if not JUNK_MAIL.search(e)]
        if found:
            # Een adres op het eigen domein is van de verkoper. Een vreemd adres
            # in de broncode is dat meestal niet: de eerste versie stuurde
            # "donate@opencart.com" mee als contactadres van een kledinghandelaar.
            # Alleen een gewone provider (gmail, ziggo) is nog geloofwaardig.
            host = domain.split("//")[-1].replace("www.", "")
            own = [e for e in found if host in e]
            if own:
                return own[0], domain
            vrij = [e for e in found if e.split("@")[-1] in FREE_MAIL]
            if vrij:
                return vrij[0], domain
    return "", domain


def _ad_count(client: httpx.Client, sid: int) -> int:
    """Het aantal actieve advertenties is het scherpste koopsignaal dat er is:
    crosslist-pijn schaalt recht evenredig met voorraad."""
    try:
        r = client.get(SELLER_PAGE.format(sid=sid))
        m = re.search(r'"totalResultCount":(\d+)', r.text)
        return int(m.group(1)) if m else 0
    except Exception:  # noqa: BLE001
        return 0


def _enrich_one(client: httpx.Client, row: dict) -> dict:
    prof, retry = _profile(client, row["seller_id"])
    if prof:
        row.update(prof)

    if not row.get("email"):
        mail, domain = _site_email(client, row.get("site_link", ""))
        if domain:
            row["website"] = domain
        if mail:
            row["email"] = mail
            row["email_bron"] = "webshop"
    # De doorklik-link is anderhalve kilobyte per verkoper en heeft na dit moment
    # geen waarde meer; het domein zelf wel.
    row.pop("site_link", None)

    if prof or row.get("email"):
        row["ads"] = _ad_count(client, row["seller_id"])
        row["url"] = PROFILE.format(sid=row["seller_id"])
        row["enriched"] = True
        return row

    if not retry:
        # Profielpagina laadde prima maar bevat geen bedrijfsgegevens, en er is
        # ook geen webshop met een adres. Morgen opnieuw kijken helpt niet.
        row["dead"] = True
        return row
    row["fails"] = row.get("fails", 0) + 1
    if row["fails"] >= MAX_FAILS:
        row["dead"] = True
    return row


def enrich(args) -> None:
    rows = _load(SELLERS)
    if not rows:
        sys.exit("Nog geen mp_sellers.json — draai eerst 'discover'")

    todo = [r for r in rows if not r.get("enriched") and not r.get("dead")]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} verkopers ophalen…")

    with _client() as client:
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(_enrich_one, client, row) for row in todo]
            for future in as_completed(futures):
                future.result()
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(todo)}", flush=True)

    _save(SELLERS, rows)
    ok = [r for r in rows if r.get("enriched")]
    met_mail = [r for r in ok if r.get("email")]
    dood = [r for r in rows if r.get("dead")]
    print(f"\n{len(ok)} zakelijke profielen ({len(met_mail)} met e-mailadres, "
          f"{100 * len(met_mail) // max(1, len(ok))}%)")
    print(f"{len(dood)} verkopers bleken toch particulier of onbereikbaar")


# -------------------------------------------------------------- crosslist


# Draait de vraag om die er echt toe doet: verkoopt deze handelaar al op meer dan
# één plek? Zo ja, dan doet hij nu handmatig precies wat Omnivaleur automatiseert.
#
# WAT WEL EN NIET TE METEN VALT (live getest 2026-08-10):
#   eigen webshop  WERKT. Te herleiden uit de doorklik-link van Marktplaats of
#                  anders uit het e-maildomein. Bij 258 van 381 leads te vinden.
#                  Webshop + Marktplaats is per definitie al crosslisten.
#   webshopsysteem WERKT. Shopify, WooCommerce, Lightspeed, Magento en CCVshop zijn
#                  aan hun eigen bestanden te herkennen. Bij tweederde van de
#                  bereikbare sites raak. Shopify is extra interessant: daar heeft
#                  Omnivaleur een koppeling voor.
#   bol.com        WERKT. Zoeken op handelsnaam en de exacte naam terugvinden in
#                  "Verkoop door ...". Ongeveer 1 op de 10 leads.
#   eBay           WERKT NIET. Winkeladressen op eBay zijn niet uit een handelsnaam
#                  af te leiden; 40 pogingen gaven 40 keer een lege winkelpagina.
#   Vinted         WERKT NIET. Cloudflare weigert alles wat geen browser is.
#   2dehands       WERKT NIET. Draait op dezelfde techniek maar heeft eigen
#                  verkoper-nummers; hetzelfde nummer levert daar nul advertenties.
#   Facebook/Instagram-links op de site zijn bewust NIET meegeteld: bijna iedereen
#   heeft die, dus ze zeggen niets over crosslisten.

SHOP_SYSTEMS = {
    "Shopify": r"cdn\.shopify|shopify\.com",
    "WooCommerce": r"woocommerce|wp-content",
    "Lightspeed": r"lightspeed|seoshop",
    "Magento": r"magento",
    "CCVshop": r"ccvshop",
    "Mijnwebwinkel": r"mijnwebwinkel|myonlinestore",
}
BOL_SEARCH = "https://www.bol.com/nl/nl/s/"
# Een doorklik-link die niet doorklikt blijft op Marktplaats staan. Dat als "eigen
# website" tellen maakt van elke verkoper een crosslister.
NIET_EIGEN = ("marktplaats.nl", "2dehands.be", "2ememain.be", "admarkt.")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _site_of(row: dict) -> str:
    """De eigen webshop. Staat er geen domein bij, dan is het e-maildomein het
    volgende beste bewijs — info@camera-point.nl betekent camera-point.nl."""
    if row.get("website") and not any(x in row["website"] for x in NIET_EIGEN):
        return row["website"]
    domain = (row.get("email") or "").split("@")[-1].lower()
    if domain and "." in domain and domain not in FREE_MAIL:
        return f"https://{domain}"
    return ""


def _on_bol(client: httpx.Client, naam: str) -> bool:
    """Een zoekopdracht op bol geeft ALTIJD verkopers terug, ook bij onzin. Alleen
    een exacte naammatch in "Verkoop door ..." telt daarom als bewijs."""
    if len(_norm(naam)) < 4:
        return False
    try:
        html = client.get(BOL_SEARCH, params={"searchtext": naam}).text
    except Exception:  # noqa: BLE001
        return False
    return any(_norm(h) == _norm(naam)
               for h in re.findall(r"Verkoop door ([^<\"]{2,40})", html))


def _crosslist_one(client: httpx.Client, row: dict) -> dict:
    site = _site_of(row)
    kanalen = ["Marktplaats"]
    row["shopsysteem"] = ""

    if site:
        html = ""
        for path in ("", "/contact"):
            try:
                r = client.get(site + path, timeout=15.0)
                if r.status_code == 200:
                    html += r.text
            except Exception:  # noqa: BLE001
                pass
        if html and not any(x in site for x in NIET_EIGEN):
            row["site"] = site
            kanalen.append("Eigen website")
            row["shopsysteem"] = ", ".join(
                naam for naam, rx in SHOP_SYSTEMS.items() if re.search(rx, html, re.I))

    if _on_bol(client, row.get("handelsnaam") or row.get("name") or ""):
        kanalen.append("bol.com")

    row["kanalen"] = kanalen
    row["crosslist"] = len(kanalen) > 1
    row["crosslist_gecheckt"] = True
    return row


def crosslist(args) -> None:
    rows = _load(SELLERS)
    todo = [r for r in rows if r.get("enriched") and not r.get("crosslist_gecheckt")]
    if args.min_ads:
        todo = [r for r in todo if (r.get("ads") or 0) >= args.min_ads]
    if not todo:
        print("Alle verkopers zijn al gecontroleerd.")
    else:
        print(f"{len(todo)} verkopers controleren op meerdere verkoopkanalen…")
        with _client() as client:
            done = 0
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(_crosslist_one, client, r) for r in todo]
                for future in as_completed(futures):
                    future.result()
                    done += 1
                    if done % 100 == 0:
                        print(f"  {done}/{len(todo)}", flush=True)
        _save(SELLERS, rows)

    checked = [r for r in rows if r.get("crosslist_gecheckt")]
    cross = [r for r in checked if r.get("crosslist")]
    shop = [r for r in checked if r.get("shopsysteem")]
    print(f"\n{len(cross)} van {len(checked)} verkopen op meer dan één kanaal "
          f"({100 * len(cross) // max(1, len(checked))}%)")
    print(f"{len(shop)} hebben een herkenbaar webshopsysteem: " + ", ".join(
        f"{naam} {sum(1 for r in shop if naam in r['shopsysteem'])}"
        for naam in SHOP_SYSTEMS))
    print(f"{sum(1 for r in checked if 'bol.com' in (r.get('kanalen') or []))} "
          f"verkopen ook op bol.com")


# ------------------------------------------------------- wat wij kunnen plaatsen


# EEN LEAD DIE VERKOOPT WAT WIJ NIET KUNNEN PUBLICEREN, IS GEEN LEAD.
#
# Dat klinkt vanzelfsprekend, maar het ging tot 27-08-2026 mis. De prompt hieronder
# noemde vroeger uit het hoofd "boeken, verzamelobjecten, computers" als goede
# handel. Voor geen van die drie bestaat een categorie in het dashboard, dus die
# leads kregen een mail, reageerden enthousiast, en kregen daarna te horen dat het
# niet kan. Twee van die gesprekken op één dag (Borstelbeer: refurbished elektrische
# tandenborstels; Vianen Telecom: telefoonaccessoires) waren vooraf te voorkomen.
#
# Daarom leest dit blok de categoriekeuze uit frontend/app.html: exact hetzelfde
# lijstje dat een klant in zijn dashboard ziet. Kan een verkoper daar niets kiezen,
# dan loopt publiceren stuk op CategoryUnresolvedError en heeft benaderen geen zin.
#
# Bewust NIET een eigen kopie van de lijst hier: die loopt binnen een maand uit de
# pas met de echte, en dan filtert dit precies verkeerd om.

APP_HTML = Path(__file__).resolve().parents[1] / "frontend" / "app.html"

# Hoe de groepsnamen uit de code in gewoon Nederlands heten. Alleen voor de prompt
# en de rapportage; de sleutel links is wat telt.
GROEP_NAMEN = {
    "dames": "dameskleding en -schoenen",
    "heren": "herenkleding en -schoenen",
    "kinderen": "kinder- en babykleding",
    "unisex": "unisex kleding",
    "sieraden": "sieraden, horloges en tassen",
    "games": "games en consoles",
    "electronics": "telefoons",
    "antiek": "antiek en curiosa",
    "kunst": "kunst",
    "muziek": "muziekinstrumenten en apparatuur",
    "wonen": "wonen, tuin en interieur",
}


@lru_cache(maxsize=1)
def _publiceerbare_groepen() -> dict[str, list[str]]:
    """De categoriekeuze uit het dashboard, per groep, in het Nederlands.

    Gooit een fout als het bestand niet te lezen valt. Bewust hard: een leeg
    resultaat zou elke lead afkeuren en een "alles mag"-terugval zou het filter
    stilzwijgend uitzetten. Allebei erger dan een run die stopt met een melding.
    """
    src = APP_HTML.read_text(encoding="utf-8")
    start = src.index("const CATEGORIES = {")
    blok = src[start:src.index("\n};", start)]

    groepen: dict[str, list[str]] = {}
    huidig = None
    for regel in blok.splitlines():
        kop = re.match(r"\s*([a-z]+):\s*\[", regel)
        if kop:
            huidig = kop.group(1)
            groepen[huidig] = []
        if huidig:
            for sleutel in re.findall(r'\["([^"]+)"\s*,\s*"[^"]*"\]', regel):
                # "wonen tuinstoelen" → "tuinstoelen"; kledingsleutels hebben geen
                # voorvoegsel en blijven zoals ze zijn.
                woorden = sleutel.split()
                kaal = " ".join(woorden[1:]) if woorden[0] == huidig else sleutel
                if kaal:
                    groepen[huidig].append(kaal)

    groepen = {g: k for g, k in groepen.items() if k}
    if len(groepen) < 8:
        raise RuntimeError(
            f"Kon de categoriekeuze niet uit {APP_HTML.name} lezen "
            f"(gevonden: {sorted(groepen)}). Zonder die lijst mag dit script niet "
            f"beoordelen, want dan filtert het willekeurig.")
    return groepen


@lru_cache(maxsize=1)
def _groepen_tekst() -> str:
    """De lijst zoals het model hem te zien krijgt: volledig, geen samenvatting.

    Volledig omdat het verschil juist in de staart zit. "elektronica" klinkt als
    een prima lead tot je ziet dat de hele tak uit tien telefoonmerken bestaat.
    """
    regels = []
    for groep, sleutels in _publiceerbare_groepen().items():
        naam = GROEP_NAMEN.get(groep, groep)
        regels.append(f"  {groep} ({naam}): " + ", ".join(sorted(set(sleutels))))
    return "\n".join(regels)


# ---------------------------------------------------------------- classify


PROMPT = """Je beoordeelt of een Marktplaats-verkoper een goede lead is voor
Omnivaleur, een tool waarmee verkopers hun advertenties in één keer op Marktplaats,
2dehands, Vinted, eBay en Shopify zetten. De waarde zit in MEER en SNELLER verkopen,
en die waarde is het grootst bij iemand met veel voorraad die nu alles handmatig op
elke site apart moet zetten.

Een goede lead moet aan ALLE DRIE voldoen:
 1. ZIJN HANDEL PAST IN ONZE CATEGORIEBOOM. Dit is de belangrijkste toets en de
    enige die hard is. Omnivaleur kan een advertentie ALLEEN aanmaken binnen de
    lijst hieronder; alles daarbuiten loopt vast en die verkoper kunnen we niet
    helpen. Lees de lijst letterlijk en vul niet aan uit je eigen kennis. Drie
    plekken waar het steeds misgaat:
      - de tak "electronics" bestaat UITSLUITEND uit telefoons. Geen hoesjes,
        opladers, oordopjes, computers, laptops, camera's, tv of audio.
      - boeken, gereedschap, speelgoed, servies en tv/audio staan er alléén in de
        tak "antiek", en dus alleen als het echt antiek of vintage is. Dezelfde
        spullen modern en nieuw passen niet.
      - helemaal afwezig: persoonlijke verzorging, witgoed en huishoudelijke
        apparaten, auto- en fietsonderdelen, bouwmateriaal en dierbenodigdheden.

{groepen}

 2. VOORRAAD EN WINSTMOTIEF — een handelaar, niet iemand die één keer zijn zolder
    opruimt. Meerdere advertenties, een handelsnaam, een winkel of webshop.
 3. NL/BE — Nederlandstalig bedrijf.

Wijs af (is_lead = false):
 * Verhuur, opslag, garageboxen, vakantiehuizen, diensten, cursussen, advies.
 * Auto's, motoren, aanhangers, caravans, machines, bouwmaterialen.
 * Meubel-, keuken-, interieur- en brocantehandel: onverzendbaar.
 * Marktplaats-partners en veilinghuizen (Catawiki en dergelijke).
 * Grote ketens en fabrikanten die uitsluitend nieuwe eigen producten verkopen.
 * Kringloopwinkels en goede doelen: geen winstmotief, verzenden meestal niet.
 * Webshops die NIEUWE producten in maten/kleuren met voorraad per variant
   verkopen — een normaal retail-assortiment dus. Bij ons is één artikel één
   stuk met één prijs; varianten bestaan niet en een voorraadaantal ook niet.
   Let op het verschil: een handelaar met tien losse tweedehands jassen is een
   prima lead, een webshop met één jas in vijf maten en drie kleuren niet.

De ideale lead is de handelaar in tweedehands of restpartijen: iemand met tientallen
losse advertenties in kleding, sneakers, sieraden, games of telefoons die ook op
Vinted of eBay zouden kunnen staan maar daar nu de tijd niet voor heeft.

Verkoper:
  {naam} (handelsnaam: {handelsnaam})
  actieve advertenties op Marktplaats: {ads}
  gevonden in rubriek: {source}
  plaats: {plaats}
  e-mail: {email} · telefoon: {tel} · KvK: {kvk}
  verkoopkanalen: {kanalen} · webshopsysteem: {shopsysteem}
  over ons: {over_ons}

Antwoord met UITSLUITEND JSON:
{{"is_lead": true/false,
  "confidence": 0-100,
  "verkopertype": "handelaar|webshop|winkel|verhuur|diensten|voertuigen|meubels|kringloop|fabrikant|particulier|onduidelijk",
  "verzendbaar": true/false,
  "commercieel": true/false,
  "reden": "één zin, Nederlands",
  "categorie_fit": "één groepsnaam uit de lijst bij punt 1 waar zijn handel echt in valt: dames, heren, kinderen, unisex, sieraden, games, electronics, antiek, muziek of wonen. Past niets, antwoord dan met het woord geen",
  "categorie_fit_reden": "welke van zijn artikelen je in die groep plaatst, of waarom niets past — één korte zin",
  "retail_varianten": true/false,
  "verkoopt_vooral": "Kleding|Meubilair|Alles|Antieke vintage|Hoogwaardige vintage|Vintage interieur|Sieraden|Knutselmaterialen",
  "verkoop_op": "Marktplaats|Eigen website|Fysieke winkel|Onbekend",
  "je_jullie": "Je|Jullie",
  "language": "NL|EN"}}"""

# Elk oordeel draagt de versie van de prompt die het velde. Gaat die omhoog, dan
# worden bestaande oordelen weggegooid en opnieuw gevraagd. Zonder dat verandert
# een strenger filter niets aan de stapel waar Daniel uit mailt — en dat is juist
# de stapel waar het misging. Verhoog dit dus bij elke inhoudelijke promptwijziging.
#   2  categoriefilter + variantenfilter (27-08-2026)
PROMPT_VERSIE = 2


# "veilinghuis" staat niet in de lijst die de prompt aanbiedt, maar het model
# verzint hem toch voor Catawiki-achtigen. Onbekende typen wegfilteren kan niet —
# "onduidelijk" is soms een prima lead — dus deze er met naam bij.
REJECT_TYPES = {"verhuur", "diensten", "voertuigen", "meubels", "kringloop",
                "fabrikant", "particulier", "veilinghuis", "veiling"}


def _fill(row: dict) -> str:
    return PROMPT.format(
        naam=row.get("name") or "(leeg)",
        handelsnaam=row.get("handelsnaam") or "(onbekend)",
        ads=row.get("ads") or row.get("ads_seen") or 0,
        source=row.get("source") or "(onbekend)",
        plaats=row.get("plaats") or "(onbekend)",
        email=row.get("email") or "(geen)",
        tel=row.get("tel") or "(geen)",
        kvk=row.get("kvk") or "(geen)",
        kanalen=", ".join(row.get("kanalen") or ["Marktplaats"]),
        shopsysteem=row.get("shopsysteem") or "(geen gevonden)",
        over_ons=row.get("over_ons") or "(leeg)",
        groepen=_groepen_tekst(),
    )


def _afwijsreden(verdict: dict, min_confidence: int) -> str:
    """Lege string = houden. Anders in één woord waaróm hij afvalt.

    Als reden teruggeven en niet als kale boolean, want zonder die reden is een
    run van 800 verkopers waar er 40 van overblijven niet te controleren — en
    juist een filter dat te streng staat merk je anders pas weken later.
    """
    vtype = (verdict.get("verkopertype") or "onduidelijk").lower()
    if not verdict.get("is_lead"):
        return "geen lead"
    if verdict.get("confidence", 0) < min_confidence:
        return "twijfel"
    if vtype in REJECT_TYPES:
        return vtype
    if verdict.get("verzendbaar") is False:
        return "onverzendbaar"
    if verdict.get("commercieel") is False:
        return "particulier"
    # De twee toetsen die op 27-08-2026 zijn toegevoegd. Zie het blok
    # "wat wij kunnen plaatsen" hierboven voor waarom.
    fit = str(verdict.get("categorie_fit") or "").strip().lower()
    if fit not in _publiceerbare_groepen():
        return "geen categorie"
    if verdict.get("retail_varianten") is True:
        return "varianten"
    return ""


def _keep(verdict: dict, min_confidence: int) -> bool:
    return not _afwijsreden(verdict, min_confidence)


def classify(args) -> None:
    everything = _load(SELLERS)
    rows = [r for r in everything if r.get("enriched")]
    if args.min_ads:
        rows = [r for r in rows if (r.get("ads") or 0) >= args.min_ads]
    if args.only_email:
        rows = [r for r in rows if r.get("email")]
    if not rows:
        sys.exit("Nog geen verrijkte verkopers — draai eerst 'enrich'")

    verlopen = [r for r in rows
                if r.get("verdict")
                and r["verdict"].get("prompt_versie") != PROMPT_VERSIE]
    for r in verlopen:
        r.pop("verdict", None)
    if verlopen:
        print(f"{len(verlopen)} eerdere oordelen zijn met een oudere prompt geveld "
              f"— die vraag ik opnieuw")

    print(f"{len(rows)} verkopers beoordelen "
          f"(vanaf {args.min_ads} advertenties"
          f"{', alleen met e-mail' if args.only_email else ''})")
    # Dezelfde beoordelaar als de Instagram-trechter, met een eigen prompt: het
    # cachen, het parallel draaien en de drie-assen-toets zijn identiek en hoeven
    # niet twee keer te bestaan.
    leads = ig._classify_rows(
        rows, args.min_confidence, fill=_fill, keep=_keep, label="name",
        carry=("seller_id", "name", "handelsnaam", "method", "source", "ads",
               "email", "tel", "kvk", "plaats", "website", "site", "kanalen",
               "shopsysteem", "crosslist"),
        url=lambda r: r.get("url") or PROFILE.format(sid=r["seller_id"]))
    for row in rows:
        if row.get("verdict"):
            row["verdict"]["prompt_versie"] = PROMPT_VERSIE

    for lead in leads:
        lead["platform"] = "MP"
        lead["full_name"] = lead.get("handelsnaam") or lead.get("name")
        # Niet aan het model gevraagd maar gemeten: van de webshopsystemen die we
        # herkennen koppelt alleen Shopify. Staat dit op False, dan mag de mail
        # geen webshopkoppeling beloven — dat was precies de belofte die bij
        # WooCommerce-leads teruggedraaid moest worden.
        systeem = lead.get("shopsysteem") or ""
        lead["webshop_koppelbaar"] = (not systeem) or ("Shopify" in systeem)

    _save(SELLERS, everything)
    _save(MP_LEADS, leads)
    print(f"\n{len(leads)} van {len(rows)} verkopers gekwalificeerd → {MP_LEADS}")

    # Waarom de rest afviel. Een filter dat je niet kunt nalezen, staat vroeg of
    # laat te streng zonder dat iemand het merkt.
    afgevallen: dict[str, int] = {}
    for row in rows:
        verdict = row.get("verdict")
        if not verdict:
            continue
        reden = _afwijsreden(verdict, args.min_confidence)
        if reden:
            afgevallen[reden] = afgevallen.get(reden, 0) + 1
    if afgevallen:
        print("afgevallen: " + ", ".join(
            f"{reden} {aantal}" for reden, aantal
            in sorted(afgevallen.items(), key=lambda x: -x[1])))
    niet_koppelbaar = [l for l in leads if not l.get("webshop_koppelbaar")]
    if niet_koppelbaar:
        print(f"let op: {len(niet_koppelbaar)} leads hebben een webshop die wij niet "
              f"koppelen (geen Shopify) — beloof ze geen webshopkoppeling")


# -------------------------------------------------------------------- push


def push(args) -> None:
    leads = _load(MP_LEADS)
    if not leads:
        sys.exit("Nog geen mp_leads.json — draai eerst 'classify'")
    met_mail = [l for l in leads if l.get("email")]

    if args.dry_run:
        print(f"{len(leads)} leads klaar, {len(met_mail)} met e-mailadres "
              f"(dry-run, er wordt niets weggeschreven):\n")
        for lead in sorted(leads, key=lambda l: -(l.get("ads") or 0))[:40]:
            print(f"  {(lead.get('handelsnaam') or lead['name'])[:32]:34s} "
                  f"{lead.get('ads') or 0:>5} adv  "
                  f"{lead.get('email') or lead.get('tel') or '-':32s} "
                  f"{lead.get('verkopertype', '')}")
            print(f"     {lead.get('reden', '')}")
        return

    created, skipped = notion.push_leads(leads, ig._need("NOTION_TOKEN"),
                                         update=args.update)
    print(f"\n{created} leads toegevoegd, {skipped} "
          f"{'bijgewerkt' if args.update else 'bestonden al'}.")


def export(args) -> None:
    """CSV voor een mailtool. Elke kolom is er om een zin mee te kunnen schrijven
    die alleen op déze handelaar slaat — een generieke mail is bij koude acquisitie
    het verschil tussen lezen en weggooien."""
    import csv

    leads = [l for l in _load(MP_LEADS) if l.get("email")]
    if not leads:
        sys.exit("Nog geen leads met e-mailadres — draai eerst 'classify'")
    leads.sort(key=lambda l: -(l.get("ads") or 0))

    velden = ["email", "bedrijf", "advertenties", "webshop", "webshopsysteem",
              "verkoopt_op", "verkoopt", "plaats", "telefoon", "kvk",
              "marktplaats_profiel", "rubriek", "aanhef", "reden"]
    doel = OUT / "mp_export.csv"
    with doel.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=velden)
        w.writeheader()
        for l in leads:
            w.writerow({
                "email": l["email"],
                "bedrijf": l.get("handelsnaam") or l.get("name") or "",
                "advertenties": l.get("ads") or "",
                "webshop": l.get("site") or "",
                "webshopsysteem": l.get("shopsysteem") or "",
                "verkoopt_op": ", ".join(l.get("kanalen") or ["Marktplaats"]),
                "verkoopt": l.get("verkoopt_vooral") or "",
                "plaats": l.get("plaats") or "",
                "telefoon": l.get("tel") or "",
                "kvk": l.get("kvk") or "",
                "marktplaats_profiel": l.get("ig_url") or "",
                "rubriek": l.get("source") or "",
                "aanhef": l.get("je_jullie") or "Je",
                "reden": l.get("reden") or "",
            })
    print(f"{len(leads)} leads → {doel}")
    print(f"  met webshop: {sum(1 for l in leads if l.get('site'))}")
    print(f"  met webshopsysteem: {sum(1 for l in leads if l.get('shopsysteem'))}")


def run(args) -> None:
    if not args.dry_run:
        ig._need("NOTION_TOKEN")

    print("── 1/5 zoeken ─────────────────────────────────────────────")
    discover(args)
    print("\n── 2/5 bedrijfsprofielen ──────────────────────────────────")
    enrich(args)
    print("\n── 3/5 verkoopkanalen ─────────────────────────────────────")
    crosslist(args)
    print("\n── 4/5 beoordelen ─────────────────────────────────────────")
    classify(args)
    print("\n── 5/5 naar Notion ────────────────────────────────────────")
    push(args)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, *, disc=False, enr=False, cls=False, psh=False):
        if disc:
            p.add_argument("--categories", nargs="*", choices=list(CATEGORIES),
                           help="alleen deze rubrieken")
            p.add_argument("--depth", type=int, default=2000,
                           help="advertenties per subcategorie (max 5000)")
        if enr:
            p.add_argument("--limit", type=int, default=0)
        if cls:
            p.add_argument("--min-confidence", type=int, default=60)
            # 20 advertenties is de ondergrens waaronder crosslisten geen probleem
            # is: met vijf advertenties zet je ze desnoods met de hand over. Op 3
            # kwamen er buurtwinkels en eenmansacties binnen die niets aan de tool
            # hebben. Verlaag dit alleen als de lijst opdroogt.
            p.add_argument("--min-ads", type=int, default=20,
                           help="verkopers met minder advertenties overslaan")
            p.add_argument("--only-email", action="store_true",
                           help="alleen verkopers met een e-mailadres beoordelen")
        if psh:
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--update", action="store_true",
                           help="bestaande rijen bijwerken in plaats van overslaan")
        p.add_argument("--workers", type=int, default=8)

    d = sub.add_parser("discover", help="zakelijke verkopers uit de rubrieken halen")
    common(d, disc=True)
    d.set_defaults(func=discover)

    e = sub.add_parser("enrich", help="bedrijfsprofiel: KvK, telefoon, e-mail")
    common(e, enr=True)
    e.set_defaults(func=enrich)

    x = sub.add_parser("crosslist",
                       help="checkt eigen webshop, webshopsysteem en bol.com")
    common(x, cls=True)
    x.set_defaults(func=crosslist)

    c = sub.add_parser("classify", help="Haiku beoordeelt handelaar vs de rest")
    common(c, cls=True)
    c.set_defaults(func=classify)

    p = sub.add_parser("push", help="naar de Notion-Leadlist")
    common(p, psh=True)
    p.set_defaults(func=push)

    ex = sub.add_parser("export", help="CSV voor je mailtool")
    common(ex)
    ex.set_defaults(func=export)

    r = sub.add_parser("run", help="ALLES in één keer")
    common(r, disc=True, enr=True, cls=True, psh=True)
    r.set_defaults(func=run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
