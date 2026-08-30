"""Verkopen op Shopify zelf opmerken, zonder webhook.

WAAROM DIT ER IS (28-08-2026)
Shopify accepteert geen apps meer die koppelen met een marktplaats buiten
Shopify. Winkeliers koppelen daarom voortaan met een app die ze in hun eigen
Shopify-organisatie maken. Dat werkt voor importeren en publiceren precies
hetzelfde — maar niet voor de verkoopmelding: die liep over een webhook
(`orders/paid`) die alleen bij ÓNZE app hoort en bij hun app nooit binnenkomt.

Zonder deze ronde zou een winkelier dus stilletjes de belangrijkste functie
kwijtraken: verkoopt hij iets in zijn eigen winkel, dan blijft het op
Marktplaats, Vinted en eBay gewoon te koop staan en kan het dubbel verkocht
worden. Precies het soort stille storing dat hier al vaker weken heeft geduurd.

Daarom kijken we het zelf na: elke paar minuten de betaalde bestellingen sinds de
vorige keer ophalen en dezelfde afhandeling draaien als de webhook deed. Dit
draait voor ÁLLE gekoppelde winkels, ook die nog via de knop gekoppeld zijn —
dan is de webhook een snellere eerste melding en is dit het vangnet. Dubbel
afhandelen kan geen kwaad: handle_item_sold slaat over wat al op verkocht staat.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus

logger = logging.getLogger(__name__)

# Hoe ver we terugkijken als een winkel nog geen merkteken heeft (net gekoppeld,
# of deze ronde draaide nog nooit). Ruim genoeg om een gemiste dag op te vangen,
# krap genoeg om niet de hele geschiedenis als "zojuist verkocht" te behandelen.
EERSTE_TERUGBLIK_UREN = 24

# Overlap op het merkteken. Shopify's `updated_at_min` filtert op de klok van
# Shopify; een paar minuten speling voorkomt dat een bestelling precies op de
# grens ertussenuit valt. Dubbel gezien is onschadelijk, gemist niet.
OVERLAP_MINUTEN = 5


async def _bestellingen(shop: str, token: str, sinds: str) -> list[dict]:
    import httpx

    url = (f"https://{shop}/admin/api/2024-01/orders.json"
           f"?status=any&financial_status=paid&updated_at_min={sinds}&limit=250")
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as c:
        r = await c.get(url, headers=headers)
        if r.status_code in (401, 403):
            # De sleutel is ingetrokken of mist read_orders. Dat is geen storing
            # van deze ronde maar iets wat de winkelier moet weten; loggen en door
            # met de volgende winkel.
            raise PermissionError(f"{shop}: geen toegang tot bestellingen ({r.status_code})")
        r.raise_for_status()
        return r.json().get("orders", [])


async def controleer_shopify_verkopen() -> dict:
    """Alle gekoppelde Shopify-winkels langslopen en verkopen afhandelen."""
    from backend.platforms.shopify import (extract_skus_from_order,
                                           extract_sku_prices_from_order)
    from backend.services.crosslist import handle_item_sold

    db = get_db()
    try:
        winkels = ((await naast_de_lus(
            lambda: db.table("platform_credentials")
            .select("user_id,access_token,extra_data")
            .eq("platform", "shopify").limit(500).execute(), herkans=True)).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("shopify-verkoopcontrole: kon de winkels niet lezen: %s", e)
        return {"winkels": 0, "verkocht": 0}

    nu = datetime.now(timezone.utc)
    verwerkt = 0

    for rij in winkels:
        extra = rij.get("extra_data") or {}
        # Via _shop_creds, niet rechtstreeks uit de rij: bij een eigen app van de
        # winkelier verloopt de sleutel na 24 uur en moet hij hier ververst
        # worden. Dat rechtstreeks lezen zou deze ronde elke dag stil laten
        # vastlopen op 401 — precies de stille storing die we willen vermijden.
        from backend.platforms.shopify import _shop_creds
        try:
            shop, token = await _shop_creds({**rij, "user_id": rij["user_id"]})
        except Exception as e:  # noqa: BLE001
            logger.warning("shopify-verkoopcontrole: geen sleutel voor %s: %s",
                           extra.get("shop_domain") or rij["user_id"][:8], e)
            continue
        # De oudste koppeling draaide op één winkel uit de serverinstellingen en
        # heeft geen eigen domein opgeslagen. Die kunnen we hier niet nakijken;
        # overslaan is beter dan een gok op de verkeerde winkel.
        if not shop or not token or token == "session":
            continue

        gezien = extra.get("orders_gezien_tot")
        sinds = gezien or (nu - timedelta(hours=EERSTE_TERUGBLIK_UREN)).isoformat()

        try:
            orders = await _bestellingen(shop, token, sinds)
        except PermissionError as e:
            logger.warning("shopify-verkoopcontrole: %s", e)
            continue
        except Exception as e:  # noqa: BLE001
            logger.warning("shopify-verkoopcontrole: %s gaf een fout: %s", shop, e)
            continue

        for order in orders:
            skus = extract_skus_from_order(order)
            if not skus:
                continue
            prijzen = extract_sku_prices_from_order(order)
            # De ECHTE besteldatum. Deze ronde kijkt bewust terug in de tijd (bij
            # een nieuwe koppeling 24 uur, na een storing langer), dus zonder deze
            # datum zou elke ingehaalde bestelling als "vandaag verkocht" in de
            # omzet belanden.
            besteld_op = order.get("processed_at") or order.get("created_at")
            for sku in skus:
                try:
                    # LET OP: altijd op user_id filteren. Twee winkeliers kunnen
                    # dezelfde SKU gebruiken (1, 001, een artikelnummer), en dan
                    # zou een verkoop bij de een de advertenties van de ander
                    # overal weghalen.
                    treffer = ((await naast_de_lus(
                        lambda: db.table("items").select("id")
                        .eq("user_id", rij["user_id"]).eq("sku", sku)
                        .limit(1).execute(), herkans=True)).data or [])
                    if not treffer:
                        continue
                    await handle_item_sold(treffer[0]["id"], "shopify",
                                           sold_price=prijzen.get(sku),
                                           sold_at=besteld_op)
                    verwerkt += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("shopify-verkoopcontrole: %s / sku %s: %s", shop, sku, e)

        # Merkteken pas bijwerken als deze winkel helemaal gelukt is. Brak er
        # iets af, dan kijken we volgende ronde dezelfde periode nog eens na —
        # liever twee keer dan een gemiste verkoop.
        nieuw = (nu - timedelta(minutes=OVERLAP_MINUTEN)).isoformat()
        try:
            # OPNIEUW LEZEN, niet `extra` hergebruiken. _shop_creds kan hierboven
            # net een verse sleutel hebben opgehaald en weggeschreven; schrijven
            # we dan de oude `extra` terug, dan wissen we die vervaldatum weer en
            # halen we elke ronde onnodig een nieuwe sleutel op — of erger, we
            # zetten er een verlopen datum overheen.
            huidig = ((await naast_de_lus(
                lambda: db.table("platform_credentials").select("extra_data")
                .eq("user_id", rij["user_id"]).eq("platform", "shopify")
                .limit(1).execute(), herkans=True)).data or [])
            basis = (huidig[0].get("extra_data") if huidig else None) or extra
            (await naast_de_lus(
                lambda: db.table("platform_credentials")
                .update({"extra_data": {**basis, "orders_gezien_tot": nieuw}})
                .eq("user_id", rij["user_id"]).eq("platform", "shopify").execute(),
                herkans=True))
        except Exception as e:  # noqa: BLE001
            logger.warning("shopify-verkoopcontrole: merkteken van %s niet bijgewerkt: %s", shop, e)

    if verwerkt:
        logger.info("shopify-verkoopcontrole: %d verkoop/verkopen afgehandeld", verwerkt)
    return {"winkels": len(winkels), "verkocht": verwerkt}
