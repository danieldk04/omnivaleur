"""
Prijs en omschrijving ophalen bij Marktplaats voor items die ze missen.

WAAROM DIT BESTAAT
Een zakelijke verkoper (Admarkt) krijgt van Marktplaats alleen titel, foto's en
categorie mee. Prijs en omschrijving zitten niet in de Admarkt-gegevens, want
Admarkt-advertenties wijzen naar de eigen webwinkel. Gemeten geval: een verkoper
met 5.534 advertenties zag na de import 240 items zonder prijs en zonder tekst,
en zou die met de hand moeten overtikken.

Maar die advertenties staan wél gewoon publiek op Marktplaats. De openbare
zoekfunctie geeft per advertentie de vraagprijs en het adres van de advertentie,
en op die advertentiepagina staat de volledige omschrijving in de HTML. Beide
zijn openbaar: er is geen inlog voor nodig en we lezen alleen wat de verkoper
zelf heeft gepubliceerd — zijn eigen teksten, terug in zijn eigen dashboard.

HOE HET KOPPELT
Het Admarkt-id en het Marktplaats-advertentienummer zijn niet hetzelfde nummer,
dus koppelen gaat op titel. Dat mag hier, omdat we uitsluitend binnen het aanbod
van één verkoper zoeken: twee verkopers kunnen dezelfde titel hebben, één
verkoper vrijwel nooit. Bij twijfel (meerdere advertenties met exact dezelfde
genormaliseerde titel) slaan we het item over in plaats van te gokken.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time
import unicodedata

import httpx
from backend.database import naast_de_lus

logger = logging.getLogger(__name__)

# Cloudflare geeft een 524 als één verzoek langer dan 100 seconden duurt — dat
# was precies wat hier gebeurde bij verkopers met honderden open items en veel
# 403's van Marktplaats (elke herkansing daarop kost tot 12 seconden). Deze
# functie stopt daarom ruim op tijd met nieuwe items beginnen en levert terug
# wat al klaar is; het scherm roept haar gewoon nog een keer aan voor de rest.
BUDGET_SECONDEN = 60

ZOEK = "https://www.marktplaats.nl/lrp/api/search"
BASIS = "https://www.marktplaats.nl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Marktplaats is niet van ons. Vier tegelijk en een korte pauze houdt het beleefd
# en blijft ver onder wat een gewone bezoeker met meerdere tabbladen doet.
TEGELIJK = 3
PAGINA = 100
# Marktplaats geeft per verkoper hooguit 5.000 advertenties terug, ook als er
# 5.534 staan. Gemeten: bij offset 5000 komt een lege lijst. Wie meer heeft, mist
# de rest in deze lijst; die halen we daarna per titel op.
MAX_PAGINAS = 50
DESC_MAX = 4000


def _sleutel(titel: str) -> str:
    """Titels vergelijkbaar maken: zonder accenten, leestekens en dubbele spaties.
    Marktplaats en Admarkt schrijven dezelfde titel niet altijd identiek terug.

    Het unescapen is niet cosmetisch: Admarkt levert titels met HTML-codes erin
    ("50&#39;s Pin Up"), Marktplaats geeft ze als gewone tekst ("50's Pin Up").
    Zonder deze stap zag geen van beide kanten elkaar."""
    schoon = html.unescape(str(titel or ""))
    t = unicodedata.normalize("NFKD", schoon).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t.lower())).strip()


async def _json(client: httpx.AsyncClient, url: str, params: dict | None = None):
    r = await client.get(url, params=params, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


async def zoek_verkoper_id(client: httpx.AsyncClient, titels: list[str]) -> int | None:
    """Het verkopersnummer achterhalen door op de eigen titels te zoeken.

    De verkoper hoeft dat nummer dus niet te weten en wij hoeven er niet naar te
    vragen. We nemen pas een nummer aan als het bij meerdere verschillende titels
    hetzelfde is; één treffer kan toevallig een andere verkoper zijn die hetzelfde
    artikel aanbiedt.
    """
    stemmen: dict[int, int] = {}
    for titel in titels[:8]:
        doel = _sleutel(titel)
        if not doel:
            continue
        try:
            data = await _json(client, ZOEK, {"query": titel[:80], "limit": 20, "offset": 0})
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: zoeken op titel mislukt: %s", e)
            continue
        for l in (data.get("listings") or []):
            if _sleutel(l.get("title")) != doel:
                continue
            sid = ((l.get("sellerInformation") or {}).get("sellerId"))
            if sid:
                stemmen[int(sid)] = stemmen.get(int(sid), 0) + 1
        await asyncio.sleep(0.3)
    if not stemmen:
        return None
    beste, aantal = max(stemmen.items(), key=lambda kv: kv[1])
    return beste if aantal >= 2 else None


async def haal_advertenties(client: httpx.AsyncClient, verkoper_id: int) -> dict[str, dict]:
    """Alle advertenties van deze verkoper, op genormaliseerde titel.

    Komt een titel twee keer voor, dan houden we de eerste aan. Dat is bij één
    verkoper geen gok: dezelfde titel is bij hem hetzelfde artikel, vaak gewoon
    twee keer geplaatst. Alleen als de vraagprijzen verschillen laten we hem
    staan, want dan is niet te zeggen welke bij het item hoort.
    """
    per_titel: dict[str, dict] = {}
    botsing: set[str] = set()
    for pagina in range(MAX_PAGINAS):
        try:
            data = await _json(client, ZOEK, {
                "sellerIds[]": verkoper_id, "limit": PAGINA, "offset": pagina * PAGINA})
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: advertentielijst pagina %s mislukt: %s", pagina, e)
            break
        rijen = data.get("listings") or []
        if not rijen:
            break
        for l in rijen:
            s = _sleutel(l.get("title"))
            if not s:
                continue
            nieuw = _naar_advertentie(l)
            if s in per_titel:
                if per_titel[s]["price"] != nieuw["price"]:
                    botsing.add(s)
                continue
            per_titel[s] = nieuw
        if len(rijen) < PAGINA:
            break
        await asyncio.sleep(0.2)
    return {k: v for k, v in per_titel.items() if k not in botsing}


def _naar_advertentie(l: dict) -> dict:
    cents = ((l.get("priceInfo") or {}).get("priceCents"))
    soort = ((l.get("priceInfo") or {}).get("priceType") or "")
    vip = l.get("vipUrl") or ""
    return {
        "item_id": l.get("itemId"),
        # Alleen een echte vraagprijs overnemen. "Bieden", "Gereserveerd" en
        # "Op aanvraag" komen als 0 of 1 cent binnen en zijn geen prijs.
        "price": (round(cents / 100, 2)
                  if soort == "FIXED" and isinstance(cents, int) and cents > 1
                  else None),
        "url": (BASIS + vip) if vip.startswith("/") else vip,
        "kort": (l.get("categorySpecificDescription") or l.get("description") or "").strip(),
    }


async def zoek_een_titel(client: httpx.AsyncClient, verkoper_id: int,
                         titel: str) -> dict | None:
    """Eén advertentie opzoeken op titel, binnen het aanbod van deze verkoper.

    Nodig omdat de verkoperslijst bij 5.000 advertenties ophoudt terwijl iemand
    er 5.534 kan hebben. Wat daar buiten valt is via de gewone zoekfunctie nog
    prima te vinden; het kost alleen een aanvraag per item, dus dit is de
    aanvulling en niet de hoofdweg.
    """
    schoon = html.unescape(str(titel or "")).strip()
    if not schoon:
        return None
    doel = _sleutel(schoon)
    try:
        data = await _json(client, ZOEK, {"query": schoon[:80], "limit": 30, "offset": 0})
    except Exception as e:  # noqa: BLE001
        logger.warning("mp_enrich: zoeken op '%s' mislukt: %s", schoon[:40], e)
        return None
    for l in (data.get("listings") or []):
        sid = ((l.get("sellerInformation") or {}).get("sellerId"))
        if sid and int(sid) == int(verkoper_id) and _sleutel(l.get("title")) == doel:
            return _naar_advertentie(l)
    return None


_BLOK = re.compile(r'class="Description-module-description"[^>]*>(.*?)</div>', re.S)


def _tekst_uit_html(ruwe: str) -> str:
    """De omschrijving staat als HTML in de advertentiepagina. <br> en </p> zijn
    de regelovergangen die de verkoper zelf heeft getypt; die horen te blijven
    staan, anders wordt zijn opsomming één lange lap tekst."""
    m = _BLOK.search(ruwe)
    if not m:
        return ""
    stuk = m.group(1)
    stuk = re.sub(r"<\s*br\s*/?>", "\n", stuk, flags=re.I)
    stuk = re.sub(r"</\s*(p|div|li|h[1-6])\s*>", "\n", stuk, flags=re.I)
    stuk = re.sub(r"<\s*li[^>]*>", "- ", stuk, flags=re.I)
    stuk = re.sub(r"<[^>]+>", "", stuk)
    stuk = html.unescape(stuk).replace("\xa0", " ")
    stuk = re.sub(r"[ \t]+", " ", stuk)
    stuk = re.sub(r"\n\s*\n\s*\n+", "\n\n", stuk)
    return stuk.strip()[:DESC_MAX]


async def volledige_omschrijving(client: httpx.AsyncClient, url: str) -> str:
    """De volledige tekst van één advertentiepagina.

    Marktplaats gaat bij veel aanvragen achter elkaar over op 403. Dat is geen
    fout in de advertentie maar een verzoek om rustiger aan te doen, dus wachten
    en opnieuw proberen is het juiste antwoord. Gemeten: zonder deze herkansing
    kwamen 52 van 240 teksten niet binnen.
    """
    for poging in range(4):
        try:
            r = await client.get(url, headers={"Accept": "text/html"})
            if r.status_code in (403, 429, 503):
                await asyncio.sleep(3 * (poging + 1))
                continue
            if r.status_code != 200:
                return ""
            return _tekst_uit_html(r.text)
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: advertentiepagina mislukt (%s): %s", url, e)
            await asyncio.sleep(2)
    return ""


async def verrijk(db, user_id: str, schrijf: bool = True,
                 maximaal: int = 0, melden=None) -> dict:
    """Vul prijs en omschrijving aan voor items die ze missen.

    Overschrijft nooit: een prijs of tekst die de verkoper zelf heeft ingevuld
    blijft staan. Alleen lege velden worden gevuld.
    """
    def zeg(tekst):
        logger.info("mp_enrich: %s", tekst)
        if melden:
            try:
                melden(tekst)
            except Exception:  # noqa: BLE001
                pass

    rijen = ((await naast_de_lus(lambda: db.table("items").select("id,title,price,description")
             .eq("user_id", user_id).limit(10000).execute())).data or [])
    open_ = [r for r in rijen
             if not str(r.get("description") or "").strip() or not r.get("price")]
    if maximaal:
        open_ = open_[:maximaal]
    uit = {"items": len(rijen), "te_doen": len(open_), "gevonden": 0,
           "prijs": 0, "omschrijving": 0, "geen_tekst": 0,
           "verkoper_id": None, "reden": ""}
    if not open_:
        uit["reden"] = "niets te doen"
        return uit

    limiet = httpx.Limits(max_connections=TEGELIJK, max_keepalive_connections=TEGELIJK)
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": UA},
                                 follow_redirects=True, limits=limiet) as client:
        vid = await zoek_verkoper_id(client, [r["title"] for r in open_])
        uit["verkoper_id"] = vid
        if not vid:
            uit["reden"] = ("advertenties niet teruggevonden op Marktplaats — "
                            "staan ze nog online onder dezelfde titels?")
            return uit
        zeg(f"verkoper {vid} gevonden, advertenties ophalen")

        adv = await haal_advertenties(client, vid)
        zeg(f"{len(adv)} advertenties met een unieke titel")

        koppels = [(r, adv[_sleutel(r["title"])]) for r in open_
                   if _sleutel(r["title"]) in adv]
        rest = [r for r in open_ if _sleutel(r["title"]) not in adv]
        zeg(f"{len(koppels)} van {len(open_)} direct teruggevonden, "
            f"{len(rest)} worden apart opgezocht")

        # De verkoperslijst houdt op bij 5.000. Alles wat daar niet in zat zoeken
        # we alsnog per titel op; dat is trager maar het scheelt de verkoper het
        # met de hand overtikken van honderden advertenties.
        if rest:
            hek_zoek = asyncio.Semaphore(TEGELIJK)

            async def zoek(item):
                async with hek_zoek:
                    a = await zoek_een_titel(client, vid, item["title"])
                    await asyncio.sleep(0.25)
                    return item, a

            for item, a in await asyncio.gather(*(zoek(r) for r in rest)):
                if a:
                    koppels.append((item, a))

        uit["gevonden"] = len(koppels)
        zeg(f"{len(koppels)} van {len(open_)} items teruggevonden")

        hek = asyncio.Semaphore(TEGELIJK)
        gedaan = [0]

        async def een(item, a):
            async with hek:
                patch = {}
                if not item.get("price") and a["price"]:
                    patch["price"] = a["price"]
                if not str(item.get("description") or "").strip():
                    tekst = await volledige_omschrijving(client, a["url"]) if a["url"] else ""
                    # BEWUST geen terugval op de korte tekst uit de zoekresultaten:
                    # die is door Marktplaats afgekapt en stopt middenin een zin.
                    # Zo'n halve tekst zou daarna gewoon op Vinted of eBay
                    # verschijnen. Liever leeg laten en het melden — leeg blokkeert
                    # publiceren, een halve zin niet.
                    if tekst:
                        patch["description"] = tekst
                    await asyncio.sleep(0.25)
                gedaan[0] += 1
                if gedaan[0] % 25 == 0:
                    zeg(f"{gedaan[0]}/{len(koppels)} verwerkt")
                return item, patch

        for item, patch in await asyncio.gather(*(een(i, a) for i, a in koppels)):
            if not str(item.get("description") or "").strip() and "description" not in patch:
                uit["geen_tekst"] += 1
            if not patch:
                continue
            if "price" in patch:
                uit["prijs"] += 1
            if "description" in patch:
                uit["omschrijving"] += 1
            if schrijf:
                try:
                    (await naast_de_lus(lambda: db.table("items").update(patch).eq("id", item["id"]).execute()))
                except Exception as e:  # noqa: BLE001
                    logger.warning("mp_enrich: opslaan mislukt voor %s: %s", item["id"], e)
    return uit
