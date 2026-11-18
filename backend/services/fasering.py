"""Fasering voor de drie grote accounts (besluit Daniel 09-11-2026).

Wie boven 3.000 actieve artikelen zit gaat niet in een keer van 19,99 naar 49, maar
in stappen: 1 januari tot 31 maart 29,99, 1 april tot 30 juni 39, daarna 49. Alles
excl. btw, zoals de Pro- en Ultra-prijzen in Stripe.

HOE
Het abonnement krijgt een Stripe-schema met vier fasen. Alle fasen na 1 januari
gebruiken de ULTRA-prijs, met een korting per fase die het verschil met 49 dekt
(19,01 en 10,00). Daardoor is het plan van deze klant in elke fase Ultra
(onbeperkt, geen blokkade op artikelen) terwijl hij minder betaalt, en weet de
rest van de code (plan uit de prijs) niets van de fasering. Na de laatste fase
laat het schema los en loopt het abonnement gewoon door op Ultra voor 49.

Er wordt nooit voor een tussentijdse prijswijziging verrekend (proration none):
de nieuwe prijs gaat in op de eerstvolgende factuur na de fasegrens.

Dit bestand maakt niets zelf aan zonder dat een script het vraagt. Het zet dus
nooit iets in Stripe als er alleen `fasen_voor` wordt aangeroepen.
"""
from __future__ import annotations

from datetime import datetime, timezone

ULTRA_CENTS = 4900

LOS_OP = datetime(2027, 8, 1, tzinfo=timezone.utc)

# (vanaf, maandprijs in centen excl. btw). De laatste stap is de gewone Ultra-prijs.
STAPPEN = (
    (datetime(2027, 1, 1, tzinfo=timezone.utc), 2999),
    (datetime(2027, 4, 1, tzinfo=timezone.utc), 3900),
    (datetime(2027, 7, 1, tzinfo=timezone.utc), ULTRA_CENTS),
)


def korting_cents(maandprijs_cents: int) -> int:
    """Wat er van de Ultra-prijs af moet om op deze maandprijs uit te komen."""
    return max(0, ULTRA_CENTS - int(maandprijs_cents))


def coupon_id(korting: int) -> str:
    """Vaste id per kortingsbedrag, zodat een tweede keer draaien dezelfde coupon pakt."""
    return f"fasering_ultra_{korting}"


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def fasen_voor(huidige_fase: dict, ultra_prijs_id: str,
               nu: datetime | None = None) -> list[dict]:
    """De fasen voor Stripe, gegeven de lopende fase van het schema.

    huidige_fase: de eerste fase van het schema dat Stripe uit het abonnement maakte
        (dict met o.a. start_date, items, automatic_tax). Die blijft tot 1 januari
        ongewijzigd lopen.
    """
    nu = nu or datetime.now(timezone.utc)
    eerste_stap = STAPPEN[0][0]
    if nu >= eerste_stap:
        raise ValueError("De eerste stap (1 januari 2027) is al voorbij; dit moet met de hand.")

    gedeeld = {}
    if huidige_fase.get("automatic_tax"):
        gedeeld["automatic_tax"] = {"enabled": bool(huidige_fase["automatic_tax"].get("enabled"))}
    if huidige_fase.get("default_tax_rates"):
        gedeeld["default_tax_rates"] = list(huidige_fase["default_tax_rates"])

    nul = {
        "start_date": huidige_fase["start_date"],
        "end_date": _ts(eerste_stap),
        "items": [{"price": i["price"] if isinstance(i["price"], str) else i["price"]["id"],
                   "quantity": i.get("quantity", 1)} for i in huidige_fase["items"]],
        "proration_behavior": "none",
        **gedeeld,
    }
    fasen = [nul]
    for n, (_vanaf, prijs) in enumerate(STAPPEN):
        fase = {
            "items": [{"price": ultra_prijs_id, "quantity": 1}],
            "proration_behavior": "none",
            **gedeeld,
        }
        k = korting_cents(prijs)
        if k:
            fase["discounts"] = [{"coupon": coupon_id(k)}]
        if n + 1 < len(STAPPEN):
            fase["end_date"] = _ts(STAPPEN[n + 1][0])
        else:
            # Een maand na de laatste stap laat het schema los en loopt het
            # abonnement gewoon door op Ultra voor 49. Een einddatum en geen
            # "iterations": die parameter bestaat niet in elke API-versie.
            fase["end_date"] = _ts(LOS_OP)
        fasen.append(fase)
    return fasen


def benodigde_kortingen() -> list[int]:
    return sorted({korting_cents(p) for _, p in STAPPEN if korting_cents(p)})
