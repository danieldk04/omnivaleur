"""De ENE verbinding met de losse Revaleur-webshop (revaleur/docs/koppeling.md).

Revaleur is een eigen webshop met eigen database, Stripe en mail. Voor Omnivaleur is het een verkoopkanaal zoals
Shopify: verkoopt Revaleur een artikel, dan meldt het dat hier (alleen het artikelnummer), en gaat het artikel van
alle andere kanalen af. Ondertekend met HMAC-SHA256 over de ruwe body, header X-Revaleur-Signature.
"""
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request

from backend.config import settings
from backend.database import get_db, naast_de_lus
from backend.services.crosslist import BEWIJS_BESTELLING, handle_item_sold

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/koppeling/revaleur", tags=["revaleur-koppeling"])


def _klopt(body: bytes, handtekening: str) -> bool:
    geheim = settings.revaleur_koppeling_geheim
    if not geheim:
        return False
    return hmac.compare_digest(hmac.new(geheim.encode(), body, hashlib.sha256).hexdigest(), handtekening or "")


@router.post("/verkocht")
async def verkocht(request: Request):
    body = await request.body()
    if not _klopt(body, request.headers.get("X-Revaleur-Signature", "")):
        raise HTTPException(401, "Ongeldige handtekening")
    data = json.loads(body or b"{}")
    sku = str(data.get("sku") or "").strip()
    if not sku:
        raise HTTPException(400, "sku ontbreekt")
    db = get_db()
    rij = await naast_de_lus(lambda: db.table("items").select("id").eq("user_id", settings.revaleur_user_id)
                             .eq("sku", sku).limit(1).execute())
    if not rij.data:
        # Onbekend artikelnummer: geen fout naar Revaleur (die zou eindeloos opnieuw proberen), wel in het logboek.
        logger.error("[revaleur-koppeling] verkoop van onbekende sku %r gemeld (bestelling %s)", sku, data.get("bestelling"))
        return {"gevonden": False}
    await handle_item_sold(rij.data[0]["id"], "revaleur", sold_price=data.get("prijs"), bewijs=BEWIJS_BESTELLING)
    return {"gevonden": True}
