"""Foto's die nog op Marktplaats staan alsnog in onze eigen opslag zetten.

WAAROM (25-10-2026, gemeten bij 9 klanten). 883 artikelen hielden foto-adressen
op images.marktplaats.com: het kopiëren bij de import is best-effort en faalt
stil, en er was geen inhaalronde voor Marktplaats (bronfotos_inhalen draait
alleen voor WooCommerce). Zo'n adres gaat dood zodra de advertentie vervangen of
weggehaald wordt: bij 0b28c1ce gaf 279 van de 306 oudere artikelen al 404, en 266
daarvan hoorden bij een advertentie die later vervangen was. Daarna is het
artikel nergens meer te plaatsen ("None of the 5 photo(s) could be downloaded").

Per artikel: eerst de opgeslagen adressen kopiëren. Leven die niet meer, dan de
foto's van de advertentie zoals hij NU op Marktplaats staat (relist._live_fotos,
met diens tempo en blokkaderem), alleen als dat er niet minder zijn. Er wordt
alleen geschreven als daarna geen enkele foto meer op Marktplaats staat; anders
blijft het artikel precies zoals het was.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Advertentiepagina's per ronde. Marktplaats gaf na een veertigtal pagina's in
# een paar minuten 403 op alles (gemeten 29-09-2026); _live_fotos houdt 8 s
# tussen pagina's en zwijgt een uur na een blokkade.
MAX_PAGINAS = 25
VOLLEDIG_OPNIEUW_NA_SEC = 24 * 3600

# Wie bij de laatste volledige ronde nog achterstand had. Zo leest een ronde niet
# elk uur alle artikelen van alle klanten opnieuw (egress), alleen eens per dag.
_stand = {"klanten": None, "volledig_om": 0.0}


def _op_marktplaats(urls) -> bool:
    from backend.services.relist import _sterft_met_advertentie
    return any(_sterft_met_advertentie(u, "marktplaats") for u in (urls or []))


async def artikel_inhalen(db, item: dict, budget: dict) -> str:
    """Eén artikel. Geeft 'hersteld', 'niet_gelukt' of 'geen_pagina' terug."""
    from backend.database import naast_de_lus
    from backend.services.photo_mirror import _wachtende_plaatsingen_bijwerken, mirror_photos
    from backend.services.relist import _live_fotos

    oud = [u for u in (item.get("photo_urls") or []) if u]
    uid = item["user_id"]
    nieuw = await mirror_photos(oud, uid)
    if _op_marktplaats(nieuw) or not nieuw:
        if budget["paginas"] <= 0:
            return "geen_pagina"
        rijen = (await naast_de_lus(lambda: db.table("listings")
                 .select("platform_listing_id,status").eq("item_id", item["id"])
                 .eq("platform", "marktplaats").eq("status", "active").execute())).data or []
        rij = next((r for r in rijen if r.get("platform_listing_id")), None)
        if not rij:
            return "niet_gelukt"
        budget["paginas"] -= 1
        live = await _live_fotos("marktplaats", rij)
        if len(live) < len(oud):
            return "niet_gelukt"
        nieuw = await mirror_photos(live, uid)
    if not nieuw or _op_marktplaats(nieuw) or len(nieuw) < len(set(oud)):
        return "niet_gelukt"
    await naast_de_lus(lambda: db.table("items").update({"photo_urls": nieuw})
                       .eq("id", item["id"]).eq("user_id", uid).execute())
    logger.info("mp_fotos_inhalen %s/%s: oud=%s nieuw=%s", uid, item["id"], oud, nieuw)
    await _wachtende_plaatsingen_bijwerken(db, uid, item["id"], oud, nieuw, 0)
    return "hersteld"


async def mp_fotos_inhalen(max_paginas: int = MAX_PAGINAS) -> dict:
    from backend.database import fetch_all, get_db, naast_de_lus
    db = get_db()
    nu = time.time()
    if _stand["klanten"] is None or nu - _stand["volledig_om"] > VOLLEDIG_OPNIEUW_NA_SEC:
        rijen = (await naast_de_lus(lambda: db.table("extension_heartbeat")
                 .select("user_id").limit(1000).execute())).data or []
        _stand["klanten"] = sorted({r["user_id"] for r in rijen if r.get("user_id")})
        _stand["volledig_om"] = nu
    budget = {"paginas": max_paginas}
    uit = {"hersteld": 0, "niet_gelukt": 0, "achterstand": 0}
    nog = []
    for uid in list(_stand["klanten"]):
        items = await naast_de_lus(lambda uid=uid: fetch_all(
            lambda: db.table("items").select("id,user_id,photo_urls").eq("user_id", uid)))
        todo = [i for i in items if _op_marktplaats(i.get("photo_urls"))]
        if not todo:
            continue
        nog.append(uid)
        uit["achterstand"] += len(todo)
        for item in todo:
            try:
                r = await artikel_inhalen(db, item, budget)
            except Exception as e:  # noqa: BLE001 — één artikel mag de ronde niet stoppen
                logger.warning("mp_fotos_inhalen %s: %s", item["id"], e)
                r = "niet_gelukt"
            if r in uit:
                uit[r] += 1
    _stand["klanten"] = nog
    logger.info("mp_fotos_inhalen: %s", uit)
    return uit
