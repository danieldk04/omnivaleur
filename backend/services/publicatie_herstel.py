"""Een publicatie die halverwege werd afgekapt alsnog afmaken.

WAAROM DIT ER IS (18-09-2026, gemeten op Daniels eigen account).

Marktplaats, 2dehands en Vinted worden gepubliceerd door een opdracht klaar te
zetten die de extensie oppakt: valt de server halverwege weg, dan staat die
opdracht er nog steeds en gebeurt het alsnog. Shopify en eBay lopen niet via de
extensie maar rechtstreeks vanuit het verzoek zelf. Wordt dát verzoek afgekapt,
dan blijft de advertentierij op 'pending' zonder advertentienummer staan, zegt
het dashboard eeuwig "Publishing…" en gebeurt er nooit meer iets.

En afgekapt worden gebeurt. Railway geeft een oude deployment standaard NUL
seconden om af te ronden: bij elke nieuwe versie krijgt het proces een SIGTERM
en meteen daarna een SIGKILL (railway.json zet dat nu op `drainingSeconds`).
GEMETEN: op 18-09-2026 om 16:15:32 UTC drukte Daniel op publiceren voor
"(1370) Navy Quechua Trousers". De drie extensie-opdrachten werden klaargezet
(16:15:32 tot 16:15:34), de Shopify-rij werd aangemaakt om 16:15:34.9, en daarna
hield het op: in de winkel zelf bestond geen product met SKU 1370. In dezelfde
minuten deed de server ook zijn eigen achtergrondwerk niet (de statuscontrole
schreef van 16:13:57 tot 16:16:27 niets weg) — precies het gat waarin de nieuwe
versie live ging.

Deze ronde maakt dat werk alsnog af, zonder te gokken:
  1. Staat het product tóch al in de winkel (het verzoek werd ná het aanmaken
     afgekapt), dan koppelen we alleen de rij. Dat is precies wat
     reconcile_shopify_catalog doet, op SKU en merk.
  2. Staat het er niet, dan publiceren we alsnog — dezelfde weg als de knop.
  3. Lukt geen van beide, dan komt er een leesbare fout op de rij te staan.
     Een zichtbare fout is altijd beter dan een "Publishing…" die nooit overgaat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus

logger = logging.getLogger(__name__)

# Een publicatie naar Shopify of eBay duurt seconden, met foto's hooguit een
# halve minuut. Staat de rij na tien minuten nog op 'pending' zonder
# advertentienummer, dan bestaat het verzoek dat hem klaarzette niet meer.
AFGEKAPT_NA_MINUTEN = 10
MAX_PER_RONDE = 25


async def _meld(db, rij_id: str, tekst: str) -> None:
    """De rij uit 'Publishing…' halen en zeggen wat er misging."""
    await naast_de_lus(lambda: db.table("listings").update(
        {"status": "error", "error_message": tekst}).eq("id", rij_id)
        .eq("status", "pending").is_("platform_listing_id", "null").execute())


async def hervat_afgekapte_api_publicaties() -> dict:
    from backend.services.crosslist import API_PLATFORMS

    db = get_db()
    grens = (datetime.now(timezone.utc)
             - timedelta(minutes=AFGEKAPT_NA_MINUTEN)).isoformat()
    try:
        rijen = ((await naast_de_lus(lambda: db.table("listings")
                 .select("id,item_id,platform,created_at")
                 .in_("platform", sorted(API_PLATFORMS))
                 .eq("status", "pending")
                 .is_("platform_listing_id", "null")
                 .lt("created_at", grens)
                 .order("created_at")
                 .limit(MAX_PER_RONDE).execute())).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("herstel afgekapte publicaties: kon de rijen niet lezen: %s", e)
        return {"gekoppeld": 0, "hervat": 0, "gemeld": 0}

    gekoppeld = hervat = gemeld = 0
    afgestemd: set[str] = set()      # één catalogusronde per verkoper is genoeg
    for rij in rijen:
        try:
            uit = await _hervat_een(db, rij, afgestemd)
        except Exception as e:  # noqa: BLE001 — één rij mag de rest niet blokkeren
            logger.warning("herstel afgekapte publicaties: rij %s mislukte: %s", rij["id"], e)
            continue
        gekoppeld += uit[0]
        hervat += uit[1]
        gemeld += uit[2]

    if gekoppeld or hervat or gemeld:
        logger.info(
            "herstel afgekapte publicaties: %d gekoppeld aan een bestaand product, "
            "%d alsnog gepubliceerd, %d als fout gemeld (van %d vastgelopen rij(en))",
            gekoppeld, hervat, gemeld, len(rijen),
        )
    return {"gekoppeld": gekoppeld, "hervat": hervat, "gemeld": gemeld,
            "gevonden": len(rijen)}


async def _hervat_een(db, rij: dict, afgestemd: set[str]) -> tuple[int, int, int]:
    from backend.services.crosslist import CrosslistValidationError, publish_to_platforms

    platform = rij["platform"]
    item = ((await naast_de_lus(lambda: db.table("items")
            .select("id,user_id,sku,title").eq("id", rij["item_id"])
            .limit(1).execute())).data or [None])[0]
    if not item:
        # Het artikel bestaat niet meer (verwijderd of samengevoegd). Dan is dit
        # alleen nog een "Publishing…" zonder artikel eronder.
        await naast_de_lus(lambda: db.table("listings").delete().eq("id", rij["id"]).execute())
        logger.info("herstel: advertentierij %s opgeruimd, het artikel bestaat niet meer", rij["id"])
        return (0, 0, 0)

    gekoppeld_bij = ((await naast_de_lus(lambda: db.table("platform_credentials")
                     .select("id").eq("user_id", item["user_id"]).eq("platform", platform)
                     .limit(1).execute())).data or [])
    if not gekoppeld_bij:
        await _meld(db, rij["id"],
                    f"{platform.capitalize()} isn't connected any more, so this never went live. "
                    f"Connect it under Platforms and press Publish again.")
        return (0, 0, 1)

    # 1. HET PRODUCT KAN ER AL STAAN. Het verzoek kan ook ná het aanmaken zijn
    #    afgekapt; dan is opnieuw publiceren een tweede product in de winkel.
    if platform == "shopify" and item["user_id"] not in afgestemd:
        afgestemd.add(item["user_id"])
        try:
            from backend.services.shopify_reconcile import reconcile_shopify_catalog
            await reconcile_shopify_catalog(item["user_id"])
        except Exception as e:  # noqa: BLE001
            logger.warning("herstel: catalogusronde mislukte voor %s: %s", item["user_id"], e)
    nu = ((await naast_de_lus(lambda: db.table("listings")
          .select("status,platform_listing_id").eq("id", rij["id"])
          .limit(1).execute())).data or [None])[0]
    if not nu or nu.get("platform_listing_id") or nu.get("status") != "pending":
        return (1, 0, 0) if nu and nu.get("platform_listing_id") else (0, 0, 0)

    # 2. HET STAAT ER ECHT NIET. Alsnog publiceren, langs precies dezelfde weg
    #    als de knop: mét de dubbelcontrole op tweelingen, dus nooit een tweede
    #    advertentie voor hetzelfde voorwerp.
    try:
        uitkomsten = await publish_to_platforms(item["id"], [platform], item["user_id"])
    except CrosslistValidationError as e:
        velden = ", ".join(sorted(e.missing.get(platform, []) or [])) or "some fields"
        await _meld(db, rij["id"],
                    f"This never went live: {velden} still missing. "
                    f"Fill it in and press Publish again.")
        return (0, 0, 1)
    except Exception as e:  # noqa: BLE001
        await _meld(db, rij["id"],
                    f"This never went live ({type(e).__name__}). Press Publish again.")
        return (0, 0, 1)

    geslaagd = any(u.get("status") in ("active", "already_live") for u in uitkomsten)
    if geslaagd:
        logger.info("herstel: %s alsnog op %s gepubliceerd", item["id"], platform)
        return (0, 1, 0)

    # DE RIJ MOET ALTIJD UIT 'pending' KOMEN, ook als publish_to_platforms er
    # niet aan toe kwam. Wordt het kanaal geweigerd omdat hetzelfde voorwerp er
    # al onder een dubbele rij op staat (status 'duplicate'), of omdat het kanaal
    # op pauze staat ('blocked'), dan raakt die weigering onze rij niet aan —
    # en dan zou deze ronde hem elke tien minuten opnieuw proberen, voor altijd.
    achtergebleven = ((await naast_de_lus(lambda: db.table("listings")
                      .select("status,platform_listing_id").eq("id", rij["id"])
                      .limit(1).execute())).data or [None])[0]
    if achtergebleven and achtergebleven.get("status") == "pending" \
            and not achtergebleven.get("platform_listing_id"):
        reden = next((u.get("error") or u.get("message") for u in uitkomsten
                      if u.get("error") or u.get("message")), None)
        await _meld(db, rij["id"], reden or "This never went live. Press Publish again.")
    # Anders heeft _publish_one de rij zelf al op 'error' met de echte reden gezet.
    return (0, 0, 1)
