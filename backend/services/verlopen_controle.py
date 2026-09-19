"""Een verlopen advertentie is geen verkoop — en dus ook geen vraag.

WAAROM DIT ER IS (19-09-2026, Lynn van De Juiste Toon)

Lynn schreef: "Bij Items staat bij 'did these items sell?' de melding 'Not found
on the platform anymore', maar als ik die dan na ga staan ze er wel nog op.
Voornamelijk bij 2dehands."

Allebei waar. Het zoekertje is van de zoekresultaten af, maar zijn eigen pagina
staat er nog: foto's, tekst, en het stempel VERLOPEN erop. Zo ziet een verlopen
advertentie op Marktplaats en 2dehands eruit. Wie hem opzoekt ziet zijn
advertentie staan en snapt de vraag niet — terecht.

Gemeten op haar account op 19-09-2026: van de 74 gemelde 2dehands-zoekertjes
gaven er 55 een HTTP 410 met "Dit zoekertje is helaas verlopen" op de pagina
(de overige 19 gaven 403 omdat 2dehands ons tempo afkapte, geen tegenbewijs).
Van vijf bewezen levende advertenties gaf er nul dat signaal. Verlopen en levend
zijn dus scherp uit elkaar te houden.

De extensie kijkt sinds 1.0.341 zelf naar die tekst en meldt zo'n advertentie als
"verlopen" in plaats van als mogelijke verkoop. Maar een nieuwe extensieversie
moet eerst weken door de Chrome Web Store, en de vragen die er NU staan gaan
daar niet vanzelf van weg. Daarom kijkt de server het ook zelf na, op precies
dezelfde openbare pagina die de verkoper zelf opent.

DE REMMEN
1. Alleen bewijs telt. Er gebeurt uitsluitend iets bij het verlopen-blok of de
   letterlijke verlopen-zin op de pagina. Een 403, een 401, een 404 zonder tekst,
   een storing of een lege pagina laat de vraag staan zoals hij staat.
2. Rustig aan. Marktplaats en 2dehands kappen een snelle reeks af met 403 —
   gemeten: op volle snelheid 24 van de 74, met acht seconden ertussen nul van
   de tien. Daarom een kleine hap per ronde, ruim uit elkaar.
3. Blijft een hele ronde zonder antwoord, dan is de meting kapot en niet de
   voorraad: de ronde stopt en er verandert niets.
4. Alleen advertenties waarvan wij het openbare adres kennen. Zonder adres valt
   er niets na te kijken en is zwijgen het juiste antwoord.
"""
from __future__ import annotations

import asyncio
import logging
import re

from datetime import datetime, timezone

from backend.database import get_db, naast_de_lus

logger = logging.getLogger(__name__)

# Het verlopen-blok dat beide platforms om een verlopen advertentie zetten
# (taalonafhankelijk, gemeten op allebei de kanten) plus de zin die erbij staat:
# "Deze advertentie is helaas verlopen" / "Dit zoekertje is helaas verlopen".
IS_VERLOPEN = re.compile(
    r"expired-listing-root|expiredlisting-module"
    r"|(advertentie|zoekertje)\s*(is)?\s*(helaas)?\s*verlopen")

# Alleen deze twee kanalen laten een advertentie vanzelf verlopen. Vinted en
# Shopify doen dat niet, dus daar betekent "weg" iets heel anders.
KANALEN = ("marktplaats", "2dehands")

# Per ronde, en met deze pauze ertussen. Zie rem 2 hierboven.
MAX_PER_RONDE = 25
PAUZE_SECONDEN = 8.0
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


async def _pagina_zegt_verlopen(client, url: str) -> bool | None:
    """True = bewezen verlopen, False = bewezen niet, None = geen uitspraak."""
    try:
        r = await client.get(url, follow_redirects=True)
    except Exception as e:                       # noqa: BLE001 — geen verbinding is geen uitspraak
        logger.info("verlopen-controle: %s niet opgehaald: %s", url[:80], e)
        return None
    if r.status_code in (401, 403) or r.status_code >= 500:
        return None                              # afgekapt of storing: niets bewezen
    tekst = (r.text or "").lower()
    if IS_VERLOPEN.search(tekst):
        return True
    if r.status_code == 200 and len(tekst) > 5000:
        return False                             # een echte, levende pagina
    return None


async def controleer_verlopen_verkoopvragen() -> dict:
    """Openstaande verkoopvragen natrekken op de advertentiepagina zelf.

    Een advertentie die zelf zegt dat hij verlopen is, gaat naar het archief met
    die reden erbij. De verkoper krijgt er geen vraag meer over, want er valt
    niets te beantwoorden.
    """
    import httpx
    from backend.api.listings import VERDENKING_REDENEN

    db = get_db()
    nu = datetime.now(timezone.utc).isoformat()
    try:
        rijen = ((await naast_de_lus(lambda: db.table("listings")
                 .select("id,item_id,platform,platform_listing_id,platform_listing_url,error_message")
                 .eq("status", "sold_unconfirmed")
                 .in_("platform", list(KANALEN))
                 .order("last_checked")
                 .limit(MAX_PER_RONDE * 4)
                 .execute())).data or [])
    except Exception as e:                       # noqa: BLE001
        logger.warning("verlopen-controle: openstaande vragen niet gelezen: %s", e)
        return {"nagekeken": 0, "verlopen": 0}

    # Alleen vragen die op "de advertentie is weg" berusten. Een advertentie met
    # een verkocht-label op de pagina, of een Marktplaats-gesprek met een
    # "Verkocht!"-melding, is een heel ander verhaal en blijft staan.
    weg_reden = VERDENKING_REDENEN["weg"][:40]
    jong_reden = VERDENKING_REDENEN["verdwenen_te_jong"][:40]
    kandidaten = [r for r in rijen
                  if (r.get("platform_listing_url") or "").strip()
                  and str(r.get("error_message") or "").startswith((weg_reden, jong_reden))]
    if not kandidaten:
        return {"nagekeken": 0, "verlopen": 0}

    reden = VERDENKING_REDENEN["verlopen"]
    nagekeken = gearchiveerd = zonder_uitspraak = 0
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": UA,
                                                      "Accept-Language": "nl-NL,nl;q=0.9"}) as client:
        for rij in kandidaten[:MAX_PER_RONDE]:
            if nagekeken:
                await asyncio.sleep(PAUZE_SECONDEN)
            url = str(rij["platform_listing_url"]).split("?")[0]
            uitkomst = await _pagina_zegt_verlopen(client, url)
            nagekeken += 1
            if uitkomst is None:
                zonder_uitspraak += 1
                # Hele ronde zonder antwoord: dan meten we niet, dan worden we
                # geweigerd. Stoppen en niets concluderen.
                if nagekeken >= 5 and zonder_uitspraak == nagekeken:
                    logger.warning("verlopen-controle: eerste %s pagina's gaven geen uitsluitsel "
                                   "— ronde afgebroken, er is niets gewijzigd", nagekeken)
                    break
                continue
            if uitkomst is False:
                continue
            try:
                (await naast_de_lus(lambda r=rij: db.table("listings").update({
                    "status": "delisted",
                    "error_message": reden,
                    "last_checked": nu,
                }).eq("id", r["id"]).eq("status", "sold_unconfirmed").execute()))
                gearchiveerd += 1
                logger.info("verlopen-controle: %s %s was verlopen, geen verkoop — "
                            "verkoopvraag ingetrokken", rij["platform"], rij["platform_listing_id"])
            except Exception as e:                # noqa: BLE001 — één rij mag de ronde niet stoppen
                logger.warning("verlopen-controle: %s niet bijgewerkt: %s", rij["id"], e)

    logger.info("verlopen-controle: %s van %s openstaande verkoopvragen nagekeken, "
                "%s aantoonbaar verlopen en ingetrokken, %s zonder uitspraak",
                nagekeken, len(kandidaten), gearchiveerd, zonder_uitspraak)
    return {"nagekeken": nagekeken, "verlopen": gearchiveerd,
            "open": len(kandidaten), "zonder_uitspraak": zonder_uitspraak}
