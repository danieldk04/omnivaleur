"""Wat betalende vrienden ontgrendelen: 3 vrienden = AI-pakket en Etsy, 5 vrienden = Ultra.

Alleen een vriend die NU betaalt op Pro of hoger telt (zelfde regel als de korting,
referral_korting.telt_mee). Stopt een vriend, dan vervalt het voordeel vanzelf
omdat er elke keer opnieuw geteld wordt. Het antwoord wordt 2 minuten onthouden.
Alles staat achter referral_korting_aan; uit = niemand krijgt iets extra.
Bij een storing: niets ontgrendelen en niets afnemen wat al gold is niet mogelijk
want we weten het niet, dus de aanroeper valt terug op het gewone plan.
"""
from __future__ import annotations

import logging
import time

from backend.config import settings
from backend.database import execute_with_retry, get_db
from backend.services.referral_korting import telt_mee

logger = logging.getLogger(__name__)

DREMPEL_AI = 3
DREMPEL_ETSY = 3     # besluit Daniel 27-11-2026: Etsy op dezelfde trede als het AI-pakket
DREMPEL_ULTRA = 5
_TTL = 120
_cache: dict[str, tuple[float, int]] = {}


def vergeet(user_id: str | None = None) -> None:
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(user_id, None)


def betalende_vrienden(user_id: str) -> int:
    if not settings.referral_korting_aan or not user_id:
        return 0
    nu = time.monotonic()
    hit = _cache.get(user_id)
    if hit and hit[0] > nu:
        return hit[1]
    try:
        from backend.services.referral_codes import codes_van
        from backend.services.referral_rewards import BETALEND
        codes = [c["code"] for c in codes_van(user_id)]
        if not codes:
            n = 0
        else:
            db = get_db()
            ids = [r["user_id"] for r in (execute_with_retry(
                db.table("referrals").select("user_id").in_("code", codes)).data or [])
                if r["user_id"] != user_id]
            n = 0
            if ids:
                abos = execute_with_retry(
                    db.table("subscriptions")
                    .select("user_id,status,plan,stripe_subscription_id")
                    .in_("user_id", ids)).data or []
                n = sum(1 for a in abos
                        if a.get("status") in BETALEND and a.get("stripe_subscription_id")
                        and telt_mee(a.get("plan")))
    except Exception:
        logger.exception("Kon betalende vrienden van %s niet tellen", user_id)
        return 0
    _cache[user_id] = (nu + _TTL, n)
    return n


def heeft_ultra_via_vrienden(user_id: str) -> bool:
    return betalende_vrienden(user_id) >= DREMPEL_ULTRA


def heeft_ai_via_vrienden(user_id: str) -> bool:
    return betalende_vrienden(user_id) >= DREMPEL_AI


def heeft_etsy_via_vrienden(user_id: str) -> bool:
    return betalende_vrienden(user_id) >= DREMPEL_ETSY
