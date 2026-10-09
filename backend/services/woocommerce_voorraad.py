"""WooCommerce-voorraad als baas, net als bij Shopify (services/shopify_voorraad.py).

DE REGEL, DEZELFDE ALS BIJ SHOPIFY
  - Verkocht in de winkel en er is nog voorraad: niets afmelden, niets als
    verkocht boeken. WooCommerce heeft de voorraad bij de bestelling zelf al
    verlaagd (synchroon, anders dan Shopify's teller die achterloopt).
  - Verkocht elders bij een winkel met voorraad: één stuk van de WooCommerce-
    voorraad af. Is het daarna op, dan gaat het elders offline en blijft het
    product in de winkel staan als uitverkocht.
  - Eén stuk en nooit meer gezien (een uniek tweedehands artikel): het gewone
    gedrag. Verkocht in de winkel haalt het elders weg; verkocht elders zet het
    product in de winkel op uitverkocht (woocommerce.delete_listing, nooit wissen).

Het verschil tussen "het laatste stuk van een voorraadwinkel" en "een uniek
artikel" is niet aan één product te zien; daarvoor is de vlag VLAG op de
koppeling, gezet bij de scan of zodra we ergens meer dan één stuk zien.
"""
from __future__ import annotations

import logging

from backend.database import naast_de_lus
from backend.platforms.woocommerce import PLATFORM, client_uit
from backend.services.shopify_voorraad import BLIJFT, LEVEND, OP, VLAG

logger = logging.getLogger(__name__)

__all__ = ["BLIJFT", "OP", "zet_vlag", "na_verkoop", "totaal"]


async def zet_vlag(db, user_id: str) -> None:
    # Opnieuw lezen vlak voor het schrijven: andere routines schrijven ook in
    # extra_data (merkteken bestellingen, inlogmodus) en mogen niets kwijtraken.
    try:
        rij = ((await naast_de_lus(lambda: db.table("platform_credentials").select("extra_data")
                .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
        if not rij:
            return
        extra = rij[0].get("extra_data") or {}
        if extra.get(VLAG):
            return
        await naast_de_lus(lambda: db.table("platform_credentials")
                           .update({"extra_data": {**extra, VLAG: True}})
                           .eq("user_id", user_id).eq("platform", PLATFORM).execute())
        logger.info("woocommerce-voorraad: %s verkoopt met voorraad, vlag gezet", user_id[:8])
    except Exception as e:  # noqa: BLE001 — de vlag mag een verkoop nooit blokkeren
        logger.warning("woocommerce-voorraad: vlag niet gezet voor %s: %s", user_id[:8], e)


def totaal(product: dict, variaties: list[dict] | None) -> int | None:
    """Stuks over het hele product, of None als ergens geen voorraadbeheer is."""
    if product.get("type") == "variable":
        if not variaties:
            return None
        if any(v.get("manage_stock") is not True for v in variaties):
            return None
        return sum(max(int(v.get("stock_quantity") or 0), 0) for v in variaties)
    if product.get("manage_stock") is not True:
        return None
    return max(int(product.get("stock_quantity") or 0), 0)


async def na_verkoop(db, item_id: str, sold_on_platform: str) -> str | None:
    """BLIJFT, OP, of None (geen voorraad bekend: het gewone gedrag geldt)."""
    rijen = ((await naast_de_lus(lambda: db.table("listings")
              .select("id,platform,status,platform_listing_id")
              .eq("item_id", item_id).execute())).data or [])
    woo = [r for r in rijen if r.get("platform") == PLATFORM and r.get("platform_listing_id")
           and r.get("status") != "delisted"]
    if not woo:
        return None
    product_id = str(sorted(woo, key=lambda r: r.get("status") != "active")[0]["platform_listing_id"])

    item = ((await naast_de_lus(lambda: db.table("items").select("user_id")
             .eq("id", item_id).limit(1).execute())).data or [None])[0]
    user_id = (item or {}).get("user_id")
    if not user_id:
        return None
    cred = ((await naast_de_lus(lambda: db.table("platform_credentials").select("*")
             .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
    if not cred:
        return None
    gevlagd = bool((cred[0].get("extra_data") or {}).get(VLAG))
    client = client_uit(cred[0])
    if not client:
        return None

    try:
        product = await client.product(product_id)
        variaties = (await client.variaties(product_id)
                     if product and product.get("type") == "variable" else None)
    except Exception as e:  # noqa: BLE001
        # Bij een voorraadwinkel is niets doen de veilige kant: een advertentie
        # te lang laten staan is te herstellen, een verdwenen product niet.
        logger.warning("woocommerce-voorraad: kon %s niet lezen voor item %s: %s",
                       product_id, item_id, e)
        return BLIJFT if gevlagd else None
    finally:
        from backend.services.woocommerce_scan import bewaar_modus
        await bewaar_modus(db, user_id, client)
    if product is None or product.get("status") == "trash":
        return None     # product bestaat niet meer: gewoon gedrag

    stuks = totaal(product, variaties)
    if stuks is None:
        return BLIJFT if gevlagd else None
    meer_dan_een = stuks > 1 or (variaties is not None and len(variaties) > 1)
    if meer_dan_een and not gevlagd:
        await zet_vlag(db, user_id)
        gevlagd = True

    if sold_on_platform == PLATFORM:
        # De bestelling heeft de voorraad al verlaagd. Wat er nu staat is na de
        # verkoop: iets over is blijven, niets over is op.
        if stuks > 0:
            return BLIJFT
        return OP if gevlagd else None

    if not gevlagd:
        return None     # uniek artikel: gewoon gedrag, winkel naar uitverkocht

    # Alleen een NIEUWE verkoop haalt een stuk af. Staat er op het verkoopkanaal
    # geen levende advertentie meer, dan is dit een herhaalde melding.
    nieuw = any(r.get("platform") == sold_on_platform and r.get("status") in LEVEND for r in rijen)
    if nieuw:
        if variaties is None:
            if stuks > 0 and await _een_eraf(client, product_id, None, stuks, item_id,
                                             sold_on_platform):
                stuks -= 1
        else:
            met_voorraad = [v for v in variaties if int(v.get("stock_quantity") or 0) > 0]
            if len(met_voorraad) == 1:
                v = met_voorraad[0]
                if await _een_eraf(client, product_id, str(v["id"]),
                                   int(v.get("stock_quantity") or 0), item_id, sold_on_platform):
                    stuks -= 1
            elif len(met_voorraad) > 1:
                logger.info("woocommerce-voorraad: item %s heeft %d maten met voorraad; welke er op "
                            "%s verkocht is weten we niet, voorraad blijft staan",
                            item_id, len(met_voorraad), sold_on_platform)
    return BLIJFT if stuks > 0 else OP


async def _een_eraf(client, product_id: str, variatie: str | None, nu: int,
                    item_id: str, kanaal: str) -> bool:
    """Eén stuk eraf. True als de winkel het aannam."""
    try:
        await client.werk_bij(product_id, {"stock_quantity": max(nu - 1, 0)}, variatie=variatie)
        logger.info("woocommerce-voorraad: item %s verkocht op %s, product %s%s nu %d stuks",
                    item_id, kanaal, product_id, f"/{variatie}" if variatie else "", max(nu - 1, 0))
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("woocommerce-voorraad: stuk eraf mislukt voor %s: %s", product_id, e)
        return False
