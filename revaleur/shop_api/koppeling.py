"""De smalle brug tussen Revaleur en Omnivaleur (docs/koppeling.md).

Twee berichten, beide ondertekend met HMAC-SHA256 over de ruwe body (header X-Revaleur-Signature):
  Revaleur -> Omnivaleur  POST {omnivaleur_url}/api/koppeling/revaleur/verkocht   {sku, bestelling, prijs}
  Omnivaleur -> Revaleur  POST {api_url}/api/revaleur/koppeling/afmelden          {sku}
Alleen het artikelnummer (sku) is gedeeld. Geen database, geen gebruikers-id's, geen sleutels.
"""
import hashlib
import hmac
import json
import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)
KOP = "X-Revaleur-Signature"


def onderteken(body: bytes, geheim: str | None = None) -> str:
    return hmac.new((geheim or settings.koppeling_geheim).encode(), body, hashlib.sha256).hexdigest()


def klopt(body: bytes, handtekening: str, geheim: str | None = None) -> bool:
    geheim = geheim or settings.koppeling_geheim
    return bool(geheim) and hmac.compare_digest(onderteken(body, geheim), handtekening or "")


def meld_verkoop_aan_omnivaleur(sku: str, bestelling: int, prijs: float) -> bool:
    """True als Omnivaleur het artikel op de andere kanalen heeft afgemeld."""
    body = json.dumps({"sku": sku, "bestelling": bestelling, "prijs": prijs}).encode()
    try:
        r = httpx.post(f"{settings.omnivaleur_url.rstrip('/')}/api/koppeling/revaleur/verkocht", content=body,
                       headers={KOP: onderteken(body), "Content-Type": "application/json"}, timeout=20)
        return r.status_code < 300
    except Exception as e:  # noqa: BLE001
        logger.error("[koppeling] Omnivaleur niet bereikt voor sku %s: %s", sku, e)
        return False


def bouw_site_opnieuw() -> None:
    """Best effort: de statische site volgt de voorraad."""
    if settings.deploy_hook:
        try:
            httpx.post(settings.deploy_hook, timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("[koppeling] deploy hook mislukt: %s", e)
