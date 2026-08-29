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
from backend.database import naast_de_lus, fetch_all

logger = logging.getLogger(__name__)

# Cloudflare geeft een 524 als één verzoek langer dan 100 seconden duurt — dat
# was precies wat hier gebeurde bij verkopers met honderden open items en veel
# 403's van Marktplaats (elke herkansing daarop kost tot 12 seconden). Deze
# functie stopt daarom ruim op tijd met nieuwe items beginnen en levert terug
# wat al klaar is; het scherm roept haar gewoon nog een keer aan voor de rest.
#
# 60 -> 75 (25-08-2026): sinds haal_advertenties zelf niet meer bijna het hele
# budget opsoupeert (zie die functie), is er ruimte om de resterende marge
# vóór Cloudflare's harde 100s-grens te benutten voor het echte verrijkwerk,
# in plaats van hem ongebruikt te laten liggen.
BUDGET_SECONDEN = 75

ZOEK = "https://www.marktplaats.nl/lrp/api/search"
BASIS = "https://www.marktplaats.nl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Marktplaats is niet van ons. Vier tegelijk en een korte pauze houdt het beleefd
# en blijft ver onder wat een gewone bezoeker met meerdere tabbladen doet.
#
# Gemeten 25-08-2026 tegen Egberts echte, openbare advertenties (150 stuks):
# TEGELIJK=3 -> 30/150 gevuld in 60s. TEGELIJK=5 -> 45/150, geen toename in
# mislukkingen. TEGELIJK=8 brak de boel merkbaar (gevonden viel van 150 naar
# 121, en er werd niets meer gevuld) — Marktplaats reageert dan zichtbaar op
# te veel gelijktijdige aanvragen. 5 is dus het hoogste dat nog veilig bleek.
TEGELIJK = 5
# De verkoperslijst zelf (haal_advertenties) is een generieke zoekvraag, geen
# individuele advertentiepagina — dat is niet dezelfde kwetsbare aanvraag waar
# de 403-bescherming in volledige_omschrijving op reageert. Iets ruimhartiger
# hier is wat het tijdsbudget nog kan redden bij een grote winkel als Egberts.
PAGINA_TEGELIJK = 6
PAGINA = 100
# Marktplaats geeft per verkoper hooguit 5.000 advertenties terug, ook als er
# 5.534 staan. Gemeten: bij offset 5000 komt een lege lijst. Wie meer heeft, mist
# de rest in deze lijst; die halen we daarna per titel op.
MAX_PAGINAS = 50
# Was 4000. Dat sneed de onderkant van elke uitgebreide advertentietekst eraf —
# artikelnummer, winkeluitleg, verzendkosten, tags — en daar kwam de klacht
# "een hele lap tekst ontbreekt" vandaan. Het is onze eigen grens, geen grens
# van Marktplaats: de tekst die we hier binnenhalen STOND daar zelf.
DESC_MAX = 20000


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


# Hoeveel titels we hooguit proberen om het verkopersnummer te vinden. We
# stoppen zodra twee titels hetzelfde nummer aanwijzen, dus in de praktijk zijn
# dit er twee of drie — dit is alleen het plafond voor het rare geval.
#
# WAAROM DIT OMHOOG MOEST (27-08-2026, Egbert Brouwer): dit stond op 8, en die
# 8 titels kwamen uit de items die nog leeg waren. Precies die items bleken
# advertenties waarvan de titel op Marktplaats nét anders staat ("Miniatuur
# Cloud gitaar met gratis standaard" is daar niet terug te vinden). Acht keer
# mis is dan genoeg om de hele ronde af te breken met "we kunnen je
# advertenties niet vinden", terwijl 2.000 andere advertenties van dezelfde
# verkoper wél gewoon vindbaar waren.
MAX_TITELPOGINGEN = 25


async def zoek_verkoper_id(client: httpx.AsyncClient, titels: list[str]) -> int | None:
    """Het verkopersnummer achterhalen door op de eigen titels te zoeken.

    De verkoper hoeft dat nummer dus niet te weten en wij hoeven er niet naar te
    vragen. We nemen pas een nummer aan als het bij meerdere verschillende titels
    hetzelfde is; één treffer kan toevallig een andere verkoper zijn die hetzelfde
    artikel aanbiedt.

    Eén titel die niet terug te vinden is, mag hier NOOIT de doorslag geven: dat
    zegt iets over die ene advertentie, niet over de verkoper.
    """
    stemmen: dict[int, int] = {}
    geprobeerd = 0
    for titel in titels:
        doel = _sleutel(titel)
        if not doel:
            continue
        if geprobeerd >= MAX_TITELPOGINGEN:
            break
        geprobeerd += 1
        try:
            data = await _json(client, ZOEK, {"query": titel[:80], "limit": 20, "offset": 0})
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: zoeken op titel mislukt: %s", e)
            continue
        gezien_deze_ronde: set[int] = set()
        for l in (data.get("listings") or []):
            if _sleutel(l.get("title")) != doel:
                continue
            sid = ((l.get("sellerInformation") or {}).get("sellerId"))
            if sid and int(sid) not in gezien_deze_ronde:
                # Per titel hooguit één stem per verkoper: anders levert één
                # advertentie die twee keer online staat in zijn eentje al de
                # vereiste twee stemmen op.
                gezien_deze_ronde.add(int(sid))
                stemmen[int(sid)] = stemmen.get(int(sid), 0) + 1
        if stemmen and max(stemmen.values()) >= 2:
            break
        await asyncio.sleep(0.3)
    if not stemmen:
        logger.warning("mp_enrich: geen verkopersnummer na %d titels", geprobeerd)
        return None
    beste, aantal = max(stemmen.items(), key=lambda kv: kv[1])
    if aantal >= 2:
        return beste
    logger.warning("mp_enrich: verkopersnummer %s kreeg maar 1 stem na %d titels",
                   beste, geprobeerd)
    return None


async def haal_advertenties(client: httpx.AsyncClient, verkoper_id: int,
                            deadline: float | None = None) -> dict[str, dict]:
    """Alle advertenties van deze verkoper, op genormaliseerde titel.

    Komt een titel twee keer voor, dan houden we de eerste aan. Dat is bij één
    verkoper geen gok: dezelfde titel is bij hem hetzelfde artikel, vaak gewoon
    twee keer geplaatst. Alleen als de vraagprijzen verschillen laten we hem
    staan, want dan is niet te zeggen welke bij het item hoort.

    Egbert Brouwer (25-08-2026): met 5.534 advertenties duurde alleen al het
    NA ELKAAR ophalen van deze lijst gemeten 52,6 seconden — bijna het volledige
    tijdsbudget van deze functie (zie BUDGET_SECONDEN), voordat er ook maar één
    prijs was opgezocht. "Fill from Marktplaats" meldde daardoor "0 prijzen,
    0 omschrijvingen": de matches (`koppels`) werden wel gevonden, maar de tijd
    om ze daadwerkelijk op te zoeken was al op. Pagina's worden nu in kleine
    beleefde groepjes van TEGELIJK gelijktijdig opgehaald in plaats van één
    voor één met een pauze ertussen, zodat er tijd overblijft voor het echte werk.
    """
    per_titel: dict[str, dict] = {}
    botsing: set[str] = set()

    async def _pagina(pagina: int) -> list[dict]:
        try:
            data = await _json(client, ZOEK, {
                "sellerIds[]": verkoper_id, "limit": PAGINA, "offset": pagina * PAGINA})
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: advertentielijst pagina %s mislukt: %s", pagina, e)
            return []
        return data.get("listings") or []

    pagina = 0
    door = True
    while door and pagina < MAX_PAGINAS:
        if deadline is not None and time.monotonic() > deadline:
            break
        groep = list(range(pagina, min(pagina + PAGINA_TEGELIJK, MAX_PAGINAS)))
        resultaten = await asyncio.gather(*(_pagina(p) for p in groep))
        for rijen in resultaten:
            if not rijen:
                door = False
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
                door = False
        pagina += len(groep)
        if door:
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


_KENMERK = re.compile(
    r'Attributes-module-label[^>]*>(.*?)</div>\s*<div[^>]*Attributes-module-value[^>]*>(.*?)</div>',
    re.S | re.I)
_FOTO = re.compile(
    r'(?:https?:)?//images\.(?:marktplaats|2dehands)\.com/api/v1/[a-z0-9\-]+/images/'
    r'([0-9a-f\-]{16,})', re.I)
# De grootste versie die Marktplaats van een foto teruggeeft. Live nagemeten:
# _82 = 6 kB, _83 = 33 kB, _85 = 148 kB, _86 = 288 kB.
FOTO_REGEL = "ecg_mp_eps$_86"


def _kenmerken_uit_html(ruwe: str) -> dict:
    """Het blok "Kenmerken" van een advertentiepagina: merk, maat, kleur, staat.

    Deze staan NIET in de zoeklijst waaruit geïmporteerd wordt — daar zit alleen
    titel, prijs en het omslagplaatje in. Gevolg: elke geïmporteerde advertentie
    kreeg in het dashboard "Vul merk en maat aan voor Marktplaats & 2dehands",
    terwijl de verkoper ze op Marktplaats gewoon had ingevuld. Ze staan hier, op
    de pagina die we tóch al ophalen voor de omschrijving.
    """
    uit = {}
    for label, waarde in _KENMERK.findall(ruwe or ""):
        l = html.unescape(re.sub(r"<[^>]+>", "", label)).strip().lower()
        w = html.unescape(re.sub(r"<[^>]+>", "", waarde)).strip()
        if l and w:
            uit[l] = w
    return uit


def _fotos_uit_html(ruwe: str) -> list[str]:
    """Alle foto's van de advertentie, op volgorde, in de grootste versie.

    Let op: de pagina levert bij het opvragen niet altijd de hele reeks mee (de
    laatste miniaturen worden pas in een echte browser bijgeladen). Wat we hier
    krijgen is dus "alles wat de pagina meestuurt" — bij een advertentie met één
    foto in ons systeem is dat vrijwel altijd een verbetering.
    """
    basis = {"marktplaats": "https://images.marktplaats.com",
             "2dehands": "https://images.2dehands.com"}
    uit, gezien = [], set()
    for m in re.finditer(
            r'(?:https?:)?//images\.(marktplaats|2dehands)\.com(/api/v1/[a-z0-9\-]+/images/'
            r'[0-9a-f\-]{16,})', ruwe or "", re.I):
        sleutel = m.group(2).lower()
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uit.append(f"{basis[m.group(1).lower()]}{m.group(2)}?rule={FOTO_REGEL}")
    return uit


def _onze_conditie(waarde: str) -> str:
    """Marktplaats' woord voor de staat, in het woord dat wij gebruiken."""
    t = (waarde or "").lower()
    if not t:
        return ""
    if "nieuw met" in t:
        return "new_with_tags"
    if "zo goed als nieuw" in t:
        return "good"
    if "nieuw" in t:
        return "new"
    if "beschadigd" in t or "defect" in t:
        return "poor"
    if "gebruikt" in t or "gedragen" in t:
        return "fair"
    return ""


def _onze_maat(waarde: str) -> str:
    """Alleen een maat die op élk platform een maat is.

    Marktplaats kent emmertjes als "Overige maten" en "Maat 46/48 (XL) of
    groter". Zoiets in het item zetten zou op Vinted en eBay onzin worden, dus
    daar halen we hooguit de echte maat uit.
    """
    t = (waarde or "").strip()
    if not t:
        return ""
    m = re.search(r"\b(XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|XXXXL)\b", t, re.I)
    if m:
        return m.group(1).upper()
    n = re.fullmatch(r"\s*(\d{2,3})\s*", t)
    return n.group(1) if n else ""


async def volledige_advertentie(client: httpx.AsyncClient, url: str) -> dict:
    """Alles wat één advertentiepagina prijsgeeft, in één ophaalronde."""
    ruwe = await _pagina(client, url)
    if not ruwe:
        return {}
    k = _kenmerken_uit_html(ruwe)
    return {
        "description": _tekst_uit_html(ruwe),
        "photo_urls": _fotos_uit_html(ruwe),
        "brand": k.get("merk", ""),
        "size": _onze_maat(k.get("maat") or k.get("kledingmaat") or ""),
        "color": k.get("kleur", ""),
        "condition": _onze_conditie(k.get("conditie") or k.get("staat") or ""),
    }


def _is_afgekapt(kort: str, lang: str) -> bool:
    """Is `kort` het begin van `lang`, afgezien van witruimte?

    Alleen dan mogen we de opgeslagen omschrijving vervangen: het is dezelfde
    tekst, alleen korter. Wijkt hij inhoudelijk af, dan heeft de verkoper hem
    zelf aangepast en blijft hij staan.
    """
    def plat(t: str) -> str:
        return re.sub(r"\s+", " ", str(t or "")).strip().lower()

    k, l = plat(kort), plat(lang)
    if not k:
        return True
    # Marktplaats zet zelf soms een beletselteken achter een ingekorte tekst.
    k = k.rstrip(". \u2026")
    return bool(k) and l.startswith(k[: max(1, len(k) - 3)])


async def vul_item_aan_uit_advertentie(db, item: dict, url: str) -> dict:
    """Eén item bijwerken met wat er op zijn eigen advertentiepagina staat.

    Bedoeld voor het moment vlak voor een herplaatsing: de advertentie staat dan
    nog online, dus alles wat het item mist (omschrijving, de rest van de foto's,
    merk, maat, kleur, staat) is daar gewoon te lezen. Zonder deze stap wordt een
    geïmporteerde advertentie — die uit de zoeklijst komt en dus alleen titel,
    prijs en het omslagplaatje meekreeg — verwijderd en daarna geweigerd door het
    plaatsformulier, dat een omschrijving eist.

    Vult NOOIT iets dat al gevuld is, en schrijft niets als de pagina niets
    prijsgeeft. Geeft het bijgewerkte item terug.
    """
    if not (url or "").strip():
        return item
    try:
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": UA},
                                     follow_redirects=True) as client:
            gevonden = await volledige_advertentie(client, url)
    except Exception as e:  # noqa: BLE001 — een mislukte aanvulling mag niets breken
        logger.warning("mp_enrich: aanvullen vanaf %s mislukt: %s", url, e)
        return item
    if not gevonden:
        return item

    patch: dict = {}
    tekst = (gevonden.get("description") or "").strip()
    huidig = str(item.get("description") or "").strip()
    if tekst and not huidig:
        patch["description"] = tekst
    elif tekst and len(tekst) > len(huidig) and _is_afgekapt(huidig, tekst):
        # DE TEKST DIE WE HEBBEN IS EEN AFGEKAPTE VERSIE VAN DEZELFDE TEKST.
        #
        # Dat gebeurde door onze eigen 4000-tekengrens en door de zoeklijst van
        # Marktplaats, die alleen het begin meegeeft. Gevolg: advertenties
        # zonder artikelnummer, zonder verzendkosten, zonder de winkeluitleg
        # onderaan (Jaap, Zilverwebsite, 28-08-2026). We vullen alleen aan als
        # wat wij hebben letterlijk het begin is van wat er op de pagina staat;
        # een tekst die de verkoper zelf heeft aangepast blijft dus staan.
        patch["description"] = tekst
    fotos = gevonden.get("photo_urls") or []
    # Meer foto's dan we hebben is altijd winst: de advertentiepagina toont de
    # hele reeks, de zoeklijst waar de import uit komt alleen het omslagplaatje.
    if len(fotos) > len(item.get("photo_urls") or []):
        patch["photo_urls"] = fotos
    for veld in ("brand", "size", "color", "condition"):
        waarde = str(gevonden.get(veld) or "").strip()
        if waarde and not str(item.get(veld) or "").strip():
            patch[veld] = waarde
    if not patch:
        return item
    try:
        await naast_de_lus(lambda: db.table("items").update(patch)
                           .eq("id", item["id"]).execute())
    except Exception as e:  # noqa: BLE001
        logger.warning("mp_enrich: item %s bijwerken mislukt: %s", item.get("id"), e)
        return item
    logger.info("mp_enrich: item %s aangevuld vanaf de advertentiepagina (%s)",
                item.get("id"), ", ".join(sorted(patch)))
    return {**item, **patch}


async def volledige_omschrijving(client: httpx.AsyncClient, url: str) -> str:
    """De volledige tekst van één advertentiepagina.

    Marktplaats gaat bij veel aanvragen achter elkaar over op 403. Dat is geen
    fout in de advertentie maar een verzoek om rustiger aan te doen, dus wachten
    en opnieuw proberen is het juiste antwoord. Gemeten: zonder deze herkansing
    kwamen 52 van 240 teksten niet binnen.
    """
    return _tekst_uit_html(await _pagina(client, url))


async def _pagina(client: httpx.AsyncClient, url: str) -> str:
    """De ruwe HTML van één advertentiepagina, met dezelfde beleefde herkansing."""
    for poging in range(4):
        try:
            r = await client.get(url, headers={"Accept": "text/html"})
            if r.status_code in (403, 429, 503):
                await asyncio.sleep(3 * (poging + 1))
                continue
            if r.status_code != 200:
                return ""
            return r.text
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_enrich: advertentiepagina mislukt (%s): %s", url, e)
            await asyncio.sleep(2)
    return ""


async def _in_batches(taken: list, worker, deadline: float):
    """`worker` op elk item toepassen, in hapjes van TEGELIJK tegelijk, en
    stoppen zodra de deadline verstreken is — met wat nog niet is gedaan als
    tweede resultaat, zodat de aanroeper dat gewoon laat liggen voor de
    volgende keer in plaats van de verbinding te laten timen."""
    resultaten = []
    i = 0
    while i < len(taken):
        if time.monotonic() > deadline:
            break
        stuk = taken[i:i + TEGELIJK]
        resultaten.extend(await asyncio.gather(*(worker(x) for x in stuk)))
        i += TEGELIJK
    return resultaten, taken[i:]


async def verrijk(db, user_id: str, schrijf: bool = True,
                 maximaal: int = 0, melden=None) -> dict:
    """Vul prijs en omschrijving aan voor items die ze missen.

    Overschrijft nooit: een prijs of tekst die de verkoper zelf heeft ingevuld
    blijft staan. Alleen lege velden worden gevuld.

    Werkt binnen een tijdsbudget (BUDGET_SECONDEN): Cloudflare knipt een
    verzoek van meer dan ~100 seconden zelf af met een 524, en dat gaf de
    verkoper een kale foutpagina terwijl er niets mis was. Wat binnen het
    budget niet af komt, blijft gewoon openstaan — de knop op het scherm roept
    deze functie net zo vaak aan tot alles gedaan is.
    """
    start = time.monotonic()
    deadline = start + BUDGET_SECONDEN

    def zeg(tekst):
        logger.info("mp_enrich: %s", tekst)
        if melden:
            try:
                melden(tekst)
            except Exception:  # noqa: BLE001
                pass

    # fetch_all, NIET .limit(10000). PostgREST geeft er stilzwijgend hooguit
    # 1.000 terug, hoe hoog je de limiet ook zet. Bij Egbert Brouwer (2.135
    # items, 557 zonder prijs of tekst) betekende dat: deze functie zag alleen
    # de eerste 1.000 items, vond daarin 5 openstaande, zocht op díe 5 titels
    # naar zijn verkopersnummer, vond niets, en meldde "could not find your
    # adverts on Marktplaats" — terwijl zijn advertenties er gewoon stonden.
    rijen = await naast_de_lus(lambda: fetch_all(
        lambda: db.table("items")
        .select("id,title,price,description,photo_urls,brand,size,color,condition")
        .eq("user_id", user_id)))

    def _mist_iets(r: dict) -> bool:
        # Niet alleen prijs en tekst. Een geïmporteerde advertentie kwam ook
        # binnen met één foto en zonder merk of maat, en juist dat blokkeert
        # publiceren naar Marktplaats en 2dehands. Het staat allemaal op dezelfde
        # advertentiepagina die we hier tóch al ophalen.
        return (not str(r.get("description") or "").strip()
                or not r.get("price")
                or len(r.get("photo_urls") or []) <= 1
                or not str(r.get("brand") or "").strip()
                or not str(r.get("size") or "").strip())

    open_ = [r for r in rijen if _mist_iets(r)]
    if maximaal:
        open_ = open_[:maximaal]
    uit = {"items": len(rijen), "te_doen": len(open_), "gevonden": 0,
           "prijs": 0, "omschrijving": 0, "geen_tekst": 0, "fotos": 0, "kenmerken": 0,
           "verkoper_id": None, "reden": ""}
    if not open_:
        uit["reden"] = "nothing to do"
        return uit

    # Voor het zóeken van het verkopersnummer gebruiken we titels uit het HELE
    # aanbod, niet alleen uit de items die nog leeg zijn. Die lege items zijn
    # namelijk precies de moeilijke gevallen — als ze makkelijk vindbaar waren,
    # waren ze een ronde eerder al gevuld. En ze staan ook nog eens bij elkaar
    # in de lijst, dus de eerste acht waren vaak acht varianten van hetzelfde
    # onvindbare artikel. Vandaar: eerst de items die al een prijs hebben (die
    # zijn aantoonbaar ooit gematcht), daarna de rest, en verspreid over de
    # hele lijst in plaats van allemaal uit hetzelfde hoekje.
    def _verspreid(rijtje):
        if len(rijtje) <= MAX_TITELPOGINGEN:
            return [r["title"] for r in rijtje if r.get("title")]
        stap = max(1, len(rijtje) // MAX_TITELPOGINGEN)
        return [rijtje[i]["title"] for i in range(0, len(rijtje), stap) if rijtje[i].get("title")]

    gevuld = [r for r in rijen if r.get("price") and str(r.get("description") or "").strip()]
    zoektitels = _verspreid(gevuld) + _verspreid(open_)

    limiet = httpx.Limits(max_connections=TEGELIJK, max_keepalive_connections=TEGELIJK)
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": UA},
                                 follow_redirects=True, limits=limiet) as client:
        vid = await zoek_verkoper_id(client, zoektitels)
        uit["verkoper_id"] = vid
        if not vid:
            uit["reden"] = ("could not find your adverts on Marktplaats — "
                            "are they still online under the same titles?")
            return uit
        zeg(f"verkoper {vid} gevonden, advertenties ophalen")

        adv = await haal_advertenties(client, vid, deadline=deadline)
        zeg(f"{len(adv)} advertenties met een unieke titel")

        koppels = [(r, adv[_sleutel(r["title"])]) for r in open_
                   if _sleutel(r["title"]) in adv]
        rest = [r for r in open_ if _sleutel(r["title"]) not in adv]
        zeg(f"{len(koppels)} van {len(open_)} direct teruggevonden, "
            f"{len(rest)} worden apart opgezocht")

        # De verkoperslijst houdt op bij 5.000. Alles wat daar niet in zat zoeken
        # we alsnog per titel op; dat is trager maar het scheelt de verkoper het
        # met de hand overtikken van honderden advertenties. Wat niet binnen het
        # tijdsbudget past, blijft gewoon "te_doen" en komt de volgende ronde aan
        # de beurt — beter dan de hele aanvraag laten timen.
        if rest:
            async def zoek(item):
                a = await zoek_een_titel(client, vid, item["title"])
                await asyncio.sleep(0.25)
                return item, a

            gevonden_rest, _ = await _in_batches(rest, zoek, deadline)
            for item, a in gevonden_rest:
                if a:
                    koppels.append((item, a))

        uit["gevonden"] = len(koppels)
        zeg(f"{len(koppels)} van {len(open_)} items teruggevonden")

        gedaan = [0]

        async def een(paar):
            item, a = paar
            patch = {}
            if not item.get("price") and a["price"]:
                patch["price"] = a["price"]
            # Eén ophaalronde per advertentie, en daar komt alles uit: de tekst,
            # de hele fotoreeks en de kenmerken.
            mist_tekst = not str(item.get("description") or "").strip()
            mist_rest = (len(item.get("photo_urls") or []) <= 1
                         or not str(item.get("brand") or "").strip()
                         or not str(item.get("size") or "").strip()
                         or not str(item.get("color") or "").strip()
                         or not str(item.get("condition") or "").strip())
            if (mist_tekst or mist_rest) and a["url"]:
                pagina = await volledige_advertentie(client, a["url"])
                # BEWUST geen terugval op de korte tekst uit de zoekresultaten:
                # die is door Marktplaats afgekapt en stopt middenin een zin.
                # Zo'n halve tekst zou daarna gewoon op Vinted of eBay
                # verschijnen. Liever leeg laten en het melden — leeg blokkeert
                # publiceren, een halve zin niet.
                if mist_tekst and pagina.get("description"):
                    patch["description"] = pagina["description"]
                fotos = pagina.get("photo_urls") or []
                if len(fotos) > len(item.get("photo_urls") or []):
                    patch["photo_urls"] = fotos
                for veld in ("brand", "size", "color", "condition"):
                    if pagina.get(veld) and not str(item.get(veld) or "").strip():
                        patch[veld] = pagina[veld]
                await asyncio.sleep(0.25)
            gedaan[0] += 1
            if gedaan[0] % 25 == 0:
                zeg(f"{gedaan[0]}/{len(koppels)} verwerkt")
            return item, patch

        verwerkt, _ = await _in_batches(koppels, een, deadline)
        for item, patch in verwerkt:
            if not str(item.get("description") or "").strip() and "description" not in patch:
                uit["geen_tekst"] += 1
            if not patch:
                continue
            if "price" in patch:
                uit["prijs"] += 1
            if "description" in patch:
                uit["omschrijving"] += 1
            if "photo_urls" in patch:
                uit["fotos"] = uit.get("fotos", 0) + 1
            if any(v in patch for v in ("brand", "size", "color", "condition")):
                uit["kenmerken"] = uit.get("kenmerken", 0) + 1
            if schrijf:
                try:
                    (await naast_de_lus(lambda: db.table("items").update(patch).eq("id", item["id"]).execute()))
                except Exception as e:  # noqa: BLE001
                    logger.warning("mp_enrich: opslaan mislukt voor %s: %s", item["id"], e)
    return uit


# ── Vanzelf aanvullen, zonder dat er iemand op een knop drukt ─────────────
#
# WAAROM DIT ER IS (29-08-2026)
# Bij het importeren haalt de extensie de volledige tekst per advertentie op,
# maar daar zit een harde tijdgrens van vier minuten op (zie VERRIJK_BUDGET_MS in
# extension/background.js — zonder die grens raakte een grote import onderweg
# álles kwijt). Alles wat na die vier minuten komt, komt binnen met alleen titel,
# prijs en foto. Amanda Haas meldde precies dat: "de advertenties zijn wel
# geïmporteerd, maar de teksten niet."
#
# De reparatie bestond al — de knop "Fill from Marktplaats" — maar die moet je
# kennen én zelf indrukken. Een import die half werk aflevert en dan wacht tot de
# verkoper doorheeft dat er nog een knop is, is geen afgeronde import. Deze ronde
# doet hetzelfde werk vanzelf, op de server, zonder browser.
#
# Beleefd blijven bij Marktplaats: één verkoper per ronde, hooguit 150 items, en
# hetzelfde tijdsbudget als de knop. De volgende ronde is de volgende verkoper.
AANVUL_PER_VERKOPER = 150

# Het demo-account staat vol nepadvertenties die niet op Marktplaats bestaan.
# Daarvoor zoeken is puur belasting bij Marktplaats zonder dat er iets te vinden
# valt.
DEMO_ACCOUNT = "00000000-0000-0000-0000-000000000001"

# Waar we gebleven waren. Blijft niet bewaard over een herstart heen, en dat mag:
# de ronde draait elk kwartier, dus na een herstart begint hij gewoon weer
# vooraan en komt iedereen alsnog aan de beurt.
_volgende_verkoper = 0


async def _verkopers_met_gaten(db) -> list[str]:
    """De verkopers die nog items zonder omschrijving hebben, meest eerst.

    Alleen verkopers die ooit vanaf Marktplaats of 2dehands hebben geïmporteerd:
    bij de rest staan de advertenties daar niet en zouden we Marktplaats voor
    niets belasten.

    NIET op `platform_credentials` filteren, hoe logisch dat ook klinkt. Gemeten
    29-08-2026: van de acht verkopers met ontbrekende teksten had er precies één
    zo'n rij, en dat was het demo-account. Marktplaats loopt via de extensie in
    de browser van de verkoper, dus er is voor gewone verkopers helemaal geen
    inlogrij op de server. Die filter liet deze ronde dus alleen op het
    demo-account draaien — het tegenovergestelde van de bedoeling. Wat er wél
    staat bij iedereen die geïmporteerd heeft, is zijn importlijst.
    """
    rijen = await naast_de_lus(lambda: fetch_all(
        lambda: db.table("items")
        .select("user_id")
        .or_("description.is.null,description.eq.")))
    aantal: dict[str, int] = {}
    for r in (rijen or []):
        if r.get("user_id"):
            aantal[r["user_id"]] = aantal.get(r["user_id"], 0) + 1
    if not aantal:
        return []
    # Per verkoper één vraag met count: de importlijst telt tienduizenden rijen,
    # en die allemaal ophalen om er acht namen uit te halen is verspilling.
    def _heeft_geimporteerd(uid: str) -> bool:
        try:
            return bool(db.table("import_candidates").select("id", count="exact")
                        .eq("user_id", uid).in_("platform", ["marktplaats", "2dehands"])
                        .limit(1).execute().count)
        except Exception as e:  # noqa: BLE001 — bij twijfel overslaan
            logger.warning("mp_enrich: kon importlijst van %s niet lezen: %s", uid, e)
            return False

    met_gaten = [u for u in aantal
                 if u != DEMO_ACCOUNT and await naast_de_lus(
                     lambda u=u: _heeft_geimporteerd(u))]
    return sorted(met_gaten, key=lambda u: -aantal[u])


async def vul_ontbrekende_teksten_aan() -> dict:
    """Eén verkoper per ronde bijwerken. Aangeroepen door de planner."""
    global _volgende_verkoper
    from backend.database import get_db

    db = get_db()
    verkopers = await _verkopers_met_gaten(db)
    if not verkopers:
        return {"verkopers": 0, "reden": "niets te doen"}

    # Beurtelings, zodat één verkoper met duizenden items de rest niet blokkeert.
    _volgende_verkoper %= len(verkopers)
    user_id = verkopers[_volgende_verkoper]
    _volgende_verkoper += 1

    uit = await verrijk(db, user_id, schrijf=True, maximaal=AANVUL_PER_VERKOPER)
    logger.info("mp_enrich automatisch: %s -> %s teksten, %s prijzen (van %s open)",
                user_id, uit.get("omschrijving"), uit.get("prijs"), uit.get("te_doen"))
    return {"verkopers": len(verkopers), "verkoper": user_id, **uit}
