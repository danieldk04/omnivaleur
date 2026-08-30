"""Twee items die hetzelfde product zijn, als één product behandelen.

WAAROM DIT BESTAAT (30-08-2026)
Bij het importeren ontstaan tweelingen: dezelfde trui komt één keer binnen via
Marktplaats en één keer via Vinted, en dat worden twee rijen in `items`. Ze zijn
herkenbaar aan het nummer dat de verkoper zelf voor de titel zet — "(1237) Navy
Suitsupply Half Zip" — maar ze worden nooit samengevoegd.

Gemeten bij Daniel: item A stond op Vinted VERKOCHT (21-08), item B was dezelfde
trui en werd daarna gewoon opnieuw op Marktplaats gezet. Elke controle keek naar
één rij en zag geen verkoop. Datzelfde nummer zorgde er ook voor dat een live
Vinted-advertentie aan geen van beide rijen gekoppeld kon worden — twee kandidaten
is geen koppeling — waardoor het dashboard "staat niet op Vinted" toonde terwijl
de advertentie er gewoon stond.

Deze module levert de enige twee dingen die daarvoor nodig zijn: het nummer van
een item, en alle item-id's die datzelfde nummer dragen.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Alleen een nummer waar veilig op te zoeken valt. Alles daarbuiten (spaties,
# haakjes, komma's) laten we lopen: dan is er gewoon geen familie.
_VEILIG = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def nummer_van(item: dict) -> str:
    """Het eigen nummer van de verkoper: uit het SKU-veld, anders uit de titel."""
    sku = str((item or {}).get("sku") or "").strip().lower()
    if sku and _VEILIG.match(sku):
        return sku
    m = re.match(r"^\s*\(([^)]{1,24})\)", str((item or {}).get("title") or ""))
    kandidaat = (m.group(1).strip().lower() if m else "")
    return kandidaat if _VEILIG.match(kandidaat or " ") else ""


def familie_ids(db, item: dict) -> list[str]:
    """Alle item-id's van deze verkoper met hetzelfde nummer, inclusief dit item.

    Eén gerichte vraag aan de database, geen volledige voorraad ophalen: dit
    draait in de uitdeelronde en bij elke verkoop.
    """
    eigen = (item or {}).get("id")
    nummer = nummer_van(item)
    user_id = (item or {}).get("user_id")
    if not (eigen and nummer and user_id):
        return [eigen] if eigen else []
    try:
        rijen = (db.table("items").select("id")
                 .eq("user_id", user_id)
                 .or_(f"sku.eq.{nummer},title.ilike.({nummer})%")
                 .limit(50).execute().data or [])
    except Exception as e:  # noqa: BLE001 — bij twijfel alleen het item zelf
        logger.warning("tweelingen: kon familie van %s niet lezen: %s", eigen, e)
        return [eigen]
    ids = [r["id"] for r in rijen if r.get("id")]
    return list(dict.fromkeys([eigen, *ids]))
