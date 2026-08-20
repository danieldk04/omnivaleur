"""
De ECHTE plaatsingsdatum van een Marktplaats-advertentie ophalen.

WAAROM DIT BESTAAT
Bij het importeren weten we niet wanneer een advertentie op Marktplaats is
gezet, dus zetten we de datum op vandaag. Voor het automatisch herplaatsen is
dat precies de verkeerde datum: Marktplaats gooit een gratis advertentie na
dertig dagen weg, gerekend vanaf de ECHTE plaatsdatum. Een advertentie die al
achtentwintig dagen online staat, ziet er bij ons dan uit als splinternieuw en
komt pas een maand later aan de beurt — als hij bij Marktplaats allang weg is.

Gemeten geval 20-08-2026: Jaap van Zilverwebsite importeerde zijn 1.222
advertenties op 18 augustus. Ongeveer honderd daarvan verlopen eind augustus.
Met de importdatum als startpunt zou Omnivaleur ze pas half september oppakken
en was hij ze alle honderd kwijt.

De openbare zoek-API van Marktplaats geeft per advertentie een datum, alleen in
mensentaal ("Vandaag", "Eergisteren", "12 aug 24"). Die vertalen we terug.
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx

from backend.services.mp_enrich import PAGINA, MAX_PAGINAS, ZOEK, _json, zoek_verkoper_id

logger = logging.getLogger(__name__)

_MAANDEN = {"jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}


def parse_mp_datum(tekst: str, vandaag: date | None = None) -> date | None:
    """"Eergisteren" of "12 aug 24" omzetten naar een echte datum.

    Onbekende vorm levert None op, en None betekent hier: niets veranderen. Een
    gegokte datum is erger dan geen datum, want daarmee zou een advertentie te
    vroeg of juist te laat opnieuw geplaatst worden.
    """
    vandaag = vandaag or date.today()
    t = (tekst or "").strip().lower()
    if not t:
        return None
    if t.startswith("vandaag"):
        return vandaag
    if t.startswith("gisteren"):
        return vandaag - timedelta(days=1)
    if t.startswith("eergisteren"):
        return vandaag - timedelta(days=2)
    m = re.match(r"^(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s*(\d{2,4})?$", t)
    if not m:
        return None
    dag, maand_kort, jaar = m.group(1), m.group(2)[:3], m.group(3)
    maand = _MAANDEN.get(maand_kort)
    if not maand:
        return None
    if jaar:
        j = int(jaar)
        j += 2000 if j < 100 else 0
    else:
        # Geen jaartal betekent bij Marktplaats "dit jaar" — tenzij die datum nog
        # moet komen, dan was het vorig jaar.
        j = vandaag.year
    try:
        uit = date(j, maand, int(dag))
    except ValueError:
        return None
    if not jaar and uit > vandaag:
        uit = uit.replace(year=j - 1)
    return uit if uit <= vandaag else None


async def _datums_van_verkoper(client: httpx.AsyncClient, verkoper_id: int) -> dict[str, date]:
    """Per advertentienummer de datum die Marktplaats zelf toont."""
    uit: dict[str, date] = {}
    for pagina in range(MAX_PAGINAS):
        try:
            data = await _json(client, ZOEK, {"sellerIds[]": verkoper_id,
                                              "limit": PAGINA, "offset": pagina * PAGINA})
        except Exception as e:  # noqa: BLE001
            logger.warning("mp_datums: pagina %s mislukt: %s", pagina, e)
            break
        rijen = data.get("listings") or []
        if not rijen:
            break
        for l in rijen:
            d = parse_mp_datum(l.get("date") or "")
            nummer = str(l.get("itemId") or "").strip()
            if d and nummer:
                uit[nummer] = d
        if len(rijen) < PAGINA:
            break
        await asyncio.sleep(0.2)
    return uit


async def corrigeer_listed_at(db, user_id: str, titels: list[str],
                              nummers: set[str]) -> int:
    """Zet listed_at van deze verkoper op de echte Marktplaats-datum.

    Geeft terug hoeveel advertenties zijn bijgesteld. Vindt hij de verkoper niet
    of geeft Marktplaats niets bruikbaars terug, dan verandert er niets.
    """
    if not nummers:
        return 0
    async with httpx.AsyncClient(timeout=25, headers={"User-Agent": "Mozilla/5.0"}) as client:
        verkoper = await zoek_verkoper_id(client, titels)
        if not verkoper:
            logger.info("mp_datums: verkoper niet gevonden voor %s", user_id)
            return 0
        datums = await _datums_van_verkoper(client, verkoper)
    if not datums:
        return 0
    bijgesteld = 0
    for nummer, d in datums.items():
        if nummer not in nummers:
            continue
        wanneer = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc).isoformat()
        try:
            db.table("listings").update({"listed_at": wanneer}).eq(
                "platform", "marktplaats").eq("platform_listing_id", nummer).execute()
            bijgesteld += 1
        except Exception as e:  # noqa: BLE001 — één advertentie mag de rest niet stoppen
            logger.warning("mp_datums: %s niet bijgesteld: %s", nummer, e)
    logger.info("mp_datums: %s advertenties op hun echte datum gezet voor %s",
                bijgesteld, user_id)
    return bijgesteld
