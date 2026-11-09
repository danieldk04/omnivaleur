"""Korting per betalende vriend, toegekend als tegoed bij Stripe.

Besluit Daniel 09-11-2026. De rekenregels staan in referral_korting.py (zonder
netwerk, met tests). Dit bestand voert ze uit.

Hoe het werkt
  * Elk uur kijkt de ronde per aangebrachte vriend naar zijn BETAALDE facturen in
    Stripe (net als de creatorcommissie: de webhook mist invoice.paid, zie
    kennisbank). Per betaalde factuur krijgt de aanbrenger een tegoed op zijn
    Stripe-klantsaldo, dat zijn eigen volgende factuur verlaagt.
  * Stripe zelf is het kasboek: elk tegoed draagt in zijn metadata het
    factuurnummer van de vriend. Daardoor kan een factuur nooit twee keer
    uitbetaald worden, ook niet als de ronde crasht of twee keer draait.
  * Wordt een factuur later terugbetaald, dan draait de ronde het te veel
    gegeven tegoed terug (een positieve boeking met hetzelfde factuurnummer).
  * Alleen facturen van de laatste 90 dagen komen in aanmerking: een oude
    factuur mag geen verrassend tegoed meer opleveren.

Bewust niet gedaan: de ronde schrijft niets naar onze eigen database. Er is geen
migratie nodig en er is dus niets wat uit de pas kan lopen met Stripe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import stripe

from backend.config import settings
from backend.services.referral_korting import korting_cents

logger = logging.getLogger(__name__)

BRON = "vriendenkorting"
LEEFTIJD_MAX_DAGEN = 90


def _g(obj, sleutel, standaard=None):
    """Veldlezer die tegen een dict EN een Stripe-object werkt (SDK 10.x op de
    server geeft dict-achtige objecten, 15.x niet). Zie kennisbank
    "stripe-twee-api-versies-tegelijk"."""
    try:
        waarde = obj[sleutel]
    except (KeyError, TypeError, AttributeError, IndexError):
        return standaard
    return standaard if waarde is None else waarde


def _ts(waarde) -> datetime | None:
    if waarde is None:
        return None
    if isinstance(waarde, datetime):
        return waarde if waarde.tzinfo else waarde.replace(tzinfo=timezone.utc)
    if isinstance(waarde, (int, float)):
        return datetime.fromtimestamp(waarde, tz=timezone.utc)
    return None


def plan_van_abonnement(sub) -> str | None:
    """'light' of 'pro' uit de prijs van het abonnement. None als het niet te
    lezen is: dan telt de vriend niet mee (liever te weinig dan te veel)."""
    try:
        items = _g(_g(sub, "items", {}), "data", []) or []
        if not items:
            return None
        pid = _g(_g(items[0], "price", {}), "id")
        if not pid:
            return None
        light = (settings.stripe_price_id_light or "").strip()
        return "light" if light and pid == light else "pro"
    except Exception:
        logger.exception("Kon het plan van een abonnement niet lezen")
        return None


def maandprijs_cents(sub) -> int | None:
    """Wat dit abonnement per maand kost (bruto). None als het niet te lezen is."""
    try:
        items = _g(_g(sub, "items", {}), "data", []) or []
        if not items:
            return None
        bedrag = _g(_g(items[0], "price", {}), "unit_amount")
        aantal = _g(items[0], "quantity", 1) or 1
        return int(bedrag) * int(aantal) if bedrag else None
    except Exception:
        logger.exception("Kon de maandprijs niet lezen")
        return None


def _boekingen_per_factuur(klant_id: str) -> dict[str, int]:
    """Per vriendenfactuur: wat er netto aan tegoed gegeven is (positief getal).

    Een tegoed is een negatieve boeking op het saldo, een terugdraaiing een
    positieve. Alleen boekingen met onze eigen bron tellen.
    """
    uit: dict[str, int] = {}
    for t in stripe.Customer.list_balance_transactions(klant_id, limit=100).auto_paging_iter():
        md = _g(t, "metadata", {}) or {}
        if _g(md, "bron") != BRON:
            continue
        fid = _g(md, "vriend_factuur")
        if fid:
            uit[fid] = uit.get(fid, 0) - int(_g(t, "amount", 0) or 0)
    return uit


def _huidig_tegoed_cents(klant_id: str) -> int:
    """Niet-verbruikt tegoed van de aanbrenger (positief). Stripe slaat tegoed op
    als negatief saldo."""
    saldo = int(_g(stripe.Customer.retrieve(klant_id), "balance", 0) or 0)
    return max(0, -saldo)


def verwerk_vriend(*, aanbrenger_klant_id: str, eigen_maandprijs_cents: int,
                   vriend_id: str, vriend_plan: str | None, facturen: list[dict],
                   nu: datetime | None = None) -> dict:
    """Legt het tegoed voor één vriend vast. Alleen Stripe, geen database.

    facturen: lijst van {"id", "bruto_cents", "terug_cents", "paid_at"} voor alle
        betaalde facturen van de vriend (ook oudere dan 90 dagen: de datum van
        zijn EERSTE betaling bepaalt of hij 10 of 5 euro oplevert).
    Geeft {"toegekend": cents, "teruggedraaid": cents, "overgeslagen": n} terug.
    """
    nu = nu or datetime.now(timezone.utc)
    uit = {"toegekend": 0, "teruggedraaid": 0, "overgeslagen": 0}
    betaalde = [f for f in facturen if int(f.get("bruto_cents") or 0) > 0 and f.get("paid_at")]
    if not betaalde:
        return uit
    betaalde.sort(key=lambda f: f["paid_at"])
    eerste = betaalde[0]["paid_at"]
    grens = nu - timedelta(days=LEEFTIJD_MAX_DAGEN)
    gegeven = _boekingen_per_factuur(aanbrenger_klant_id)

    for f in betaalde:
        fid = f["id"]
        betaald = int(f["bruto_cents"]) - int(f.get("terug_cents") or 0)
        al = gegeven.get(fid, 0)
        if fid in gegeven:
            # Al behandeld. Alleen terugdraaien als er na een teruggave te veel
            # tegoed staat; nooit opnieuw geven.
            toegestaan = korting_cents(
                vriend_plan=vriend_plan, vriend_betaald_cents=betaald,
                vriend_eerste_betaling_op=eerste,
                eigen_maandprijs_cents=eigen_maandprijs_cents, huidig_tegoed_cents=0)
            te_veel = al - toegestaan
            if te_veel > 0:
                stripe.Customer.create_balance_transaction(
                    aanbrenger_klant_id, amount=te_veel, currency="eur",
                    description="Omnivaleur: tegoed vriendenkorting teruggedraaid",
                    metadata={"bron": BRON, "vriend_factuur": fid, "vriend": vriend_id,
                              "soort": "terugdraaien"},
                    idempotency_key=f"{BRON}-terug-{fid}-{betaald}")
                uit["teruggedraaid"] += te_veel
            continue
        if f["paid_at"] < grens:
            uit["overgeslagen"] += 1
            continue
        bedrag = korting_cents(
            vriend_plan=vriend_plan, vriend_betaald_cents=betaald,
            vriend_eerste_betaling_op=eerste,
            eigen_maandprijs_cents=eigen_maandprijs_cents,
            huidig_tegoed_cents=_huidig_tegoed_cents(aanbrenger_klant_id))
        if bedrag <= 0:
            uit["overgeslagen"] += 1
            continue
        stripe.Customer.create_balance_transaction(
            aanbrenger_klant_id, amount=-bedrag, currency="eur",
            description="Omnivaleur: korting voor een betalende vriend",
            metadata={"bron": BRON, "vriend_factuur": fid, "vriend": vriend_id,
                      "soort": "tegoed"},
            idempotency_key=f"{BRON}-{fid}")
        uit["toegekend"] += bedrag
    return uit
