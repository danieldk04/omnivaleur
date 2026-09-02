"""Ontbrekende advertentieteksten ophalen bij de eigen Vinted-advertenties.

WAAROM DIT ER IS (02-09-2026, Toon van dejuistetoon)
====================================================
Toon importeerde 1.024 advertenties uit zijn Vinted-kast. Bij 244 daarvan bleef
de omschrijving leeg, en zonder omschrijving weigert het dashboard te publiceren
naar Marktplaats, 2dehands en Facebook. Zijn woorden: "alles blijft vaag en kan
niets aanklikken".

Nagemeten waar die tekst blijft:

* Vinted's kastoverzicht (`/api/v2/wardrobe/{id}/items`) geeft titel, prijs,
  foto's, merk en maat — maar géén omschrijving. Gecontroleerd: nul van de vijf
  advertenties had er een.
* Het detail-endpoint dat de extensie daarvoor gebruikte
  (`/api/v2/items/{id}`) is dood. Gemeten: 404, allebei de varianten, ook zonder
  inloggen. In Toons eigen scanlogboek staat het letterlijk: `api404`.
* De openbare advertentiepagina (`/items/{id}`) heeft de tekst wél. Steekproef
  van acht advertenties die bij ons leeg stonden: alle acht hadden op Vinted
  gewoon een omschrijving van 51 tot 313 tekens.

Waarom het dan tóch misging: Vinted knijpt af. Gemeten vanaf één adres:

    26 verzoeken op rij (0,5s ertussen)  -> daarna 429
    30 seconden pauze                    -> nog maar 2 pagina's, dan weer 429
    60 seconden pauze                    -> 15 pagina's, dan weer 429

Ruwweg vijftien pagina's per minuut, en dat is alles. De extensie vroeg er
duizend per scan op, driekwart daarvan voor teksten die ze allang had. Vandaar
de pauze van VIER SECONDEN hieronder: precies onder de gemeten grens, niet een
getal dat plausibel leek.

Deze ronde vult alleen wat leeg is. Een tekst die de verkoper zelf heeft
geschreven of aangepast blijft staan.
"""
import asyncio
import html as _html
import json
import logging
import re
import time

import httpx

from backend.database import fetch_all, fetch_all_in, naast_de_lus

logger = logging.getLogger(__name__)

# Zelfde reden als in mp_enrich: Cloudflare kapt een verzoek van meer dan ~100
# seconden af met een 524, en dat komt bij de verkoper aan als een kale
# foutpagina terwijl er niets mis is. Ruim daaronder blijven en de rest
# overlaten aan de volgende ronde; het scherm roept net zo vaak aan tot het op is.
BUDGET_SECONDEN = 75

# Gemeten grens: ~15 pagina's per minuut. Vier seconden ertussen zit daar net
# onder. Eén voor één, niet parallel — bij deze rem levert gelijktijdigheid
# niets op behalve een snellere 429.
PAUZE_SECONDEN = 4.0

# Zo vaak achter elkaar 429 en we stoppen de ronde. Doorvragen op een dichte
# deur levert alleen maar lege uitkomsten op, en lege uitkomsten waren nu juist
# het probleem.
MAX_KNEPEN = 3

# Vinted's eigen tekstlengte ligt ruim hieronder; dit is alleen een noodrem
# tegen een pagina die iets anders blijkt te zijn dan wij denken.
MAX_TEKST = 8000

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_DESC_RE = re.compile(r'"description":"((?:[^"\\]|\\.)*)"')
_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\']'
    r'[^>]+content=["\']([^"\']+)["\']', re.I)


def tekst_uit_pagina(html: str) -> str:
    """De advertentietekst uit de HTML van een Vinted-advertentiepagina.

    Vinted zet meerdere `"description":"…"` in de pagina en de eerste is vaak een
    lege SEO-stomp. We houden de langste; die is de echte. Levert dat niets op,
    dan de og:description als tweede keus.

    Losgetrokken van het netwerk zodat hij te testen is op een opgeslagen pagina.
    """
    beste = ""
    for m in _DESC_RE.finditer(html or ""):
        try:
            waarde = json.loads('"' + m.group(1) + '"')
        except Exception:  # noqa: BLE001
            waarde = m.group(1)
        if len(waarde) > len(beste):
            beste = waarde
    if not beste:
        m = _OG_RE.search(html or "")
        if m:
            beste = _html.unescape(m.group(1))
    return beste.strip()[:MAX_TEKST]


async def _haal(client: httpx.AsyncClient, url: str) -> tuple[int, str]:
    r = await client.get(url)
    return r.status_code, (r.text if r.status_code == 200 else "")


async def verrijk(db, user_id: str, item_id: str | None = None,
                  maximaal: int = 0) -> dict:
    """Vul lege omschrijvingen aan vanaf de eigen Vinted-advertenties.

    `item_id` gezet: alleen dat ene artikel (de knop in het publiceervenster).
    Anders: alles wat leeg is, tot het tijdsbudget op is.

    Overschrijft nooit. Alleen een leeg veld wordt gevuld.
    """
    start = time.monotonic()
    deadline = start + BUDGET_SECONDEN
    uit = {"te_doen": 0, "gevuld": 0, "geen_tekst": 0, "geknepen": 0,
           "resterend": 0, "reden": ""}

    # Welke artikelen missen tekst. Alleen id's lezen, nooit de kolom zelf: dat
    # is de dikste die we hebben en een ronde die hem meenam at destijds het
    # verkeersbudget van Supabase op (zie mp_enrich.verrijk).
    def _zonder_tekst():
        q = (db.table("items").select("id").eq("user_id", user_id)
             .or_("description.is.null,description.eq."))
        return q.eq("id", item_id) if item_id else q

    zonder = {r["id"] for r in await naast_de_lus(lambda: fetch_all(_zonder_tekst))}
    if not zonder:
        uit["reden"] = "nothing to do"
        return uit

    # Hun Vinted-advertentie. Alleen wat er nu nog staat: van een verwijderde
    # advertentie valt niets meer te halen.
    rijen = await naast_de_lus(lambda: fetch_all_in(
        lambda: db.table("listings")
        .select("item_id,platform_listing_id,platform_listing_url")
        .eq("platform", "vinted").eq("status", "active"),
        "item_id", sorted(zonder)))

    doelen: dict[str, str] = {}   # item_id -> url
    for l in rijen:
        iid = l.get("item_id")
        if not iid or iid in doelen:
            continue
        url = l.get("platform_listing_url")
        if not url and l.get("platform_listing_id"):
            url = f"https://www.vinted.nl/items/{l['platform_listing_id']}"
        if url:
            doelen[iid] = url

    volgorde = sorted(doelen.items())
    if maximaal:
        volgorde = volgorde[:maximaal]
    uit["te_doen"] = len(volgorde)
    if not volgorde:
        uit["reden"] = "no live Vinted listing to read the text from"
        return uit

    knepen = 0
    gedaan = 0
    async with httpx.AsyncClient(
            timeout=25, follow_redirects=True,
            headers={"User-Agent": _UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}) as client:
        for iid, url in volgorde:
            if time.monotonic() > deadline:
                uit["reden"] = "time budget reached — call again for the rest"
                break
            try:
                status, html = await _haal(client, url)
            except Exception as e:  # noqa: BLE001
                logger.warning("vinted_enrich: %s niet opgehaald (%s)", url, e)
                status, html = 0, ""

            if status == 429:
                knepen += 1
                uit["geknepen"] += 1
                if knepen >= MAX_KNEPEN:
                    uit["reden"] = "Vinted is rate-limiting — call again in a minute"
                    break
                # Gemeten: na 30s laat hij er 2 door, na 60s weer een stuk of
                # vijftien. Een minuut wachten is dus het eerste moment waarop
                # doorgaan zin heeft.
                await asyncio.sleep(60)
                continue
            knepen = 0
            gedaan += 1

            if status != 200:
                continue
            tekst = tekst_uit_pagina(html)
            if not tekst:
                uit["geen_tekst"] += 1
                continue
            try:
                # Nog één keer controleren dat het veld écht leeg is. Tussen het
                # lezen hierboven en dit moment kan de verkoper zelf iets hebben
                # ingetypt, en zijn tekst wint altijd van de onze.
                await naast_de_lus(lambda i=iid, t=tekst: db.table("items")
                                   .update({"description": t})
                                   .eq("id", i).eq("user_id", user_id)
                                   .or_("description.is.null,description.eq.")
                                   .execute())
                uit["gevuld"] += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("vinted_enrich: %s niet weggeschreven (%s)", iid, e)
            await asyncio.sleep(PAUZE_SECONDEN)

    uit["resterend"] = max(0, len(volgorde) - gedaan)
    if not uit["reden"]:
        uit["reden"] = "done"
    logger.info("vinted_enrich %s: %s van %s gevuld, %s over (%s)",
                user_id, uit["gevuld"], uit["te_doen"], uit["resterend"], uit["reden"])
    return uit
