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


def _terugbetaald_per_sleutel(klant_id: str) -> dict[str, int]:
    """Teruggaven per factuurnummer EN per payment_intent.

    Waarom beide: in de oude Stripe-API (gepinde SDK op de server) hangt een
    betaling met `invoice` aan de factuur, in de nieuwe API bestaat dat veld niet
    meer en loopt de koppeling via de payment_intent. Gemeten 09-11-2026 in
    testmodus: met alleen `invoice` bleef een teruggave onzichtbaar op de nieuwe API.
    Mislukt het lezen, dan geldt "niets teruggegeven" en volgt het volgende uur een
    nieuwe poging.
    """
    uit: dict[str, int] = {}
    try:
        for charge in stripe.Charge.list(customer=klant_id, limit=100).auto_paging_iter():
            terug = int(_g(charge, "amount_refunded", 0) or 0)
            for sleutel in (_g(charge, "invoice"), _g(charge, "payment_intent")):
                if sleutel:
                    uit[sleutel] = uit.get(sleutel, 0) + terug
    except Exception:
        logger.exception("Kon teruggaven niet lezen voor %s", klant_id)
    return uit


def _id_van(waarde) -> str | None:
    """Een verwijzing is soms een id en soms een uitgeklapt object."""
    if isinstance(waarde, str):
        return waarde
    return _g(waarde, "id") if waarde else None


def _payment_intent_van_factuur(f) -> str | None:
    """Oude API: veld op de factuur. Nieuwe API: via de (uitgeklapte) betalingen."""
    pi = _id_van(_g(f, "payment_intent"))
    if pi:
        return pi
    for p in _g(_g(f, "payments", {}), "data", []) or []:
        pi = _id_van(_g(_g(p, "payment", {}), "payment_intent"))
        if pi:
            return pi
    return None


def _betaalde_facturen(klant_id: str):
    """Betaalde facturen, met de betalingen uitgeklapt waar de API dat kent."""
    try:
        return list(stripe.Invoice.list(customer=klant_id, status="paid", limit=100,
                                        expand=["data.payments"]).auto_paging_iter())
    except Exception:
        # De oude API kent `payments` niet en weigert het uitklappen.
        return list(stripe.Invoice.list(customer=klant_id, status="paid",
                                        limit=100).auto_paging_iter())


def facturen_van_klant(klant_id: str) -> list[dict]:
    """Alle betaalde facturen van een klant, in de vorm die verwerk_vriend wil."""
    teruggaven = _terugbetaald_per_sleutel(klant_id)
    uit = []
    for f in _betaalde_facturen(klant_id):
        fid = _g(f, "id")
        if not fid:
            continue
        pi = _payment_intent_van_factuur(f)
        uit.append({
            "id": fid,
            "bruto_cents": int(_g(f, "amount_paid", 0) or 0),
            "terug_cents": max(teruggaven.get(fid, 0), teruggaven.get(pi, 0) if pi else 0),
            "paid_at": (_ts(_g(_g(f, "status_transitions", {}), "paid_at"))
                        or _ts(_g(f, "created"))),
        })
    return uit


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


async def verwerk_vriendenkorting() -> dict:
    """Draait elk uur (zolang de vlag referral_korting_aan aan staat): per
    aangebrachte vriend van een klant legt het zijn betaalde facturen vast als
    tegoed bij de aanbrenger. Een fout bij één vriend stopt de rest niet."""
    uit = {"vrienden": 0, "toegekend": 0, "teruggedraaid": 0, "overgeslagen": 0, "fout": 0}
    if not settings.referral_korting_aan or not settings.stripe_secret_key:
        return uit

    from backend.database import execute_with_retry, get_db
    from backend.services.referral_rewards import _is_eigenaar

    db = get_db()
    try:
        verwijzingen = execute_with_retry(db.table("referrals").select("user_id, code")).data or []
        eigenaar_per_code = {c["code"]: c.get("owner_user_id") for c in (execute_with_retry(
            db.table("referral_codes").select("code, owner_user_id")).data or [])}
    except Exception as e:
        logger.error("Vriendenkortingronde overgeslagen (%s)", e)
        return uit

    paren = [(v["user_id"], eigenaar_per_code.get(v.get("code"))) for v in verwijzingen]
    # Alleen klantcodes: een creatorcode heeft geen eigenaar en loopt via geld.
    paren = [(vriend, aanbrenger) for vriend, aanbrenger in paren
             if aanbrenger and aanbrenger != vriend]
    if not paren:
        return uit

    ids = sorted({x for p in paren for x in p})
    try:
        abos = {r["user_id"]: r for r in (execute_with_retry(
            db.table("subscriptions").select(
                "user_id, status, stripe_customer_id, stripe_subscription_id")
            .in_("user_id", ids)).data or [])}
    except Exception as e:
        logger.error("Vriendenkortingronde: abonnementen niet te lezen (%s)", e)
        return uit

    prijs_per_aanbrenger: dict[str, int | None] = {}
    for vriend, aanbrenger in paren:
        v_abo, a_abo = abos.get(vriend) or {}, abos.get(aanbrenger) or {}
        try:
            if (a_abo.get("status") == "complimentary" or not a_abo.get("stripe_customer_id")
                    or not a_abo.get("stripe_subscription_id")
                    or not v_abo.get("stripe_customer_id")
                    or not v_abo.get("stripe_subscription_id")
                    or _is_eigenaar(aanbrenger)):
                uit["overgeslagen"] += 1
                continue
            if aanbrenger not in prijs_per_aanbrenger:
                prijs_per_aanbrenger[aanbrenger] = maandprijs_cents(
                    stripe.Subscription.retrieve(a_abo["stripe_subscription_id"]))
            prijs = prijs_per_aanbrenger[aanbrenger]
            plan = plan_van_abonnement(stripe.Subscription.retrieve(v_abo["stripe_subscription_id"]))
            if not prijs or not plan:
                # Niet te lezen: liever niets toekennen dan iets onverantwoords.
                uit["overgeslagen"] += 1
                continue
            r = verwerk_vriend(
                aanbrenger_klant_id=a_abo["stripe_customer_id"], eigen_maandprijs_cents=prijs,
                vriend_id=vriend, vriend_plan=plan,
                facturen=facturen_van_klant(v_abo["stripe_customer_id"]))
            uit["vrienden"] += 1
            uit["toegekend"] += r["toegekend"]
            uit["teruggedraaid"] += r["teruggedraaid"]
        except Exception:
            uit["fout"] += 1
            logger.exception("Vriendenkorting mislukt voor vriend %s", vriend)
    if uit["toegekend"] or uit["teruggedraaid"] or uit["fout"]:
        logger.info("Vriendenkortingronde: %s", uit)
    return uit
