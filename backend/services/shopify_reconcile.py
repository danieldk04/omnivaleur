"""Advertenties herkennen die al op Shopify staan, zonder dat de verkoper dat zelf hoeft te melden.

WAAROM DIT ER IS (09-09-2026, Daniel)

Marktplaats en 2dehands hebben een scan die een bestaande advertentie herkent en
aanbiedt om te koppelen (backend/api/imports.py, import_candidates). Shopify
heeft dat niet — wie zijn winkel koppelt terwijl er al een catalogus staat
(en dat is de normale situatie, niemand begint met een lege Shopify-winkel) ziet
elk artikel dat óók op Shopify staat gewoon als "niet gelist". De verkoper zou
dat per artikel handmatig moeten aanvinken.

GEMETEN op Revaleur's eigen winkel (09-09-2026, ywqad3-xb.myshopify.com, 315
actieve producten): 241 artikelen stonden al Active op Shopify zonder koppeling
in Omnivaleur. Voorbeeld: "(1274) Beige Suitsupply Shirt - Men S - Very Good",
op Shopify sinds 31-05-2026 — ruim vóór dit item op 03-07-2026 vanuit Marktplaats
werd geïmporteerd en vóór Shopify op 28-08-2026 werd gekoppeld.

Zonder de koppeling loopt ook de verkoopherkenning mis: match_shopify_sale
(shopify_orders.py) zoekt eerst op platform_listing_id en pas dan op SKU — een
artikel zonder listings-rij vindt geen van beide, dus een verkoop op Shopify zelf
haalt het artikel nergens anders weg. Handmatig aanvinken "staat al gelist" lost
het bovenaanzicht op maar niet dít probleem: zonder platform_listing_id blijft de
verkoopherkenning net zo blind.

HOE DE KOPPELING WORDT GEVONDEN. Het nummer dat de verkoper zelf voor de titel
zet — "(1274)" — staat óók als variant-SKU in Shopify. Dat is precies het
nummer dat tweelingen.py al gebruikt (nummer_van) om dezelfde advertentie op twee
kanalen te herkennen; hier gebruiken we het om dezelfde advertentie tussen
Omnivaleur en Shopify te herkennen.

Twee vangnetten tegen een verkeerde koppeling, want een verkeerde koppeling is
erger dan geen koppeling — die zet straks een verkoop op het verkeerde artikel
af:
  1. Het nummer moet bij precies één Shopify-product horen. Draagt het nummer
     bij meerdere producten (kan, bij een fout in de winkel zelf), dan koppelen
     we niets.
  2. Staat er een merk bij zowel het Omnivaleur-artikel als het Shopify-product
     (vendor), dan moeten die overeenkomen — zelfde afweging als
     tweelingen.familie_ids. GEMETEN: dit ving 3 van de 244 kandidaten af, onder
     meer "(1277) Red/White Suitsupply Shirt" dat qua nummer overeenkwam met een
     Ralph Lauren-product; zonder deze controle had dat artikel een advertentie
     van een ander merk als koppeling gekregen.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

from backend.database import get_db, naast_de_lus
from backend.platforms.shopify import _shop_creds

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^\s*[\(\[\{]\s*([A-Za-z0-9][A-Za-z0-9\-_.]{1,23})\s*[\)\]\}]")

# Shopify staat 2 verzoeken per seconde toe op de Admin REST-API. Deze pauze
# tussen pagina's houdt daar ruim onder; bij een 429 wachten we bovendien de
# door Shopify zelf opgegeven Retry-After af.
_PAUZE_TUSSEN_PAGINAS = 0.55


def _nummer_van(item: dict) -> str:
    """Zelfde functie als tweelingen.nummer_van — hier los gehouden zodat deze
    module niet van een import-context afhangt die alleen bij het uitdelen
    van werk bestaat."""
    m = _CODE_RE.match(str((item or {}).get("title") or ""))
    if m:
        return m.group(1).lower()
    sku = str((item or {}).get("sku") or "").strip().lower()
    return sku


async def _alle_actieve_shopify_producten(shop: str, token: str) -> list[dict]:
    """Elk actief product met zijn variant-SKU's en merk (vendor), gepagineerd."""
    producten: list[dict] = []
    url = f"https://{shop}/admin/api/2024-10/products.json"
    params: dict | None = {"limit": 250, "status": "active",
                           "fields": "id,title,vendor,handle,variants"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        while url:
            for _poging in range(4):
                resp = await client.get(url, params=params,
                                        headers={"X-Shopify-Access-Token": token})
                if resp.status_code == 429:
                    wacht = float(resp.headers.get("Retry-After", 1))
                    await asyncio.sleep(wacht + 0.3)
                    continue
                resp.raise_for_status()
                break
            else:
                logger.warning("shopify-reconciliatie: bleef 429 krijgen op %s, ronde afgebroken", shop)
                break
            data = resp.json()
            producten += data.get("products", [])
            url = None
            for part in resp.headers.get("Link", "").split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
            params = None
            if url:
                await asyncio.sleep(_PAUZE_TUSSEN_PAGINAS)
    return producten


async def reconcile_shopify_catalog(user_id: str) -> dict:
    """Koppel elk Omnivaleur-artikel van deze verkoper aan zijn bestaande
    Shopify-product, als dat er ondubbelzinnig één is.

    Raakt nooit een bestaande listings-rij aan — alleen artikelen die nog geen
    enkele Shopify-rij hebben (actief, verwijderd of anderszins) komen in
    aanmerking. Veilig om vaker te draaien: een tweede ronde vindt gewoon niets
    meer om te doen.
    """
    db = get_db()
    cred = ((await naast_de_lus(lambda: db.table("platform_credentials")
            .select("*").eq("user_id", user_id).eq("platform", "shopify")
            .limit(1).execute())).data or [None])[0]
    if not cred:
        return {"gekoppeld": 0, "reden": "Shopify niet gekoppeld"}

    try:
        shop, token = await _shop_creds(cred)
    except Exception as e:  # noqa: BLE001 — een verlopen sleutel mag deze ronde niet laten crashen
        logger.warning("shopify-reconciliatie: geen bruikbare sleutel voor %s: %s", user_id, e)
        return {"gekoppeld": 0, "reden": f"geen bruikbare Shopify-sleutel: {e}"}
    if not (shop and token):
        return {"gekoppeld": 0, "reden": "geen bruikbare Shopify-sleutel"}

    try:
        producten = await _alle_actieve_shopify_producten(shop, token)
    except Exception as e:  # noqa: BLE001
        logger.warning("shopify-reconciliatie: kon de catalogus niet lezen voor %s: %s", user_id, e)
        return {"gekoppeld": 0, "reden": f"kon Shopify niet lezen: {e}"}

    # SKU -> Shopify-producten die die SKU dragen. Meer dan één is geen
    # betrouwbaar signaal meer.
    per_sku: dict[str, list[dict]] = {}
    for p in producten:
        for variant in p.get("variants") or []:
            sku = str(variant.get("sku") or "").strip().lower()
            if sku:
                per_sku.setdefault(sku, []).append(p)

    items = ((await naast_de_lus(lambda: db.table("items")
             .select("id,title,brand,sku").eq("user_id", user_id).execute())).data or [])
    if not items:
        return {"gekoppeld": 0, "producten_gezien": len(producten)}

    item_ids = [i["id"] for i in items]
    al_gekoppeld = {
        r["item_id"] for r in
        ((await naast_de_lus(lambda: db.table("listings").select("item_id")
         .eq("platform", "shopify").in_("item_id", item_ids).execute())).data or [])
    }

    # Draagt hetzelfde nummer meer dan één artikel VAN DEZE VERKOPER, dan is niet
    # te zeggen welke van de twee bij het Shopify-product hoort. Overslaan.
    nummer_naar_items: dict[str, list[str]] = {}
    for it in items:
        nr = _nummer_van(it)
        if nr:
            nummer_naar_items.setdefault(nr, []).append(it["id"])

    gekoppeld = 0
    overgeslagen_merkverschil = 0
    overgeslagen_dubbelzinnig = 0
    for item in items:
        if item["id"] in al_gekoppeld:
            continue
        nummer = _nummer_van(item)
        if not nummer or nummer not in per_sku:
            continue
        if len(nummer_naar_items.get(nummer, [])) != 1:
            overgeslagen_dubbelzinnig += 1
            continue
        kandidaten = per_sku[nummer]
        if len(kandidaten) != 1:
            continue  # dubbele SKU op Shopify zelf: niet gokken
        product = kandidaten[0]
        merk_item = str(item.get("brand") or "").strip().lower()
        merk_shop = str(product.get("vendor") or "").strip().lower()
        if merk_item and merk_shop and merk_item != merk_shop:
            overgeslagen_merkverschil += 1
            continue
        try:
            await naast_de_lus(lambda item=item, product=product: db.table("listings").insert({
                "item_id": item["id"],
                "platform": "shopify",
                "status": "active",
                "platform_listing_id": str(product["id"]),
                "platform_listing_url": f"https://{shop}/products/{product.get('handle', '')}",
                "listed_at": datetime.now(timezone.utc).isoformat(),
            }).execute())
            gekoppeld += 1
        except Exception as e:  # noqa: BLE001 — één mislukte koppeling mag de rest niet blokkeren
            logger.warning("shopify-reconciliatie: kon item %s niet koppelen: %s", item["id"], e)

    if gekoppeld:
        logger.info(
            "shopify-reconciliatie: %d artikel(en) gekoppeld aan hun bestaande Shopify-product voor %s "
            "(overgeslagen: %d merkverschil, %d dubbelzinnig nummer)",
            gekoppeld, user_id, overgeslagen_merkverschil, overgeslagen_dubbelzinnig,
        )
    return {
        "gekoppeld": gekoppeld,
        "overgeslagen_merkverschil": overgeslagen_merkverschil,
        "overgeslagen_dubbelzinnig": overgeslagen_dubbelzinnig,
        "producten_gezien": len(producten),
    }


async def _product_bestaat_nog(shop: str, token: str, platform_listing_id: str | None) -> str:
    """"levend", "weg" of "onbekend".

    "onbekend" bij een transiënte fout (429, 5xx, netwerkhik) — die mag een
    listing NOOIT laten kelderen. Alleen een expliciete 404 (Shopify's "dit
    bestaat niet") telt als "weg". Zonder eigen platform_listing_id is er niets
    te controleren; dat telt hier ook als "weg", want de rij hangt dan toch al
    los van elk bewijs dat hij ooit echt bestond.
    """
    if not platform_listing_id:
        return "weg"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0)) as client:
            for _poging in range(3):
                resp = await client.get(
                    f"https://{shop}/admin/api/2024-10/products/{platform_listing_id}.json",
                    headers={"X-Shopify-Access-Token": token},
                )
                if resp.status_code == 429:
                    await asyncio.sleep(float(resp.headers.get("Retry-After", 1)) + 0.3)
                    continue
                if resp.status_code == 404:
                    return "weg"
                if resp.status_code == 200:
                    return "levend"
                return "onbekend"
    except Exception as e:  # noqa: BLE001 — een netwerkhik is geen bewijs dat het product weg is
        logger.warning("shopify-reconciliatie: kon product %s niet controleren: %s",
                       platform_listing_id, e)
    return "onbekend"


async def reconcile_verweesde_shopify_listings(user_id: str) -> dict:
    """Advertentierijen rechtzetten die "actief" zeggen terwijl het Shopify-product

    weg is — het spiegelbeeld van reconcile_shopify_catalog hierboven. Drie
    soorten, elk met een andere, veilige uitkomst:

      1. Er is nog een ANDERE actieve rij voor hetzelfde artikel op Shopify die
         wél bestaat (een oude herplaatsing zette een tweede product naast het
         eerste in plaats van het te vervangen — zie kennisbank
         "reddingsronde-kale-plaatsing-dubbele-advertentie"). De verweesde rij
         is dan gewoon overbodig: rechtstreeks naar 'delisted', geen vraag
         nodig.
      2. Geen enkele rij op Shopify leeft nog, maar het artikel staat al
         bevestigd 'sold' op een ANDER kanaal. Dan is de vraag al beantwoord:
         rechtstreeks naar 'delisted'. Zelfde afweging als bij
         `_neem_herplaatsing_terug`/de nachtelijke verversing in
         backend/api/jobs.py ("al_verkocht_elders").
      3. Geen van beide: we weten het niet. Naar 'sold_unconfirmed', zodat de
         verkoper de bestaande "Is dit verkocht?"-vraag op het dashboard
         krijgt — dezelfde weg als bij Marktplaats en 2dehands. Een verkeerde
         gok hier zou het artikel ten onrechte van je andere kanalen afhalen;
         dat is niet aan een geautomatiseerde ronde om te beslissen.

    GEMETEN op Revaleur (09-09-2026): 4 verweesde rijen. Eén ervan (Navy
    Suitsupply Suit Pants) had een levende opvolger — rechtstreeks opgeruimd.
    De andere drie hadden nergens een bevestigde verkoop — allemaal naar
    'sold_unconfirmed'.
    """
    from backend.api.listings import VERDENKING_REDENEN

    db = get_db()
    cred = ((await naast_de_lus(lambda: db.table("platform_credentials")
            .select("*").eq("user_id", user_id).eq("platform", "shopify")
            .limit(1).execute())).data or [None])[0]
    if not cred:
        return {"opgeruimd": 0, "gevraagd": 0, "reden": "Shopify niet gekoppeld"}
    try:
        shop, token = await _shop_creds(cred)
    except Exception as e:  # noqa: BLE001
        logger.warning("shopify-reconciliatie: geen bruikbare sleutel voor %s: %s", user_id, e)
        return {"opgeruimd": 0, "gevraagd": 0, "reden": f"geen bruikbare Shopify-sleutel: {e}"}
    if not (shop and token):
        return {"opgeruimd": 0, "gevraagd": 0, "reden": "geen bruikbare Shopify-sleutel"}

    items = ((await naast_de_lus(lambda: db.table("items").select("id")
             .eq("user_id", user_id).execute())).data or [])
    item_ids = [i["id"] for i in items]
    if not item_ids:
        return {"opgeruimd": 0, "gevraagd": 0}

    actief = ((await naast_de_lus(lambda: db.table("listings")
              .select("id,item_id,platform_listing_id")
              .eq("platform", "shopify").eq("status", "active")
              .in_("item_id", item_ids).execute())).data or [])
    if not actief:
        return {"opgeruimd": 0, "gevraagd": 0}

    per_item: dict[str, list[dict]] = {}
    for rij in actief:
        per_item.setdefault(rij["item_id"], []).append(rij)

    nu = datetime.now(timezone.utc).isoformat()
    opgeruimd = 0   # rechtstreeks naar 'delisted' — overbodig of al elders verkocht
    gevraagd = 0    # naar 'sold_unconfirmed' — de verkoper moet het zeggen
    overgeslagen = 0  # transiënte fout: met rust gelaten

    for item_id, rijen in per_item.items():
        beoordeeld = []
        onzeker_hier = 0
        for rij in rijen:
            staat = await _product_bestaat_nog(shop, token, rij.get("platform_listing_id"))
            if staat == "onbekend":
                onzeker_hier += 1
                continue
            beoordeeld.append((rij, staat == "levend"))
            await asyncio.sleep(_PAUZE_TUSSEN_PAGINAS)
        if onzeker_hier:
            overgeslagen += onzeker_hier
            # Bij twijfel over ÉÉN rij van dit artikel raken we de rest van dit
            # artikel deze ronde ook niet aan — de volgende ronde komt terug.
            continue

        weg = [rij for rij, levend in beoordeeld if not levend]
        levend = [rij for rij, levend in beoordeeld if levend]
        if not weg:
            continue

        if levend:
            # Overbodig: er is al een levende opvolger voor dit artikel.
            for rij in weg:
                try:
                    await naast_de_lus(lambda r=rij: db.table("listings").update({
                        "status": "delisted", "error_message": None, "last_checked": nu,
                    }).eq("id", r["id"]).execute())
                    opgeruimd += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning("shopify-reconciliatie: kon overbodige rij %s niet opruimen: %s",
                                   rij["id"], e)
            continue

        # Geen enkele Shopify-rij van dit artikel leeft nog. Al bevestigd
        # verkocht op een ANDER kanaal? Dan is de vraag al beantwoord.
        verkochte_rijen = ((await naast_de_lus(lambda: db.table("listings")
                           .select("platform").eq("item_id", item_id)
                           .eq("status", "sold").execute())).data or [])
        al_verkocht_elders = any(r.get("platform") != "shopify" for r in verkochte_rijen)

        for rij in weg:
            try:
                if al_verkocht_elders:
                    await naast_de_lus(lambda r=rij: db.table("listings").update({
                        "status": "delisted", "error_message": None, "last_checked": nu,
                    }).eq("id", r["id"]).execute())
                    opgeruimd += 1
                else:
                    await naast_de_lus(lambda r=rij: db.table("listings").update({
                        "status": "sold_unconfirmed",
                        "error_message": VERDENKING_REDENEN["shopify_weg"],
                        "last_checked": nu,
                    }).eq("id", r["id"]).execute())
                    gevraagd += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("shopify-reconciliatie: kon verweesde rij %s niet bijwerken: %s",
                               rij["id"], e)

    if opgeruimd or gevraagd:
        logger.info(
            "shopify-reconciliatie: %d verweesde rij(en) opgeruimd, %d aan de verkoper gevraagd "
            "(%d overgeslagen wegens een onzekere controle) voor %s",
            opgeruimd, gevraagd, overgeslagen, user_id,
        )
    return {"opgeruimd": opgeruimd, "gevraagd": gevraagd, "overgeslagen": overgeslagen}


async def reconcile_alle_shopify_winkels() -> dict:
    """Elke gekoppelde Shopify-winkel een reconciliatieronde geven — zowel wat
    er nieuw bij moet (reconcile_shopify_catalog) als wat er weg moet
    (reconcile_verweesde_shopify_listings).

    Draait dagelijks (zie scheduler.py) zodat een product dat buiten Omnivaleur
    om aan de catalogus wordt toegevoegd of verwijderd — bulkimport, handmatig
    in het winkelbeheer — vanzelf wordt herkend, zonder dat de verkoper iets
    hoeft te doen of zelfs maar hoeft in te loggen.
    """
    db = get_db()
    rijen = ((await naast_de_lus(lambda: db.table("platform_credentials")
             .select("user_id").eq("platform", "shopify").execute())).data or [])
    totaal_gekoppeld = totaal_opgeruimd = totaal_gevraagd = 0
    for rij in rijen:
        try:
            uit = await reconcile_shopify_catalog(rij["user_id"])
            totaal_gekoppeld += uit.get("gekoppeld", 0)
        except Exception as e:  # noqa: BLE001 — één winkel mag de rest niet blokkeren
            logger.warning("shopify-reconciliatie: koppelronde mislukt voor %s: %s", rij["user_id"], e)
        try:
            uit2 = await reconcile_verweesde_shopify_listings(rij["user_id"])
            totaal_opgeruimd += uit2.get("opgeruimd", 0)
            totaal_gevraagd += uit2.get("gevraagd", 0)
        except Exception as e:  # noqa: BLE001
            logger.warning("shopify-reconciliatie: opruimronde mislukt voor %s: %s", rij["user_id"], e)
    if totaal_gekoppeld or totaal_opgeruimd or totaal_gevraagd:
        logger.info(
            "shopify-reconciliatie: %d gekoppeld, %d opgeruimd, %d aan verkopers gevraagd, over %d winkel(s)",
            totaal_gekoppeld, totaal_opgeruimd, totaal_gevraagd, len(rijen),
        )
    return {"winkels": len(rijen), "gekoppeld": totaal_gekoppeld,
            "opgeruimd": totaal_opgeruimd, "gevraagd": totaal_gevraagd}
