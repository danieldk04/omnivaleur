"""De vier plannen en hun grenzen (besluit Daniel 09-11-2026, live 01-01-2027).

Een plan telt ACTIEVE artikelen per factuur, niet advertenties. Nieuwe artikelen mogen
tot 10% boven de grens (marge), daarboven worden alleen NIEUWE artikelen geweigerd. Wat al
online staat blijft altijd gewoon werken.

Alles hier staat uit totdat `nieuwe_plannen_aan` aan gaat. Zolang dat uit staat gedraagt
de server zich precies als voor deze wijziging: alleen Light heeft een grens (20).
"""
from __future__ import annotations

from backend.config import settings

PLAN_LIGHT, PLAN_PRO, PLAN_PLUS, PLAN_ULTRA = "light", "pro", "plus", "ultra"

# Grens in actieve artikelen. None = onbeperkt.
GRENZEN = {PLAN_LIGHT: 20, PLAN_PRO: 250, PLAN_PLUS: 1500, PLAN_ULTRA: None}
MARGE = 0.10                 # Light blijft strikt 20, zoals het nu live staat
MET_MARGE = {PLAN_PRO, PLAN_PLUS}
UITSTEL_DAGEN = 14           # (nog niet gebouwd: vraagt een plek om de overschrijding te onthouden)

# Prijs-id (maand of jaar) naar plan. Leeg = bestaat nog niet in Stripe.
_PRIJS_VELDEN = (
    ("stripe_price_id_light", PLAN_LIGHT), ("stripe_price_id_light_jaar", PLAN_LIGHT),
    ("stripe_price_id", PLAN_PRO), ("stripe_price_id_pro_jaar", PLAN_PRO),
    ("stripe_price_id_plus", PLAN_PLUS), ("stripe_price_id_plus_jaar", PLAN_PLUS),
    ("stripe_price_id_ultra", PLAN_ULTRA), ("stripe_price_id_ultra_jaar", PLAN_ULTRA),
)


def plan_uit_prijs_id(prijs_id: str | None) -> str:
    """Het plan bij een Stripe-prijs. Onbekend of leeg is 'pro': liever geen
    onterechte beperking dan een klant die we ten onrechte beperken."""
    pid = (prijs_id or "").strip()
    if pid:
        for veld, plan in _PRIJS_VELDEN:
            if pid == (getattr(settings, veld, "") or "").strip():
                return plan
    return PLAN_PRO


def grens(plan: str | None) -> int | None:
    """Hoeveel actieve artikelen dit plan mag hebben voor een NIEUW artikel
    geweigerd wordt. None = geen grens.

    Staat de schakelaar uit, dan geldt alleen de oude regel: Light 20, de rest vrij.
    """
    plan = (plan or PLAN_PRO).lower()
    if not settings.nieuwe_plannen_aan:
        return GRENZEN[PLAN_LIGHT] if plan == PLAN_LIGHT else None
    basis = GRENZEN.get(plan)
    if basis is None:
        return None
    return int(basis * (1 + MARGE)) if plan in MET_MARGE else basis
