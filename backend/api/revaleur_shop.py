"""Revaleur-webshop: afrekenen en afhandelen (herbouw 27-11-2026, docs/revaleur-ontwerp.md).

De winkelkant is statisch (Cloudflare Pages). Alleen dit stuk hangt van de backend af:
  POST /api/revaleur/checkout        winkelmand -> reserveren -> Stripe Checkout-sessie
  POST /api/revaleur/stripe-webhook  betaald -> bestelling, artikel overal afmelden, mail

Eén exemplaar per artikel: de reservering (tabel revaleur_reserveringen) houdt een artikel
30 minuten vast. Een tweede koper krijgt `verkocht`. Een verlopen of mislukte betaling geeft
het artikel vrij. De prijs komt van de server; de browser stuurt de getoonde prijs mee en
bij een verschil weigeren we (409) in plaats van een ander bedrag te innen.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/revaleur", tags=["revaleur"])

RESERVERING_MINUTEN = 30
MAX_ARTIKELEN = 20
EU = {"AT", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
      "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
# Verzendbeleid (docs/revaleur/policies_shipping-policy.txt): NL en BE gratis; EU 3,95; buiten EU 4,95; gratis vanaf 100.
GRATIS_VANAF = 100.0
ZONES = {
    "NL": ("Netherlands", ["NL"], 0.0), "BE": ("Belgium", ["BE"], 0.0),
    "EU": ("Europe", sorted(EU), 3.95),
    "INT": ("International", ["GB", "CH", "NO", "US", "CA", "AU", "IS", "LI"], 4.95),
}


def verzendkosten(zone: str, subtotaal: float) -> float:
    if zone not in ZONES:
        raise ValueError(zone)
    kosten = ZONES[zone][2]
    return 0.0 if kosten == 0 or subtotaal >= GRATIS_VANAF else kosten


def zone_van_land(land: str) -> str:
    land = (land or "").upper()
    if land in ("NL", "BE"):
        return land
    return "EU" if land in EU else "INT"


class CheckoutIn(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=MAX_ARTIKELEN)   # Shopify-product-id's uit de statische site
    prijzen: dict[str, float] | None = None                                # getoonde prijs per id
    land: str = "NL"
    taal: str = "en"


def _sleutel() -> str:
    return settings.revaleur_stripe_secret_key or settings.stripe_secret_key


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _vrijgeven_verlopen(db) -> None:
    db.table("revaleur_reserveringen").delete().lt("tot", _nu().isoformat()).execute()


def _artikelen(db, product_ids: list[str]) -> dict[str, dict]:
    """product-id (listing) -> {item, prijs}. Alleen artikelen van Revaleur met een levende Shopify-advertentie."""
    uit: dict[str, dict] = {}
    ls = (db.table("listings").select("item_id,platform_listing_id,status").eq("platform", "shopify")
          .in_("platform_listing_id", product_ids).eq("status", "active").execute().data or [])
    if not ls:
        return uit
    items = {i["id"]: i for i in (db.table("items").select("id,sku,title,shopify_title,price,price_shopify,photo_urls,user_id")
                                  .in_("id", [l["item_id"] for l in ls]).execute().data or [])}
    for l in ls:
        it = items.get(l["item_id"])
        if not it or it.get("user_id") != settings.revaleur_user_id:
            continue
        prijs = float(it.get("price_shopify") or it.get("price") or 0)
        uit[l["platform_listing_id"]] = {"item": it, "prijs": round(prijs, 2)}
    return uit


@router.post("/checkout")
async def checkout(body: CheckoutIn):
    if not _sleutel():
        raise HTTPException(503, "Stripe is niet ingesteld")
    zone = body.land if body.land in ZONES else "INT"
    ids = list(dict.fromkeys(body.ids))
    db = get_db()
    try:
        _vrijgeven_verlopen(db)
        gevonden = _artikelen(db, ids)
    except Exception as e:  # noqa: BLE001
        logger.error("[revaleur] database onbereikbaar bij afrekenen: %s", e)
        raise HTTPException(503, "Afrekenen is tijdelijk niet beschikbaar")
    weg = [i for i in ids if i not in gevonden]
    if weg:
        raise HTTPException(409, {"verkocht": weg})
    if body.prijzen:
        afwijkend = [i for i in ids if i in body.prijzen and abs(body.prijzen[i] - gevonden[i]["prijs"]) > 0.01]
        if afwijkend:
            raise HTTPException(409, {"prijs_gewijzigd": afwijkend})

    # Reserveren: de primaire sleutel op item_id laat precies één koper slagen.
    tot = (_nu() + timedelta(minutes=RESERVERING_MINUTEN + 1)).isoformat()
    sessie_tijdelijk = f"pending-{int(time.time() * 1000)}"
    vastgehouden, verkocht = [], []
    for pid in ids:
        item_id = gevonden[pid]["item"]["id"]
        try:
            db.table("revaleur_reserveringen").insert({"item_id": item_id, "sessie_id": sessie_tijdelijk, "tot": tot}).execute()
            vastgehouden.append(item_id)
        except Exception:  # noqa: BLE001 — bezet (unieke sleutel) of database-fout
            verkocht.append(pid)
    if verkocht:
        _geef_vrij(db, vastgehouden)
        raise HTTPException(409, {"verkocht": verkocht})

    subtotaal = round(sum(gevonden[i]["prijs"] for i in ids), 2)
    kosten = verzendkosten(zone, subtotaal)
    regels = [{
        "quantity": 1,
        "price_data": {
            "currency": "eur", "unit_amount": int(round(gevonden[i]["prijs"] * 100)),
            "product_data": {"name": (gevonden[i]["item"].get("shopify_title") or gevonden[i]["item"]["title"])[:250],
                             "images": [u for u in (gevonden[i]["item"].get("photo_urls") or [])[:1]],
                             "metadata": {"item_id": gevonden[i]["item"]["id"], "sku": gevonden[i]["item"].get("sku") or ""}},
        },
    } for i in ids]
    site = settings.revaleur_site_url.rstrip("/")
    pre = "/nl" if body.taal == "nl" else ""
    try:
        sessie = stripe.checkout.Session.create(
            api_key=_sleutel(), mode="payment", line_items=regels,
            shipping_address_collection={"allowed_countries": ZONES[zone][1]},
            shipping_options=[{"shipping_rate_data": {
                "type": "fixed_amount", "display_name": "Free shipping" if kosten == 0 else "Standard shipping",
                "fixed_amount": {"amount": int(round(kosten * 100)), "currency": "eur"}}}],
            payment_method_types=["ideal", "card"] if zone in ("NL", "BE", "EU") else ["card"],
            locale="nl" if body.taal == "nl" else "en",
            expires_at=int(time.time()) + RESERVERING_MINUTEN * 60,
            metadata={"bron": "revaleur", "item_ids": ",".join(gevonden[i]["item"]["id"] for i in ids), "taal": body.taal},
            success_url=f"{site}{pre}/bedankt", cancel_url=f"{site}{pre}/cart",
            phone_number_collection={"enabled": True},
        )
    except Exception as e:  # noqa: BLE001
        _geef_vrij(db, vastgehouden)
        logger.error("[revaleur] Stripe weigerde de sessie: %s", e)
        raise HTTPException(503, "Afrekenen is tijdelijk niet beschikbaar")
    db.table("revaleur_reserveringen").update({"sessie_id": sessie.id}).in_("item_id", vastgehouden).execute()
    return {"url": sessie.url}


def _geef_vrij(db, item_ids: list[str]) -> None:
    if item_ids:
        try:
            db.table("revaleur_reserveringen").delete().in_("item_id", item_ids).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("[revaleur] vrijgeven mislukt: %s", e)


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    geheim = settings.revaleur_stripe_webhook_secret or settings.stripe_webhook_secret
    payload = await request.body()
    try:
        ev = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), geheim)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Ongeldige handtekening")
    sessie = ev["data"]["object"]
    if (sessie.get("metadata") or {}).get("bron") != "revaleur":
        return {"genegeerd": True}       # een abonnementsbetaling van Omnivaleur: die loopt via billing.py
    db = get_db()
    if ev["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        db.table("revaleur_reserveringen").delete().eq("sessie_id", sessie["id"]).execute()
        return {"vrijgegeven": True}
    if ev["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if sessie.get("payment_status") != "paid":
            return {"wacht": True}           # iDEAL/bank: komt later als async_payment_succeeded
        await verwerk_betaling(db, sessie)
        return {"ok": True}
    return {"genegeerd": True}


async def verwerk_betaling(db, sessie: dict) -> None:
    """Idempotent: Stripe kan dezelfde melding vaker sturen."""
    from backend.services.crosslist import handle_item_sold, BEWIJS_BESTELLING
    bestaand = db.table("revaleur_bestellingen").select("id").eq("stripe_sessie", sessie["id"]).execute().data
    if bestaand:
        return
    item_ids = [i for i in (sessie.get("metadata") or {}).get("item_ids", "").split(",") if i]
    items = {i["id"]: i for i in (db.table("items").select("id,sku,title,shopify_title,price,price_shopify")
                                  .in_("id", item_ids).execute().data or [])}
    klant = sessie.get("customer_details") or {}
    verzending = (sessie.get("shipping_details") or sessie.get("collected_information", {}).get("shipping_details") or {})
    adres = verzending.get("address") or klant.get("address") or {}
    regels = [{"item_id": i, "sku": items.get(i, {}).get("sku"),
               "titel": items.get(i, {}).get("shopify_title") or items.get(i, {}).get("title"),
               "prijs": float(items.get(i, {}).get("price_shopify") or items.get(i, {}).get("price") or 0)} for i in item_ids]
    totaal = (sessie.get("amount_total") or 0) / 100
    verzend = ((sessie.get("total_details") or {}).get("amount_shipping") or 0) / 100
    rij = db.table("revaleur_bestellingen").insert({
        "stripe_sessie": sessie["id"], "email": klant.get("email"), "naam": verzending.get("name") or klant.get("name"),
        "adres": adres, "land": adres.get("country"), "taal": (sessie.get("metadata") or {}).get("taal", "en"),
        "artikelen": regels, "subtotaal": round(totaal - verzend, 2), "verzendkosten": verzend, "totaal": totaal,
    }).execute().data[0]
    for r in regels:
        try:
            await handle_item_sold(r["item_id"], "revaleur", sold_price=r["prijs"], bewijs=BEWIJS_BESTELLING)
        except Exception as e:  # noqa: BLE001 — de bestelling staat vast; melding aan Daniel via het logboek
            logger.error("[revaleur] artikel %s niet overal afgemeld na bestelling %s: %s", r["item_id"], rij["id"], e)
    db.table("revaleur_reserveringen").delete().eq("sessie_id", sessie["id"]).execute()
    try:
        from backend.services.revaleur_mail import stuur_bevestiging
        stuur_bevestiging(rij)
        db.table("revaleur_bestellingen").update({"mail_bevestiging_op": _nu().isoformat()}).eq("id", rij["id"]).execute()
    except Exception as e:  # noqa: BLE001
        logger.error("[revaleur] bevestigingsmail voor bestelling %s mislukt: %s", rij["id"], e)
