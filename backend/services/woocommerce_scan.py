"""WooCommerce-producten inlezen als importkandidaten.

WAAROM (09-10-2026, Mikkis: "hoe werkt dit met WooCommerce? Want daar staan mijn
items in.") Precies zoals de Shopify-scan (services/shopify_scan.py): de server
leest de winkel met de sleutel van de koppeling en geeft de producten aan
dezelfde opslag als een Marktplaats- of Vinted-scan (jobs._store_scan_results).
Alles erna werkt daardoor vanzelf mee: te beoordelen, koppelen, bulk importeren,
en de advertentierij met het WooCommerce-productnummer, waarop een verkoop in de
winkel later het artikel terugvindt.

WAT ER UIT EEN PRODUCT KOMT. Gemeten bij Mikkis (304 producten bekeken van 2.504):
de eigenschappen heten Merk (271), Maat (210), Staat (200), Geslacht (187) en
Schoenmaat (11); 9% is een product met varianten (maten). Die namen, en hun
Engelse tegenhangers, worden hier herkend. Wat we niet herkennen laten we leeg;
de import vult dat aan zoals bij elk ander kanaal.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

from backend.platforms.woocommerce import PLATFORM, WooFout, client_uit, platte_tekst

logger = logging.getLogger(__name__)

# Eigenschapnamen per veld, kleine letters. Eerste treffer wint.
_NAMEN = {
    "brand": ("merk", "brand", "marke", "marque", "label", "designer"),
    "size": ("maat", "size", "kledingmaat", "schoenmaat", "shoe size", "größe", "taille",
             "ringmaat", "ring size"),
    "color": ("kleur", "color", "colour", "farbe", "couleur"),
    "material": ("materiaal", "material", "stof", "fabric", "matière"),
    "condition": ("staat", "conditie", "condition", "toestand", "zustand", "état", "etat"),
    "gender": ("geslacht", "gender", "doelgroep", "voor"),
}


def _eigenschappen(product: dict) -> dict[str, list[str]]:
    uit: dict[str, list[str]] = {}
    for a in product.get("attributes") or []:
        naam = html.unescape(str(a.get("name") or "")).strip().lower()
        opties = [html.unescape(str(o)).strip() for o in (a.get("options") or []) if str(o).strip()]
        if naam and opties and naam not in uit:
            uit[naam] = opties
    return uit


def _veld(eig: dict[str, list[str]], veld: str) -> list[str]:
    for naam in _NAMEN[veld]:
        if naam in eig:
            return eig[naam]
    return []


def _geslacht(waarden: list[str]) -> str | None:
    """Onze doelgroep uit de eigenschap Geslacht. Unisex laten we open: bij een
    kinderwinkel als Mikkis is dat een kinderproduct, en dat ziet de import wél
    aan maat en titel."""
    tekst = " ".join(waarden).lower()
    if re.search(r"\b(jongen|jongens|meisje|meisjes|baby|kind|kinderen|kids|boy|boys|girl|girls|junior)\b", tekst):
        return "kinderen"
    heren = re.search(r"\b(heren|man|mannen|men|male)\b", tekst)
    dames = re.search(r"\b(dames|vrouw|vrouwen|women|female|ladies)\b", tekst)
    if heren and not dames:
        return "heren"
    if dames and not heren:
        return "dames"
    return None


def _prijs(product: dict) -> float | None:
    for veld in ("price", "regular_price"):
        try:
            p = float(product.get(veld) or 0)
        except (TypeError, ValueError):
            continue
        if p > 0:
            return round(p, 2)
    return None


def uitverkocht(product: dict) -> bool:
    """WooCommerce zegt het zelf: bij een product met varianten is de stand van
    het hoofdproduct 'instock' zolang er één variant leverbaar is."""
    return product.get("stock_status") == "outofstock"


def stuks(product: dict) -> int | None:
    """Voorraad van een product zonder varianten, of None als niet bijgehouden."""
    if product.get("type") == "variable" or product.get("manage_stock") is not True:
        return None
    try:
        return max(int(product.get("stock_quantity") or 0), 0)
    except (TypeError, ValueError):
        return None


def heeft_meerdere_stuks(product: dict) -> bool:
    """Meer dan één stuk achter dit product: dan is het een voorraadwinkel.

    Een product met varianten telt mee zodra er twee varianten zijn: twee maten
    zijn twee stuks, en één verkoop mag dan nooit het hele product afmelden."""
    if product.get("type") == "variable":
        return len(product.get("variations") or []) > 1
    n = stuks(product)
    return n is not None and n > 1


def naar_scanregel(product: dict) -> dict:
    """Eén WooCommerce-product in de vorm die _store_scan_results verwacht."""
    eig = _eigenschappen(product)
    fotos = [i.get("src") for i in (product.get("images") or []) if i.get("src")]
    merk = (_veld(eig, "brand") or [None])[0]
    if not merk:
        # WooCommerce 9.6+ heeft een eigen merkenlijst naast de eigenschappen.
        merk = next((html.unescape(b.get("name") or "").strip()
                     for b in product.get("brands") or [] if b.get("name")), None) or None
    maten = _veld(eig, "size")
    # Eén maat is de maat. Meerdere (een product met varianten) zijn meerdere
    # stuks; welke maat er straks verkocht wordt weten we niet, dus leeg.
    maat = maten[0] if len(maten) == 1 else None
    kleuren = _veld(eig, "color")
    materiaal = (_veld(eig, "material") or [None])[0]
    if not materiaal:
        m = re.search(r"(?:materiaal|material)\s*:\s*([^\n]+)", platte_tekst(product.get("description")), re.I)
        materiaal = m.group(1).strip().rstrip(".")[:40] if m else None
    gender = _geslacht(_veld(eig, "gender"))
    if not gender and maat:
        from backend.api.imports import _kindermaat
        if _kindermaat(f"maat {maat}"):
            gender = "kinderen"
    omschrijving = platte_tekst(product.get("description")) or platte_tekst(product.get("short_description"))
    sku = (product.get("sku") or "").strip() or None
    gemaakt = product.get("date_created_gmt")
    return {
        "platform_listing_id": str(product["id"]),
        "platform_listing_url": product.get("permalink") or None,
        "platform_listed_at": (gemaakt + "Z") if gemaakt and not gemaakt.endswith("Z") else gemaakt,
        "title": html.unescape(product.get("name") or "").strip(),
        "price": _prijs(product),
        "photo_url": fotos[0] if fotos else None,
        "photo_urls": fotos,
        "description": omschrijving or None,
        "brand": merk,
        "size": maat,
        "color": kleuren[0] if len(kleuren) == 1 else None,
        "material": materiaal,
        "condition": (_veld(eig, "condition") or [None])[0],
        "gender": gender,
        "is_closed": uitverkocht(product),
        "sku": sku,
    }


async def markeer_als_voorraadwinkel(db, user_id: str, producten: list[dict]) -> None:
    """Bij de scan: heeft een product meer dan één stuk, dan is dit een voorraadwinkel.

    Dezelfde vlag als bij Shopify (shopify_voorraad.VLAG), op de WooCommerce-rij.
    Zonder die vlag haalt de eerste verkoop elders een product met voorraad uit
    de winkel, en dat is precies wat bij Goudlief misging (08-10-2026)."""
    if not any(heeft_meerdere_stuks(p) for p in producten):
        return
    from backend.services.woocommerce_voorraad import zet_vlag
    await zet_vlag(db, user_id)


async def lees_winkel(cred: dict) -> tuple[list[dict], object]:
    """Alle gepubliceerde producten. Geeft (producten, client)."""
    c = client_uit(cred)
    if not c:
        raise WooFout("Your WooCommerce shop isn't connected yet. Connect it under Platforms first.",
                      "geen_koppeling")
    producten = await c.producten()
    return producten, c


async def bewaar_modus(db, user_id: str, client) -> None:
    """Schakelde de client onderweg naar de sleutel in het adres, onthoud dat dan."""
    if not getattr(client, "modus_gewijzigd", False):
        return
    from backend.database import naast_de_lus
    try:
        rij = ((await naast_de_lus(lambda: db.table("platform_credentials").select("extra_data")
                .eq("user_id", user_id).eq("platform", PLATFORM).limit(1).execute())).data or [])
        extra = (rij[0].get("extra_data") if rij else None) or {}
        await naast_de_lus(lambda: db.table("platform_credentials")
                           .update({"extra_data": {**extra, "modus": client.modus}})
                           .eq("user_id", user_id).eq("platform", PLATFORM).execute())
        client.modus_gewijzigd = False
    except Exception as e:  # noqa: BLE001 — volgende keer schakelt hij gewoon opnieuw
        logger.warning("woocommerce: inlogmodus niet bewaard voor %s: %s", user_id[:8], e)


async def scan_winkel(user_id: str, job_id: str) -> None:
    """Achtergrondtaak na /imports/scan/woocommerce. Sluit de opdracht altijd af."""
    from backend.api.jobs import _store_scan_results
    from backend.database import get_db, naast_de_lus

    db = get_db()

    async def zet(velden: dict) -> None:
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
                                   .select("user_id,access_token,refresh_token,extra_data")
                                   .eq("user_id", user_id).eq("platform", PLATFORM)
                                   .limit(1).execute(), herkans=True)).data or [])
        if not rij:
            await fout("Your WooCommerce shop isn't connected yet. Connect it under Platforms first.")
            return
        await zet({"result": {"_progress": {"stage": "listing",
                                            "message": "Reading the products in your WooCommerce shop…"}}})
        try:
            producten, client = await lees_winkel(rij[0])
        except WooFout as e:
            await fout(str(e))
            return
        await bewaar_modus(db, user_id, client)

        try:
            await markeer_als_voorraadwinkel(db, user_id, producten)
        except Exception:  # noqa: BLE001 — de scan gaat voor
            logger.exception("woocommerce-scan: voorraadvlag niet gezet voor %s", user_id)

        regels = [naar_scanregel(p) for p in producten]
        await zet({"result": {"_progress": {"stage": "saving", "current": len(regels),
                                            "total": len(regels),
                                            "message": f"Saving {len(regels)} products to your dashboard…"}}})
        job = {"id": job_id, "user_id": user_id, "platform": PLATFORM}
        await naast_de_lus(lambda: _store_scan_results(db, job, regels))

        concepten = await client.tel("draft")
        te_koop = [r for r in regels if not r["is_closed"]]
        logger.info("woocommerce-scan %s: %d producten, %d te koop, %d uitverkocht",
                    user_id, len(regels), len(te_koop), len(regels) - len(te_koop))
        await zet({"status": "done", "done_at": datetime.now(timezone.utc).isoformat(),
                   "result": {"listings": [{"platform_listing_id": r["platform_listing_id"]}
                                           for r in te_koop],
                              "scan_meta": {"gevonden": len(te_koop),
                                            "uitverkocht": len(regels) - len(te_koop),
                                            "concepten": concepten}}})
    except Exception as e:  # noqa: BLE001
        logger.exception("woocommerce-scan mislukt voor %s", user_id)
        try:
            await fout(f"The WooCommerce scan failed ({type(e).__name__}). Try again in a moment.")
        except Exception:  # noqa: BLE001
            logger.exception("woocommerce-scan: kon de opdracht niet afsluiten")
