"""Vangnet: een verkocht artikel dat ergens anders tóch nog te koop staat.

WAAROM DIT ER IS
`handle_item_sold` meldt een verkocht artikel meteen af bij alle andere kanalen:
API-kanalen (Shopify, eBay) rechtstreeks, extensie-kanalen (Marktplaats,
2dehands, Vinted, Facebook) via een verwijderopdracht die in de browser van de
verkoper draait. Elk van die stappen kan stil mislukken:

  * de verwijderopdracht komt op 'error' te staan (advertentie niet gevonden,
    sessie verlopen) en niets probeert hem opnieuw;
  * de browser van de verkoper stond dagen uit, de opdracht verliep;
  * de Shopify-advertentierij had geen product-id, dus de API-verwijdering
    vond niets;
  * de verkoop werd pas laat opgemerkt en er was intussen al opnieuw geplaatst.

In al die gevallen is het artikel op één kanaal verkocht en staat het op een
ander kanaal gewoon te koop: precies het dubbelverkoop-risico dat we beloven weg
te nemen. Deze ronde kijkt elke 20 minuten of dat ergens zo is en zet de
afmelding opnieuw in gang. Veilig, want er is al een bevestigde 'sold'-rij: dit
raadt niets, het maakt alleen af wat al had moeten gebeuren.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus, IN_BROK

logger = logging.getLogger(__name__)

# Hoe ver terug we verkopen meenemen. Alles wat binnen deze week niet is
# opgeruimd, ruimt deze ronde alsnog op. Ouder dan dat en het is geen storing
# meer maar geschiedenis.
TERUGBLIK_DAGEN = 7

# Speling na de verkoop voordat we ingrijpen: de gewone afmelding (en de
# extensie) krijgen eerst de kans. Onder deze grens laten we het met rust.
RESPIJT_MINUTEN = 20

# Hooguit zoveel artikelen per ronde echt aanpakken, oudste verkoop eerst, zodat
# één ronde altijd afloopt en de databaseverbinding het aankan.
PER_RONDE = 40

# Statussen waarin een advertentie nog op het platform kan staan.
_NOG_LEVEND = ("active", "error", "relisting", "hidden", "pending")


async def reconcileer_verkochte_artikelen() -> dict:
    db = get_db()
    grens = (datetime.now(timezone.utc) - timedelta(days=TERUGBLIK_DAGEN)).isoformat()
    respijt = datetime.now(timezone.utc) - timedelta(minutes=RESPIJT_MINUTEN)

    try:
        verkocht = ((await naast_de_lus(
            lambda: db.table("listings")
            .select("item_id,platform,sold_at")
            .eq("status", "sold")
            .gte("sold_at", grens)
            .order("sold_at", desc=False)
            .limit(1500)
            .execute(), herkans=True)).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("verkoop-reconciliatie: kon de verkopen niet lezen: %s", e)
        return {"bekeken": 0, "opnieuw_ingezet": 0}

    if not verkocht:
        return {"bekeken": 0, "opnieuw_ingezet": 0}

    # Per artikel: wanneer was de (vroegste) verkoop, en op welke kanalen.
    verkoop_van: dict[str, dict] = {}
    for r in verkocht:
        iid = r.get("item_id")
        if not iid:
            continue
        d = verkoop_van.setdefault(iid, {"sold_at": r.get("sold_at"), "platforms": set()})
        d["platforms"].add(r["platform"])
        if r.get("sold_at") and (not d["sold_at"] or r["sold_at"] < d["sold_at"]):
            d["sold_at"] = r["sold_at"]

    item_ids = list(verkoop_van.keys())

    # Alle advertentierijen van die artikelen ophalen, in brokken (een te lange
    # .in_() maakt een URL die stilletjes wordt geweigerd — zie IN_BROK).
    rijen_per_item: dict[str, list[dict]] = {}
    for i in range(0, len(item_ids), IN_BROK):
        brok = item_ids[i:i + IN_BROK]
        try:
            rows = ((await naast_de_lus(
                lambda: db.table("listings")
                .select("item_id,platform,status,platform_listing_id")
                .in_("item_id", brok).execute(), herkans=True)).data or [])
        except Exception as e:  # noqa: BLE001
            logger.warning("verkoop-reconciliatie: listings-brok overgeslagen: %s", e)
            continue
        for row in rows:
            rijen_per_item.setdefault(row["item_id"], []).append(row)

    # Kandidaten: verkocht op kanaal A, nog levend op kanaal B, verkoop oud genoeg.
    kandidaten: list[tuple[str, str]] = []  # (sold_at, item_id) voor sortering
    for iid, info in verkoop_van.items():
        try:
            verkocht_op_dt = datetime.fromisoformat((info["sold_at"] or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            verkocht_op_dt = respijt - timedelta(minutes=1)  # geen datum: behandel als oud
        if verkocht_op_dt > respijt:
            continue
        nog_levend = [
            r for r in rijen_per_item.get(iid, [])
            if r["platform"] not in info["platforms"] and r.get("status") in _NOG_LEVEND
        ]
        if nog_levend:
            kandidaten.append((info["sold_at"] or "", iid))

    kandidaten.sort()
    kandidaten = kandidaten[:PER_RONDE]

    if not kandidaten:
        return {"bekeken": len(item_ids), "opnieuw_ingezet": 0}

    # Eigenaren erbij zoeken (delist_all_platforms wil het user_id).
    doel_ids = [iid for _, iid in kandidaten]
    eigenaar: dict[str, str] = {}
    for i in range(0, len(doel_ids), IN_BROK):
        brok = doel_ids[i:i + IN_BROK]
        rows = ((await naast_de_lus(
            lambda: db.table("items").select("id,user_id").in_("id", brok).execute(),
            herkans=True)).data or [])
        for row in rows:
            eigenaar[row["id"]] = row["user_id"]

    from backend.services.crosslist import delist_all_platforms

    opnieuw = 0
    for _, iid in kandidaten:
        uid = eigenaar.get(iid)
        if not uid:
            continue
        levend = [
            r["platform"] for r in rijen_per_item.get(iid, [])
            if r["platform"] not in verkoop_van[iid]["platforms"] and r.get("status") in _NOG_LEVEND
        ]
        try:
            res = await delist_all_platforms(iid, uid)
            opnieuw += 1
            logger.info(
                "verkoop-reconciliatie: item %s was verkocht op %s maar stond nog op %s "
                "— afmelding opnieuw ingezet: %s",
                iid, sorted(verkoop_van[iid]["platforms"]), sorted(set(levend)),
                [(x.get("platform"), x.get("status")) for x in (res or [])],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("verkoop-reconciliatie: item %s afmelden mislukte: %s", iid, e)

    logger.info("verkoop-reconciliatie: %d artikel(en) bekeken, %d opnieuw ingezet",
                len(item_ids), opnieuw)
    return {"bekeken": len(item_ids), "opnieuw_ingezet": opnieuw}
