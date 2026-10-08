"""Shopify-voorraad als baas, voor verkopers met meer dan één stuk per artikel.

WAAROM DIT ER IS (08-10-2026, Goudlief 5aae4954, Daniel: "bouw dat in")
De verkoopafhandeling (crosslist.handle_item_sold) ging ervan uit dat elk
artikel uniek is: verkocht = overal weg. Voor een winkel met voorraad gaat dat
op twee manieren mis:
  1. Verkoop in de eigen Shopify-winkel: Omnivaleur haalde Marktplaats en
     2dehands offline en boekte het artikel als verkocht, terwijl er nog 40 lagen.
  2. Verkoop op Marktplaats of 2dehands: Omnivaleur WISTE het hele product uit de
     Shopify-winkel (delete_product), met alle voorraad, foto's en varianten.

GEMETEN 08-10-2026 bij Goudlief: 4.919 producten, 3.907 met meer dan 5 stuks,
alle varianten met voorraadbeheer aan. De 8 "verkochte" artikelen hadden nog
9 tot 123 stuks.

DE REGEL
  - Verkocht in Shopify en er is nog voorraad: niets afmelden, niets als
    verkocht boeken. Shopify heeft de voorraad zelf al verlaagd.
  - Verkocht elders bij een winkel met voorraad: één stuk van de Shopify-voorraad
    af, het product blijft. Is het daarna op, dan gaat het elders offline maar
    blijft het Shopify-product staan (uitverkocht), zodat het aangevuld kan worden.
  - Eén stuk en nooit meer gezien: precies het oude gedrag. Daarvoor is de vlag
    `voorraad_meerdere` in platform_credentials.extra_data: zonder die vlag kunnen
    we het laatste stuk van een voorraadwinkel niet onderscheiden van een uniek
    tweedehands artikel, en dan zou het laatste stuk het product alsnog wissen.

Een variant raden doen we niet: heeft een product meerdere varianten met
voorraad, dan weten we niet welke er elders verkocht is. Dan blijft de voorraad
staan en past de verkoper hem zelf aan; alles blijft online.
"""
from __future__ import annotations

import logging

from backend.database import naast_de_lus

logger = logging.getLogger(__name__)

API_VERSIE = "2024-01"
VLAG = "voorraad_meerdere"

BLIJFT = "blijft"   # er is nog voorraad: niets afmelden, niets als verkocht boeken
OP = "op"           # voorraad nu op: elders afmelden, Shopify-product NIET wissen

LEVEND = ("active", "relisting", "hidden", "sold_unconfirmed", "pending")


def totaal(varianten: list[dict]) -> int | None:
    """Stuks over alle varianten, of None als er een variant zonder voorraadbeheer is."""
    if not varianten:
        return None
    if any(v.get("inventory_management") != "shopify" for v in varianten):
        return None
    return sum(max(int(v.get("inventory_quantity") or 0), 0) for v in varianten)


async def lees_varianten(shop: str, token: str, product_id: str) -> list[dict] | None:
    import httpx
    url = f"https://{shop}/admin/api/{API_VERSIE}/products/{product_id}.json?fields=id,variants"
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as c:
        r = await c.get(url, headers={"X-Shopify-Access-Token": token})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return (r.json().get("product") or {}).get("variants") or []


async def een_stuk_eraf(shop: str, token: str, variant: dict) -> bool:
    """Eén stuk van de locatie met de meeste voorraad. True als Shopify het aannam."""
    import httpx
    basis = f"https://{shop}/admin/api/{API_VERSIE}"
    kop = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    item_id = variant.get("inventory_item_id")
    if not item_id:
        return False
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as c:
        r = await c.get(f"{basis}/inventory_levels.json?inventory_item_ids={item_id}", headers=kop)
        r.raise_for_status()
        niveaus = [n for n in r.json().get("inventory_levels") or []
                   if int(n.get("available") or 0) > 0]
        if not niveaus:
            return False
        plek = max(niveaus, key=lambda n: int(n.get("available") or 0))
        r = await c.post(f"{basis}/inventory_levels/adjust.json", headers=kop, json={
            "location_id": plek["location_id"], "inventory_item_id": item_id,
            "available_adjustment": -1})
    if r.status_code >= 400:
        logger.warning("shopify-voorraad: aanpassen geweigerd (%s): %s", r.status_code, r.text[:200])
        return False
    return True


async def _zet_vlag(db, user_id: str) -> None:
    # Opnieuw lezen vlak voor het schrijven: andere routines schrijven ook in
    # extra_data (merkteken bestellingen, verse sleutel) en mogen niets kwijtraken.
    try:
        rij = ((await naast_de_lus(lambda: db.table("platform_credentials").select("extra_data")
                .eq("user_id", user_id).eq("platform", "shopify").limit(1).execute())).data or [])
        extra = (rij[0].get("extra_data") if rij else None) or {}
        if extra.get(VLAG):
            return
        await naast_de_lus(lambda: db.table("platform_credentials")
                           .update({"extra_data": {**extra, VLAG: True}})
                           .eq("user_id", user_id).eq("platform", "shopify").execute())
        logger.info("shopify-voorraad: %s verkoopt met voorraad, vlag gezet", user_id[:8])
    except Exception as e:  # noqa: BLE001 — de vlag mag een verkoop nooit blokkeren
        logger.warning("shopify-voorraad: vlag niet gezet voor %s: %s", user_id[:8], e)


async def markeer_als_voorraadwinkel(db, user_id: str, producten: list[dict]) -> None:
    """Bij de import: heeft een product meer dan één stuk, dan is dit een voorraadwinkel."""
    if any((totaal(p.get("variants") or []) or 0) > 1 for p in producten):
        await _zet_vlag(db, user_id)


async def na_verkoop(db, item_id: str, sold_on_platform: str) -> str | None:
    """BLIJFT, OP, of None (geen voorraad bekend: het oude gedrag geldt)."""
    rijen = ((await naast_de_lus(lambda: db.table("listings")
              .select("id,platform,status,platform_listing_id")
              .eq("item_id", item_id).execute())).data or [])
    shopify = [r for r in rijen if r.get("platform") == "shopify" and r.get("platform_listing_id")
               and r.get("status") != "delisted"]
    if not shopify:
        return None
    product_id = str(sorted(shopify, key=lambda r: r.get("status") != "active")[0]["platform_listing_id"])

    item = ((await naast_de_lus(lambda: db.table("items").select("user_id")
             .eq("id", item_id).limit(1).execute())).data or [None])[0]
    user_id = (item or {}).get("user_id")
    if not user_id:
        return None
    cred = ((await naast_de_lus(lambda: db.table("platform_credentials").select("*")
             .eq("user_id", user_id).eq("platform", "shopify").limit(1).execute())).data or [])
    if not cred:
        return None
    gevlagd = bool((cred[0].get("extra_data") or {}).get(VLAG))

    try:
        from backend.platforms.shopify import _shop_creds
        shop, token = await _shop_creds({**cred[0], "user_id": user_id})
        varianten = await lees_varianten(shop, token, product_id) if (shop and token) else None
    except Exception as e:  # noqa: BLE001
        # Bij een voorraadwinkel is niets doen de veilige kant: een advertentie
        # te lang laten staan is te herstellen, een gewist product niet.
        logger.warning("shopify-voorraad: kon %s niet lezen voor item %s: %s", product_id, item_id, e)
        return BLIJFT if gevlagd else None
    if varianten is None:
        return None     # product bestaat niet meer in Shopify: oud gedrag

    stuks = totaal(varianten)
    if stuks is None:
        return BLIJFT if gevlagd else None
    if stuks > 1 and not gevlagd:
        await _zet_vlag(db, user_id)
        gevlagd = True

    if sold_on_platform == "shopify":
        # Shopify verlaagt de voorraad bij de bestelling zelf, maar de teller op
        # de variant loopt een paar seconden achter (GEMETEN 08-10-2026: na een
        # aanpassing gaf hij nog de oude stand). Een webhook die meteen komt kan
        # dus de stand van vóór de verkoop zien. Bij 1 weten we niet of dat het
        # laatste stuk was; dan liever elders offline dan dubbel verkocht.
        return BLIJFT if stuks > 1 else (OP if gevlagd else None)

    if not gevlagd:
        return None     # uniek artikel: het oude gedrag, product weg uit Shopify

    # Alleen een NIEUWE verkoop haalt een stuk af. Staat er op het verkoopkanaal
    # geen levende advertentie meer, dan is dit een herhaalde melding.
    nieuw = any(r.get("platform") == sold_on_platform and r.get("status") in LEVEND for r in rijen)
    met_voorraad = [v for v in varianten if int(v.get("inventory_quantity") or 0) > 0]
    if nieuw and len(met_voorraad) == 1:
        try:
            if await een_stuk_eraf(shop, token, met_voorraad[0]):
                stuks -= 1
                logger.info("shopify-voorraad: item %s verkocht op %s, Shopify %s nu %d stuks",
                            item_id, sold_on_platform, product_id, stuks)
        except Exception as e:  # noqa: BLE001
            logger.warning("shopify-voorraad: stuk eraf mislukt voor %s: %s", product_id, e)
    elif nieuw and len(met_voorraad) > 1:
        logger.info("shopify-voorraad: item %s heeft %d varianten met voorraad; welke er op %s "
                    "verkocht is weten we niet, voorraad blijft staan",
                    item_id, len(met_voorraad), sold_on_platform)
    return BLIJFT if stuks > 0 else OP
