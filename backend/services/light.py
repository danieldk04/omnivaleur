"""Omnivaleur Light: het goedkope plan voor particulieren, tot 20 actieve artikelen.

Een 'actief artikel' is een artikel met minstens één advertentie die draait of
klaarstaat (active, hidden, pending, relisting). Verkocht, verlopen of weggehaald
telt niet meer mee, dus wie verkoopt maakt vanzelf weer ruimte.

De limiet geldt voor NIEUWE artikelen die live gaan. Wat al online staat blijft
gewoon onderhouden (verversen, verlengen, afmelden bij verkoop), ook als iemand
na een import boven de 20 zit. Alleen Pro-klanten en de eigenaar hebben geen
limiet. Een storing bij het nakijken laat altijd door: niemand buitensluiten
omdat onze eigen telling haperde.
"""
import logging

from backend.config import settings
from backend.database import fetch_all

logger = logging.getLogger(__name__)

PLAN_PRO = "pro"
PLAN_LIGHT = "light"
LIGHT_MAX_ARTIKELEN = 20

# Dezelfde lijst als _LEVENDE_STATUS in services/crosslist.py.
LEVENDE_STATUS = ["active", "hidden", "pending", "relisting"]
# Wat echt online staat, zonder de advertenties die nog moeten verschijnen.
ONLINE_STATUS = ["active", "hidden", "relisting"]

LIGHT_LIMIET_MELDING = (
    f"Omnivaleur Light includes up to {LIGHT_MAX_ARTIKELEN} active items and you have reached that. "
    "Mark something as sold, or upgrade to Pro for unlimited items."
)


def plan_uit_stripe(stripe_sub) -> str:
    """'light' als het abonnement op de Light-prijs loopt, anders 'pro'.

    Staat de Light-prijs niet in de instellingen, dan is alles 'pro': liever geen
    limiet dan een klant die we ten onrechte beperken.
    """
    light_id = (settings.stripe_price_id_light or "").strip()
    if not light_id or not stripe_sub:
        return PLAN_PRO
    try:
        items = (stripe_sub.get("items") or {}).get("data") or []
    except AttributeError:
        return PLAN_PRO
    for it in items:
        prijs = it.get("price") or {}
        pid = prijs.get("id") if isinstance(prijs, dict) else getattr(prijs, "id", None)
        if pid == light_id:
            return PLAN_LIGHT
    return PLAN_PRO


def plan_van_gebruiker(user_id: str) -> str:
    """Het plan uit de (een minuut onthouden) abonnementsrij. Bij twijfel 'pro'."""
    try:
        from backend.services.billing import _fetch_subscription
        sub = _fetch_subscription(user_id)
    except Exception:  # noqa: BLE001 — een storing mag niemand beperken
        logger.exception("Kon het plan van %s niet nagaan, geen limiet toegepast", user_id)
        return PLAN_PRO
    return (sub or {}).get("plan") or PLAN_PRO


def is_light(user_id: str) -> bool:
    return plan_van_gebruiker(user_id) == PLAN_LIGHT


def actieve_artikelen(db, user_id: str, statussen=None) -> set[str]:
    """De id's van de artikelen van deze gebruiker met een draaiende advertentie."""
    statussen = statussen or LEVENDE_STATUS

    def bouw():
        return (db.table("listings")
                .select("id,item_id,items!inner(user_id)")
                .eq("items.user_id", user_id)
                .in_("status", statussen))

    return {r["item_id"] for r in fetch_all(bouw, page_size=1000) if r.get("item_id")}


def ruimte_over(db, user_id: str) -> int | None:
    """Hoeveel nieuwe artikelen mogen er nog bij? None = geen limiet.

    Bij een fout ook None: dan laten we door.
    """
    if not is_light(user_id):
        return None
    try:
        return max(0, LIGHT_MAX_ARTIKELEN - len(actieve_artikelen(db, user_id)))
    except Exception:  # noqa: BLE001
        logger.exception("Kon de artikelen van %s niet tellen, geen limiet toegepast", user_id)
        return None


def publicatie_geblokkeerd(db, user_id: str, item_id: str) -> str | None:
    """Reden waarom dit artikel niet live mag, of None als het mag.

    Een artikel dat al draait (op een ander kanaal) telt al mee en mag dus altijd
    naar een extra kanaal.
    """
    if not is_light(user_id):
        return None
    try:
        actief = actieve_artikelen(db, user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Kon de artikelen van %s niet tellen, geen limiet toegepast", user_id)
        return None
    if str(item_id) in actief or len(actief) < LIGHT_MAX_ARTIKELEN:
        return None
    return LIGHT_LIMIET_MELDING


def neem_plaatsing_terug_boven_limiet(db, user_id: str, job: dict) -> bool:
    """Laatste zeef in get_pending_jobs, voor elk pad dat een 'create' klaarzet.

    Geeft True als de opdracht is teruggenomen. Alleen een 'create' voor een
    artikel dat nog nergens online staat telt: verversen en een extra kanaal voor
    een artikel dat al draait gaan door.
    """
    if job.get("action") != "create" or not job.get("item_id"):
        return False
    pl = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    if pl.get("_refresh_rollback"):
        return False
    if not is_light(user_id):
        return False
    try:
        online = actieve_artikelen(db, user_id, ONLINE_STATUS)
    except Exception as e:  # noqa: BLE001
        logger.warning("job %s: Light-limiet niet na te gaan: %s", job.get("id"), e)
        return False
    if str(job["item_id"]) in online or len(online) < LIGHT_MAX_ARTIKELEN:
        return False
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.table("jobs").update({
            "status": "cancelled",
            "result": {"cancelled": "light limit", "error": LIGHT_LIMIET_MELDING},
            "done_at": now,
        }).eq("id", job["id"]).eq("status", "pending").execute()
        db.table("listings").update({"status": "error", "error_message": LIGHT_LIMIET_MELDING}).eq(
            "item_id", job["item_id"]).eq("platform", job.get("platform")).eq("status", "pending").execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("job %s: Light-limiet niet kunnen toepassen: %s", job.get("id"), e)
        return False
    logger.warning("job %s: %s staat op de Light-limiet, plaatsing niet uitgedeeld", job.get("id"), user_id)
    return True
