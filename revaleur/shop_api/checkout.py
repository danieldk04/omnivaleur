"""Revaleur-webshop: afrekenen en afhandelen. Staat los van Omnivaleur (eigen database, Stripe en mail).

  POST /api/revaleur/checkout           winkelmand -> reserveren -> Stripe Checkout-sessie
  POST /api/revaleur/stripe-webhook     betaald -> bestelling, artikel verkocht, mail, Omnivaleur melden
  POST /api/revaleur/koppeling/afmelden Omnivaleur: artikel is elders verkocht, hier van de site (ondertekend)

Eén exemplaar per artikel: de reservering (tabel reserveringen) houdt een artikel 30 minuten vast.
Een tweede koper krijgt `verkocht`. Verlopen of mislukte betaling geeft het artikel vrij. De prijs komt van
de server; de browser stuurt de getoonde prijs mee en bij een verschil weigeren we (409).
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import koppeling
from .config import settings
from .db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/revaleur", tags=["revaleur"])

RESERVERING_MINUTEN = 30
MAX_ARTIKELEN = 20
EU = {"AT", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT",
      "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
# Verzendbeleid (docs/beleid/policies_shipping-policy.txt): NL en BE gratis; EU 3,95; buiten EU 4,95; gratis vanaf 100.
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
    ids: list[str] = Field(..., min_length=1, max_length=MAX_ARTIKELEN)   # product-id's uit de statische site
    prijzen: dict[str, float] | None = None                                # getoonde prijs per id
    land: str = "NL"
    taal: str = "en"


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def _beschikbaar(db, ids: list[str]) -> dict[str, dict]:
    rijen = db.table("producten").select("id,sku,titel,prijs,fotos,status").in_("id", ids).eq("status", "beschikbaar").execute().data or []
    return {r["id"]: r for r in rijen}


def _geef_vrij(db, ids: list[str]) -> None:
    if ids:
        try:
            db.table("reserveringen").delete().in_("product_id", ids).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning("[revaleur] vrijgeven mislukt: %s", e)


@router.post("/checkout")
async def checkout(body: CheckoutIn):
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe is niet ingesteld")
    zone = body.land if body.land in ZONES else "INT"
    ids = list(dict.fromkeys(body.ids))
    db = get_db()
    try:
        db.table("reserveringen").delete().lt("tot", _nu().isoformat()).execute()
        gevonden = _beschikbaar(db, ids)
    except Exception as e:  # noqa: BLE001
        logger.error("[revaleur] database onbereikbaar bij afrekenen: %s", e)
        raise HTTPException(503, "Afrekenen is tijdelijk niet beschikbaar")
    weg = [i for i in ids if i not in gevonden]
    if weg:
        raise HTTPException(409, {"verkocht": weg})
    if body.prijzen:
        afwijkend = [i for i in ids if i in body.prijzen and abs(body.prijzen[i] - float(gevonden[i]["prijs"])) > 0.01]
        if afwijkend:
            raise HTTPException(409, {"prijs_gewijzigd": afwijkend})

    # Reserveren: de primaire sleutel op product_id laat precies één koper slagen.
    tot = (_nu() + timedelta(minutes=RESERVERING_MINUTEN + 1)).isoformat()
    tijdelijk = f"pending-{int(time.time() * 1000)}"
    vast, bezet = [], []
    for pid in ids:
        try:
            db.table("reserveringen").insert({"product_id": pid, "sessie_id": tijdelijk, "tot": tot}).execute()
            vast.append(pid)
        except Exception:  # noqa: BLE001 — bezet (unieke sleutel) of database-fout
            bezet.append(pid)
    if bezet:
        _geef_vrij(db, vast)
        raise HTTPException(409, {"verkocht": bezet})

    subtotaal = round(sum(float(gevonden[i]["prijs"]) for i in ids), 2)
    kosten = verzendkosten(zone, subtotaal)
    regels = [{"quantity": 1, "price_data": {
        "currency": "eur", "unit_amount": int(round(float(gevonden[i]["prijs"]) * 100)),
        "product_data": {"name": gevonden[i]["titel"][:250],
                         "images": [f["src"] for f in (gevonden[i].get("fotos") or [])[:1]],
                         "metadata": {"product_id": i, "sku": gevonden[i].get("sku") or ""}}}} for i in ids]
    site = settings.site_url.rstrip("/")
    pre = "/nl" if body.taal == "nl" else ""
    try:
        sessie = stripe.checkout.Session.create(
            api_key=settings.stripe_secret_key, mode="payment", line_items=regels,
            shipping_address_collection={"allowed_countries": ZONES[zone][1]},
            shipping_options=[{"shipping_rate_data": {
                "type": "fixed_amount", "display_name": "Free shipping" if kosten == 0 else "Standard shipping",
                "fixed_amount": {"amount": int(round(kosten * 100)), "currency": "eur"}}}],
            payment_method_types=["ideal", "card"] if zone in ("NL", "BE", "EU") else ["card"],
            locale="nl" if body.taal == "nl" else "en",
            expires_at=int(time.time()) + RESERVERING_MINUTEN * 60,
            metadata={"bron": "revaleur", "product_ids": ",".join(ids), "taal": body.taal},
            success_url=f"{site}{pre}/bedankt", cancel_url=f"{site}{pre}/cart",
            phone_number_collection={"enabled": True},
        )
    except Exception as e:  # noqa: BLE001
        _geef_vrij(db, vast)
        logger.error("[revaleur] Stripe weigerde de sessie: %s", e)
        raise HTTPException(503, "Afrekenen is tijdelijk niet beschikbaar")
    db.table("reserveringen").update({"sessie_id": sessie.id}).in_("product_id", vast).execute()
    return {"url": sessie.url}


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        ev = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Ongeldige handtekening")
    sessie = ev["data"]["object"]
    db = get_db()
    if ev["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        db.table("reserveringen").delete().eq("sessie_id", sessie["id"]).execute()
        return {"vrijgegeven": True}
    if ev["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if sessie.get("payment_status") != "paid":
            return {"wacht": True}           # iDEAL/bank: komt later als async_payment_succeeded
        verwerk_betaling(db, sessie)
        return {"ok": True}
    return {"genegeerd": True}


def verwerk_betaling(db, sessie: dict) -> None:
    """Idempotent: Stripe kan dezelfde melding vaker sturen."""
    from .mail import stuur_bevestiging
    if db.table("bestellingen").select("id").eq("stripe_sessie", sessie["id"]).execute().data:
        return
    ids = [i for i in (sessie.get("metadata") or {}).get("product_ids", "").split(",") if i]
    prod = {p["id"]: p for p in (db.table("producten").select("id,sku,titel,prijs").in_("id", ids).execute().data or [])}
    klant = sessie.get("customer_details") or {}
    verz = sessie.get("shipping_details") or (sessie.get("collected_information") or {}).get("shipping_details") or {}
    adres = verz.get("address") or klant.get("address") or {}
    regels = [{"product_id": i, "sku": prod.get(i, {}).get("sku"), "titel": prod.get(i, {}).get("titel"),
               "prijs": float(prod.get(i, {}).get("prijs") or 0)} for i in ids]
    totaal = (sessie.get("amount_total") or 0) / 100
    verzend = ((sessie.get("total_details") or {}).get("amount_shipping") or 0) / 100
    rij = db.table("bestellingen").insert({
        "stripe_sessie": sessie["id"], "email": klant.get("email"), "naam": verz.get("name") or klant.get("name"),
        "adres": adres, "land": adres.get("country"), "taal": (sessie.get("metadata") or {}).get("taal", "en"),
        "artikelen": regels, "subtotaal": round(totaal - verzend, 2), "verzendkosten": verzend, "totaal": totaal,
    }).execute().data[0]
    db.table("producten").update({"status": "verkocht"}).in_("id", ids).execute()
    # Eén sku is één fysiek stuk: een dubbele advertentie van hetzelfde stuk verdwijnt mee.
    db.table("producten").update({"status": "verkocht"}).in_("sku", [r["sku"] for r in regels if r["sku"]]).execute()
    db.table("reserveringen").delete().eq("sessie_id", sessie["id"]).execute()
    alles_gemeld = True
    for r in regels:
        if not koppeling.meld_verkoop_aan_omnivaleur(r["sku"], rij.get("nummer"), r["prijs"]):
            alles_gemeld = False
            logger.error("[revaleur] verkoop van %s niet aan Omnivaleur gemeld (bestelling %s); opnieuw proberen", r["sku"], rij["id"])
    if alles_gemeld:
        db.table("bestellingen").update({"omnivaleur_gemeld_op": _nu().isoformat()}).eq("id", rij["id"]).execute()
    koppeling.bouw_site_opnieuw()
    try:
        stuur_bevestiging(rij)
        db.table("bestellingen").update({"mail_bevestiging_op": _nu().isoformat()}).eq("id", rij["id"]).execute()
    except Exception as e:  # noqa: BLE001
        logger.error("[revaleur] bevestigingsmail voor bestelling %s mislukt: %s", rij["id"], e)


@router.post("/koppeling/afmelden")
async def afmelden(request: Request):
    """Omnivaleur: dit artikel is op een ander kanaal verkocht. Alleen met geldige handtekening."""
    body = await request.body()
    if not koppeling.klopt(body, request.headers.get(koppeling.KOP, "")):
        raise HTTPException(401, "Ongeldige handtekening")
    sku = json.loads(body or b"{}").get("sku")
    if not sku:
        raise HTTPException(400, "sku ontbreekt")
    db = get_db()
    db.table("producten").update({"status": "verkocht"}).eq("sku", sku).eq("status", "beschikbaar").execute()
    koppeling.bouw_site_opnieuw()
    return {"ok": True}


@router.get("/health")
async def health():
    return {"ok": True, "dienst": "revaleur"}
