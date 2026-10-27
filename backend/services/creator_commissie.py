"""Commissie voor creators: een percentage van wat hun klanten echt betalen.

De afspraak in de creatormail is "25% van wat klanten betalen die via jouw link
komen". Dit bestand legt per betaalde factuur vast wat dat is, zodat Daniel op
elk moment kan zien wat hij wie verschuldigd is. Het maakt zelf nooit geld over.

Drie keuzes die je niet moet omdraaien:

  * Gerekend wordt over het NETTO bedrag: wat de klant betaalde zonder btw en na
    een eventuele korting of teruggave. Over btw betaal je geen commissie, die
    gaat naar de belasting.
  * De bron is Stripe zelf, niet de webhook. De webhook mist invoice.paid
    (zie kennisbank), dus zou een creator geld mislopen zonder dat iemand het
    merkt. De uurronde kijkt per aangebrachte klant zelf naar de betaalde
    facturen.
  * Uitbetaalbaar is een betaling pas 60 dagen na de betaling. SEPA-incasso
    mag 8 weken zonder reden teruggedraaid worden; eerder uitbetalen betekent
    geld betalen voor een klant die zijn geld terugkreeg. Dezelfde 60 dagen als
    de oude bounty.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import stripe

from backend.database import execute_with_retry, get_db

logger = logging.getLogger(__name__)

WACHT_DAGEN = 60
TABEL = "creator_commissie"


def _g(obj, sleutel, standaard=None):
    """Veldlezer die tegen een dict EN tegen een Stripe-object werkt.

    De gepinde SDK op de server (10.x) geeft dict-achtige objecten, een nieuwere
    (15.x) niet meer: daar bestaat .get() niet, [] wel. Zie de kennisbank bij
    "stripe-twee-api-versies-tegelijk".
    """
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
    try:
        d = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def netto_van_factuur(factuur) -> tuple[int, int]:
    """(bruto, netto) in centen van een betaalde factuur.

    Bruto is wat er echt betaald is. Netto haalt daar de btw af, naar rato als
    er minder betaald is dan het factuurtotaal (korting of tegoed). Staat het
    bedrag zonder btw er niet op, dan geldt bruto: liever iets te veel
    verschuldigd tonen dan een creator korten.
    """
    bruto = int(_g(factuur, "amount_paid", 0) or 0)
    if bruto <= 0:
        return 0, 0
    zonder_btw = _g(factuur, "total_excluding_tax")
    totaal = int(_g(factuur, "total", 0) or 0)
    if zonder_btw is None or totaal <= 0:
        return bruto, bruto
    return bruto, min(bruto, round(bruto * int(zonder_btw) / totaal))


def commissie_cents(netto: int, terugbetaald: int, bruto: int, pct: int) -> int:
    """Commissie over wat de klant na teruggaven netto heeft betaald."""
    if bruto <= 0 or pct <= 0:
        return 0
    over = max(0, min(bruto, bruto - max(0, terugbetaald)))
    return round(netto * (over / bruto) * pct / 100)


def uitbetaalbaar(rij: dict, nu: datetime | None = None) -> bool:
    nu = nu or datetime.now(timezone.utc)
    betaald = _ts(rij.get("paid_at"))
    return (rij.get("status") == "open" and betaald is not None
            and nu - betaald >= timedelta(days=WACHT_DAGEN))


def _terugbetaald_per_factuur(klant_id: str) -> dict[str, int]:
    """Teruggave per factuur, uit de betalingen van deze klant.

    Een mislukte lezing geeft een lege lijst terug: dan geldt "niets
    teruggegeven", en het volgende uur wordt het opnieuw gelezen. Omdat een
    betaling pas na 60 dagen uitbetaalbaar is en elk uur herberekend wordt,
    komt een teruggave er ruim voor de uitbetaling in.
    """
    uit: dict[str, int] = {}
    try:
        for charge in _g(stripe.Charge.list(customer=klant_id, limit=100), "data", []) or []:
            factuur = _g(charge, "invoice")
            if factuur:
                uit[factuur] = uit.get(factuur, 0) + int(_g(charge, "amount_refunded", 0) or 0)
    except Exception:
        logger.exception("Kon teruggaven niet lezen voor %s", klant_id)
    return uit


async def verwerk_commissie() -> dict:
    """Draait elk uur: legt elke betaalde factuur van aangebrachte klanten vast."""
    uit = {"nieuw": 0, "bijgewerkt": 0, "fout": 0}
    db = get_db()
    try:
        codes = {c["code"]: int(c.get("commission_pct") or 0) for c in (execute_with_retry(
            db.table("referral_codes").select("code, commission_pct, kind")
            .eq("kind", "creator")).data or []) if int(c.get("commission_pct") or 0) > 0}
        if not codes:
            return uit
        verwijzingen = [v for v in (execute_with_retry(
            db.table("referrals").select("user_id, code")).data or []) if v.get("code") in codes]
        bestaand = {r["invoice_id"]: r for r in (execute_with_retry(
            db.table(TABEL).select("invoice_id, status, commission_pct")).data or [])}
    except Exception as e:
        # Niet stil: zolang scripts/sql/creator_commissie.sql niet gedraaid is
        # hoort dat hier te staan.
        logger.error("Commissieronde overgeslagen (%s). Staat scripts/sql/"
                     "creator_commissie.sql al in Supabase?", e)
        return uit
    if not verwijzingen:
        return uit

    abos = {r["user_id"]: r for r in (execute_with_retry(
        db.table("subscriptions").select("user_id, stripe_customer_id")
        .in_("user_id", [v["user_id"] for v in verwijzingen])).data or [])}

    nu = datetime.now(timezone.utc).isoformat()
    for v in verwijzingen:
        klant_id = (abos.get(v["user_id"]) or {}).get("stripe_customer_id")
        if not klant_id:
            continue
        try:
            facturen = _g(stripe.Invoice.list(customer=klant_id, status="paid", limit=100),
                          "data", []) or []
            teruggaven = _terugbetaald_per_factuur(klant_id)
            for f in facturen:
                factuur_id = _g(f, "id")
                bruto, netto = netto_van_factuur(f)
                if not factuur_id or bruto <= 0:
                    continue
                oud = bestaand.get(factuur_id)
                if oud and oud.get("status") != "open":
                    continue  # uitbetaald is bevroren
                pct = int(oud["commission_pct"]) if oud else codes[v["code"]]
                terug = teruggaven.get(factuur_id, 0)
                betaald_op = (_ts(_g(_g(f, "status_transitions", {}), "paid_at"))
                              or _ts(_g(f, "created")) or datetime.now(timezone.utc))
                execute_with_retry(db.table(TABEL).upsert({
                    "invoice_id": factuur_id, "code": v["code"],
                    "referred_user_id": v["user_id"], "paid_at": betaald_op.isoformat(),
                    "bruto_cents": bruto, "netto_cents": netto, "terugbetaald_cents": terug,
                    "commission_pct": pct,
                    "commission_cents": commissie_cents(netto, terug, bruto, pct),
                    "updated_at": nu,
                }, on_conflict="invoice_id"))
                uit["bijgewerkt" if oud else "nieuw"] += 1
        except Exception:
            uit["fout"] += 1
            logger.exception("Commissie lezen mislukt voor %s", v["user_id"])
    if uit["nieuw"] or uit["fout"]:
        logger.info("Commissieronde: %s", uit)
    return uit
