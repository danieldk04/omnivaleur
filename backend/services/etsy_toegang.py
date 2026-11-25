"""Wie mag Etsy gebruiken?

Etsy gaf Omnivaleur Personal Access (25-11-2026): beperkte schaal. Daniel wil Etsy
alleen voor Ultra, of te verdienen met 5 betalende vrienden (zelfde regel als Ultra
zelf, zie light.plan_van_gebruiker). De eigenaar mag altijd, om te kunnen testen.
"""
from __future__ import annotations
import logging
import time

logger = logging.getLogger(__name__)


_cache: dict[str, tuple[float, bool]] = {}


def etsy_toegang(user_id: str) -> bool:
    """Vijf minuten onthouden: de kanalenlijst vraagt dit bij elke schermverversing."""
    nu = time.time()
    hit = _cache.get(user_id)
    if hit and hit[0] > nu:
        return hit[1]
    antwoord = _bereken(user_id)
    _cache[user_id] = (nu + 300, antwoord)
    return antwoord


def _bereken(user_id: str) -> bool:
    try:
        from backend.services.billing import is_owner_email
        from backend.services.referral_mail import email_van
        if is_owner_email(email_van(user_id)):
            return True
    except Exception:  # noqa: BLE001
        logger.exception("Eigenaarscontrole voor Etsy mislukt")
    try:
        from backend.services.light import plan_van_gebruiker
        return plan_van_gebruiker(user_id) == "ultra"
    except Exception:  # noqa: BLE001
        logger.exception("Plan niet na te gaan voor Etsy-toegang")
        return False


GEEN_TOEGANG = ("Etsy is part of the Ultra plan, or you unlock it by inviting 5 paying friends.")
