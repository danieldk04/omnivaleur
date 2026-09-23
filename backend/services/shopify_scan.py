"""Bestaande Shopify-producten inlezen als importkandidaten.

WAAROM (23-09-2026, Goudlief)
Een winkelier met zijn voorraad in Shopify wil die vanuit Shopify op Marktplaats
en de rest krijgen. Tot nu toe kon Omnivaleur alleen NAAR Shopify schrijven;
inlezen ging alleen vanuit Marktplaats, 2dehands en Vinted. Voor Goudlief was dat
de reden om niet te beginnen ("voor mij is het een must").

HOE
Anders dan de andere kanalen heeft de extensie hier niets te doen: de server
heeft de sleutel van de winkel al (dezelfde die het publiceren gebruikt, met
read_products erin). We lezen de actieve producten via de Admin API en geven ze
aan precies dezelfde opslag als een Marktplaats- of Vinted-scan
(jobs._store_scan_results). Daardoor werkt alles erna vanzelf mee: de
te-beoordelen lijst, koppelen aan een bestaand artikel, bulk importeren, en het
bijschrijven van de advertentierij met het Shopify-productnummer. Dat laatste is
wat een verkoop in de winkel later aan het artikel koppelt
(shopify_orders.match_shopify_sale matcht op product_id).
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

API_VERSIE = "2024-01"          # dezelfde als ShopifyClient en de verkoopcontrole
PER_PAGINA = 250                # het maximum dat Shopify per keer toestaat
MAX_PAGINAS = 80                # 20.000 producten: ruim, maar nooit eindeloos
VELDEN = ("id,title,body_html,vendor,handle,images,variants,options,tags,"
          "product_type,status,published_at,created_at")


def volgende_pagina(link_header: str | None) -> str | None:
    """page_info van de volgende pagina uit Shopify's Link-kop, of None."""
    for deel in (link_header or "").split(","):
        if 'rel="next"' in deel:
            m = re.search(r"page_info=([^&>]+)", deel)
            if m:
                return m.group(1)
    return None


def uitverkocht(product: dict) -> bool:
    """Alle varianten worden bijgehouden en staan op nul of minder.

    Een variant zonder voorraadbeheer telt als leverbaar: dan weten we het niet,
    en een artikel dat er wél is weglaten kost meer dan er één te veel tonen."""
    varianten = product.get("variants") or []
    if not varianten:
        return False
    for v in varianten:
        if v.get("inventory_management") != "shopify":
            return False
        if (v.get("inventory_quantity") or 0) > 0:
            return False
    return True


def winkelnaam_als_merk(producten: list[dict]) -> str | None:
    """De vendor die Shopify invult als niemand een merk opgaf: de winkelnaam.

    Staat bij (vrijwel) elk product dezelfde vendor, dan is dat geen merk maar de
    winkel zelf, en die hoort niet als merk op Marktplaats te belanden."""
    namen = [(p.get("vendor") or "").strip() for p in producten]
    namen = [n for n in namen if n]
    if len(namen) < 10:
        return None
    naam, aantal = Counter(namen).most_common(1)[0]
    return naam if aantal / len(producten) >= 0.9 else None


def naar_scanregel(product: dict, shop: str, winkelnaam: str | None = None) -> dict:
    """Eén Shopify-product in de vorm die _store_scan_results verwacht."""
    from backend.platforms.shopify_importer import _convert

    basis = _convert(product)
    fotos = [u for u in (basis.get("photo_urls") or []) if u]
    vendor = (product.get("vendor") or "").strip()
    merk = basis.get("brand") or (vendor if vendor and vendor != winkelnaam else None)
    handle = product.get("handle") or ""
    # Materiaal opnieuw zoeken in de platte tekst, die zijn regels nog heeft.
    # _convert zoekt in html waarvan elke <br> een spatie werd, en pakte daardoor
    # de rest van de omschrijving mee: "Merino Wool Fit: Slim Fit Questions
    # welcome…" (gemeten op een echte winkel, 23-09-2026).
    materiaal = basis.get("material")
    m = re.search(r"Material:\s*([^\n]+)", basis.get("description") or "", re.IGNORECASE)
    if m:
        materiaal = m.group(1).strip().rstrip(".")
    elif materiaal and len(materiaal) > 40:
        materiaal = None     # liever leeg dan een halve zin als materiaal
    return {
        "platform_listing_id": str(product["id"]),
        "platform_listing_url": f"https://{shop}/products/{handle}" if handle else None,
        "platform_listed_at": product.get("published_at") or product.get("created_at"),
        "title": basis.get("title") or "",
        "price": basis.get("price") or None,
        "photo_url": fotos[0] if fotos else None,
        "photo_urls": fotos,
        "description": basis.get("description") or None,
        "brand": merk,
        "size": basis.get("size"),
        "color": basis.get("color"),
        "material": basis.get("material"),
        "is_closed": uitverkocht(product),
    }


async def lees_producten(shop: str, token: str) -> list[dict]:
    """Alle actieve producten van de winkel, pagina voor pagina."""
    import httpx

    kop = {"X-Shopify-Access-Token": token}
    basis = f"https://{shop}/admin/api/{API_VERSIE}/products.json"
    producten: list[dict] = []
    page_info = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as c:
        for _ in range(MAX_PAGINAS):
            # Met page_info mag Shopify geen andere filters meer krijgen dan
            # limit en fields; status zit dan al in de cursor.
            params = {"limit": PER_PAGINA, "fields": VELDEN}
            if page_info:
                params["page_info"] = page_info
            else:
                params["status"] = "active"
            r = await c.get(basis, params=params, headers=kop)
            if r.status_code in (401, 403):
                raise PermissionError(r.status_code)
            r.raise_for_status()
            producten += r.json().get("products", [])
            page_info = volgende_pagina(r.headers.get("link"))
            if not page_info:
                return producten
    logger.warning("shopify-scan %s: gestopt na %d pagina's", shop, MAX_PAGINAS)
    return producten


async def scan_winkel(user_id: str, job_id: str) -> None:
    """Draait als achtergrondtaak na /imports/scan/shopify. Sluit de opdracht
    altijd af, met 'done' of met een 'error' die de verkoper kan lezen: een
    opdracht die op 'claimed' blijft hangen leest als een kapotte scan."""
    from backend.database import get_db, naast_de_lus
    from backend.platforms.shopify import _shop_creds
    from backend.api.jobs import _store_scan_results

    db = get_db()

    async def zet(velden: dict) -> None:
        # Een tijdstip bij elke voortgangsmelding: zonder "at" ziet de
        # opruimregel in jobs._recover_stale_claims de scan als vastgelopen.
        prog = (velden.get("result") or {}).get("_progress")
        if isinstance(prog, dict):
            prog["at"] = datetime.now(timezone.utc).isoformat()
        await naast_de_lus(lambda: db.table("jobs").update(velden).eq("id", job_id).execute(),
                           herkans=True)

    async def fout(tekst: str) -> None:
        await zet({"status": "error", "done_at": datetime.now(timezone.utc).isoformat(),
                   "result": {"error": tekst}})

    try:
        rij = ((await naast_de_lus(lambda: db.table("platform_credentials")
                                   .select("user_id,access_token,extra_data")
                                   .eq("user_id", user_id).eq("platform", "shopify")
                                   .limit(1).execute(), herkans=True)).data or [])
        if not rij:
            await fout("Your Shopify store isn't connected yet. Connect it under Platforms first.")
            return
        shop, token = await _shop_creds({**rij[0], "user_id": user_id})
        if not (shop and token):
            await fout("Your Shopify connection is incomplete. Reconnect it under Platforms.")
            return

        await zet({"result": {"_progress": {"stage": "listing",
                                            "message": "Reading the products in your Shopify store…"}}})
        try:
            producten = await lees_producten(shop, token)
        except PermissionError:
            await fout("Shopify refused access to your products. Reconnect your store under "
                       "Platforms and make sure read_products is among the permissions.")
            return

        winkelnaam = winkelnaam_als_merk(producten)
        regels = [naar_scanregel(p, shop, winkelnaam) for p in producten]
        await zet({"result": {"_progress": {"stage": "saving", "current": len(regels),
                                            "total": len(regels),
                                            "message": f"Saving {len(regels)} products to your dashboard…"}}})
        job = {"id": job_id, "user_id": user_id, "platform": "shopify"}
        await naast_de_lus(lambda: _store_scan_results(db, job, regels))

        te_koop = [r for r in regels if not r["is_closed"]]
        logger.info("shopify-scan %s (%s): %d producten, %d te koop, %d uitverkocht",
                    user_id, shop, len(regels), len(te_koop), len(regels) - len(te_koop))
        await zet({"status": "done", "done_at": datetime.now(timezone.utc).isoformat(),
                   "result": {"listings": [{"platform_listing_id": r["platform_listing_id"]}
                                           for r in te_koop],
                              "scan_meta": {"gevonden": len(te_koop),
                                            "uitverkocht": len(regels) - len(te_koop)}}})
    except Exception as e:  # noqa: BLE001
        logger.exception("shopify-scan mislukt voor %s", user_id)
        try:
            await fout(f"The Shopify scan failed ({type(e).__name__}). Try again in a moment.")
        except Exception:  # noqa: BLE001
            logger.exception("shopify-scan: kon de opdracht niet afsluiten")
