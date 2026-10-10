"""Verkopen in de WooCommerce-winkel zelf opmerken, elke paar minuten.

WAAROM GEEN WEBHOOK. WooCommerce kan een melding sturen bij een bestelling, maar
zet die stil uit na meer dan vijf mislukte afleveringen achter elkaar (filter
woocommerce_max_webhook_delivery_failures, standaard 5), en een herstart van
onze server is al een mislukte aflevering. Daarna merkt niemand iets: het
product blijft op Marktplaats staan en wordt twee keer verkocht. Daarom kijken
we zelf, precies zoals bij Shopify sinds 28-08-2026 (shopify_orders.py): de
bestellingen die sinds de vorige ronde veranderden, en dezelfde afhandeling.

Dubbel zien kan geen kwaad: handle_item_sold slaat over wat al op verkocht staat,
en de voorraadregel telt alleen een nieuwe verkoop.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db, naast_de_lus
from backend.platforms.woocommerce import PLATFORM, WooFout, client_uit

logger = logging.getLogger(__name__)

EERSTE_TERUGBLIK_UREN = 24
OVERLAP_MINUTEN = 10        # klokverschil met de winkel; dubbel is onschadelijk, gemist niet


def regels_uit_bestelling(order: dict) -> list[dict]:
    """Per bestelregel: product, variant, sku en wat er per stuk betaald is."""
    uit = []
    for r in order.get("line_items") or []:
        try:
            aantal = max(int(r.get("quantity") or 1), 1)
            bedrag = (float(r.get("total") or 0) + float(r.get("total_tax") or 0)) / aantal
        except (TypeError, ValueError):
            bedrag = None
        uit.append({
            "product_id": str(r["product_id"]) if r.get("product_id") else None,
            "variation_id": str(r["variation_id"]) if r.get("variation_id") else None,
            "sku": (r.get("sku") or "").strip() or None,
            "price": round(bedrag, 2) if bedrag else None,
        })
    return uit


async def match_verkoop(db, user_id: str, ref: dict) -> str | None:
    """Welk item hoort bij deze bestelregel? None als het niet zeker is.

    1. product_id → de WooCommerce-advertentierij met dat productnummer, van
       deze verkoper;
    2. SKU → het enige item van deze verkoper met die SKU.
    Nooit raden: een verkeerde match haalt een artikel van álle kanalen af."""
    pid = ref.get("product_id")
    if pid:
        rows = ((await naast_de_lus(
            lambda: db.table("listings").select("item_id")
            .eq("platform", PLATFORM).eq("platform_listing_id", pid)
            .limit(10).execute(), herkans=True)).data or [])
        item_ids = {r["item_id"] for r in rows if r.get("item_id")}
        if item_ids:
            eigen = ((await naast_de_lus(
                lambda: db.table("items").select("id").eq("user_id", user_id)
                .in_("id", list(item_ids)).limit(10).execute(), herkans=True)).data or [])
            if len(eigen) == 1:
                return eigen[0]["id"]
    sku = ref.get("sku")
    if sku:
        got = ((await naast_de_lus(
            lambda: db.table("items").select("id")
            .eq("user_id", user_id).eq("sku", sku).limit(2).execute(), herkans=True)).data or [])
        if len(got) == 1:
            return got[0]["id"]
    return None


def _besteldatum(order: dict) -> str | None:
    d = order.get("date_paid_gmt") or order.get("date_created_gmt")
    return (d + "Z") if d and not d.endswith("Z") else d


async def verwerk_bestelling(db, user_id: str, order: dict) -> int:
    """Eén betaalde bestelling afhandelen: de verkochte artikelen elders weghalen.

    Gedeeld door de ronde hieronder en de webhook (winkels die alleen via de
    browser van de klant bereikbaar zijn, services/woocommerce_browser.py)."""
    from backend.platforms.woocommerce import BETAALDE_STATUSSEN
    from backend.services.crosslist import BEWIJS_BESTELLING, handle_item_sold

    if order.get("status") not in BETAALDE_STATUSSEN:
        return 0
    verwerkt = 0
    gezien: set[str] = set()
    for ref in regels_uit_bestelling(order):
        try:
            item_id = await match_verkoop(db, user_id, ref)
            if not item_id or item_id in gezien:
                continue
            gezien.add(item_id)
            await handle_item_sold(item_id, PLATFORM, sold_price=ref.get("price"),
                                   sold_at=_besteldatum(order), bewijs=BEWIJS_BESTELLING)
            verwerkt += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("woocommerce-verkoopcontrole: %s / bestelling %s regel %s: %s",
                           user_id[:8], order.get("id"), ref.get("product_id") or ref.get("sku"), e)
    return verwerkt


async def controleer_winkel(db, rij: dict, nu: datetime) -> int:
    """Eén winkel nalopen. Geeft het aantal afgehandelde verkopen."""
    from backend.services.woocommerce_scan import bewaar_modus

    user_id = rij["user_id"]
    extra = rij.get("extra_data") or {}
    client = client_uit(rij)
    if not client:
        return 0
    gezien_tot = extra.get("orders_gezien_tot")
    sinds = gezien_tot or (nu - timedelta(hours=EERSTE_TERUGBLIK_UREN)).isoformat()
    # WooCommerce wil een tijd zonder zone als dates_are_gmt=true.
    sinds = datetime.fromisoformat(sinds.replace("Z", "+00:00")).astimezone(timezone.utc) \
        .replace(tzinfo=None).isoformat(timespec="seconds")
    try:
        orders = await client.bestellingen(sinds)
    finally:
        await bewaar_modus(db, user_id, client)

    verwerkt = 0
    for order in orders:
        verwerkt += await verwerk_bestelling(db, user_id, order)

    # Merkteken pas na een geslaagde ronde. Opnieuw lezen: andere routines
    # schrijven ook in extra_data (voorraadvlag, inlogmodus).
    nieuw = (nu - timedelta(minutes=OVERLAP_MINUTEN)).isoformat()
    huidig = ((await naast_de_lus(
        lambda: db.table("platform_credentials").select("extra_data")
        .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute(), herkans=True)).data or [])
    basis = (huidig[0].get("extra_data") if huidig else None) or extra
    vorige_fout = basis.pop("verkoop_fout", None)
    if vorige_fout:
        logger.info("woocommerce-verkoopcontrole: %s weer bereikbaar", user_id[:8])
    await naast_de_lus(lambda: db.table("platform_credentials")
                       .update({"extra_data": {**basis, "orders_gezien_tot": nieuw}})
                       .eq("user_id", user_id).eq("platform", PLATFORM).execute(), herkans=True)
    return verwerkt


async def _noteer_fout(db, user_id: str, fout: Exception, nu: datetime) -> None:
    """De eerste mislukte ronde bewaren, zodat een winkel die al uren onbereikbaar
    is te zien is (en niet stil ophoudt met verkopen opmerken)."""
    try:
        huidig = ((await naast_de_lus(
            lambda: db.table("platform_credentials").select("extra_data")
            .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
        extra = (huidig[0].get("extra_data") if huidig else None) or {}
        vorige = extra.get("verkoop_fout") or {}
        await naast_de_lus(lambda: db.table("platform_credentials").update({"extra_data": {
            **extra, "verkoop_fout": {"sinds": vorige.get("sinds") or nu.isoformat(),
                                      "laatst": nu.isoformat(), "reden": str(fout)[:300],
                                      "soort": getattr(fout, "soort", type(fout).__name__)}}})
            .eq("user_id", user_id).eq("platform", PLATFORM).execute())
    except Exception as e:  # noqa: BLE001
        logger.warning("woocommerce-verkoopcontrole: fout niet bewaard voor %s: %s", user_id[:8], e)


async def controleer_woocommerce_verkopen() -> dict:
    """Alle gekoppelde WooCommerce-winkels langslopen. Draait elke 5 minuten."""
    db = get_db()
    try:
        winkels = ((await naast_de_lus(
            lambda: db.table("platform_credentials")
            .select("user_id,access_token,refresh_token,extra_data")
            .eq("platform", PLATFORM).limit(1000).execute(), herkans=True)).data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("woocommerce-verkoopcontrole: kon de winkels niet lezen: %s", e)
        return {"winkels": 0, "verkocht": 0}

    nu = datetime.now(timezone.utc)
    verwerkt = 0
    from backend.services.woocommerce_browser import bereikbaar
    for rij in winkels:
        if not bereikbaar(rij):
            # Alleen via de browser van de klant bereikbaar en die is dicht. Geen
            # storing: verkopen komen via de webhook, en deze ronde haalt de rest
            # in zodra er weer een browser is (het merkteken blijft staan).
            continue
        try:
            verwerkt += await controleer_winkel(db, rij, nu)
        except WooFout as e:
            logger.warning("woocommerce-verkoopcontrole: %s: %s", rij["user_id"][:8], e)
            await _noteer_fout(db, rij["user_id"], e, nu)
        except Exception as e:  # noqa: BLE001
            logger.exception("woocommerce-verkoopcontrole mislukt voor %s", rij["user_id"][:8])
            await _noteer_fout(db, rij["user_id"], e, nu)
    if verwerkt:
        logger.info("woocommerce-verkoopcontrole: %d verkoop/verkopen afgehandeld", verwerkt)
    return {"winkels": len(winkels), "verkocht": verwerkt}
