"""Wie mag Etsy gebruiken? Nu de eigenaar en de testverkopers (etsy_open_voor_ultra staat uit).

Etsy gaf Omnivaleur Personal Access (25-11-2026): beperkte schaal. Daniel wil Etsy
voor Ultra, of te verdienen met 3 betalende vrienden (besluit 27-11-2026; 5 vrienden
geven Ultra zelf, zie light.plan_van_gebruiker). De eigenaar mag altijd, om te kunnen testen.
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


def _testgebruikers() -> set[str]:
    from backend.config import settings
    return {a.strip().lower() for a in (settings.etsy_testgebruikers or "").split(",") if a.strip()}


def _bereken(user_id: str) -> bool:
    try:
        from backend.services.billing import is_owner_email
        from backend.services.referral_mail import email_van
        adres = email_van(user_id)
        if is_owner_email(adres):
            return True
        if adres and adres.strip().lower() in _testgebruikers():
            return True
    except Exception:  # noqa: BLE001
        logger.exception("Eigenaarscontrole voor Etsy mislukt")
    from backend.config import settings
    if not settings.etsy_open_voor_ultra:
        return False
    try:
        from backend.services.light import plan_van_gebruiker
        if plan_van_gebruiker(user_id) == "ultra":
            return True
    except Exception:  # noqa: BLE001
        logger.exception("Plan niet na te gaan voor Etsy-toegang")
    try:
        from backend.services.vriendenvoordeel import heeft_etsy_via_vrienden
        return bool(heeft_etsy_via_vrienden(user_id))
    except Exception:  # noqa: BLE001
        logger.exception("Vrienden niet na te gaan voor Etsy-toegang")
        return False


GEEN_TOEGANG = ("Etsy is part of the Ultra plan, or you unlock it by inviting 3 paying friends.")
