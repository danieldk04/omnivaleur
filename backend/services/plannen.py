"""De vier plannen en hun grenzen (besluit Daniel 09-11-2026, live 01-01-2027).

Een plan telt ACTIEVE artikelen per factuur, niet advertenties. Nieuwe artikelen mogen
tot 10% boven de grens (marge), daarboven worden alleen NIEUWE artikelen geweigerd. Wat al
online staat blijft altijd gewoon werken.

Alles hier staat uit totdat `nieuwe_plannen_aan` aan gaat. Zolang dat uit staat gedraagt
de server zich precies als voor deze wijziging: alleen Light heeft een grens (20).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.config import settings

PLAN_LIGHT, PLAN_PRO, PLAN_PLUS, PLAN_ULTRA = "light", "pro", "plus", "ultra"

# Grens in actieve artikelen. None = onbeperkt.
GRENZEN = {PLAN_LIGHT: 20, PLAN_PRO: 250, PLAN_PLUS: 1500, PLAN_ULTRA: None}
MARGE = 0.10                 # Light blijft strikt 20, zoals het nu live staat
MET_MARGE = {PLAN_PRO, PLAN_PLUS}
# Invoeringsuitstel: de grenzen van Pro en Plus gaan pas gelden UITSTEL_DAGEN na de start
# van de nieuwe plannen. Wie dan boven zijn grens zit heeft zo twee weken om te kiezen. Dit is
# bewust vast voor iedereen en niet per klant: per klant onthouden vraagt een kolom of een
# schrijfactie vanuit de poll, en de limiet-poort draait bij elke opdracht. Daniel kan dit later
# per klant maken als hij dat wil. Light blijft strikt 20 (staat nu al zo live).
START_NIEUWE_PLANNEN = datetime(2027, 1, 1, tzinfo=timezone.utc)
UITSTEL_DAGEN = 14
GRENZEN_VANAF = START_NIEUWE_PLANNEN + timedelta(days=UITSTEL_DAGEN)

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


def grens(plan: str | None, nu: datetime | None = None) -> int | None:
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
    if plan != PLAN_LIGHT and (nu or datetime.now(timezone.utc)) < GRENZEN_VANAF:
        return None          # invoeringsuitstel: nog niemand geweigerd
    return int(basis * (1 + MARGE)) if plan in MET_MARGE else basis


_MAAND_VELD = {PLAN_LIGHT: "stripe_price_id_light", PLAN_PRO: "stripe_price_id",
               PLAN_PLUS: "stripe_price_id_plus", PLAN_ULTRA: "stripe_price_id_ultra"}
_JAAR_VELD = {PLAN_LIGHT: "stripe_price_id_light_jaar", PLAN_PRO: "stripe_price_id_pro_jaar",
              PLAN_PLUS: "stripe_price_id_plus_jaar", PLAN_ULTRA: "stripe_price_id_ultra_jaar"}


def keuze_beschikbaar(plan: str, jaar: bool = False) -> str | None:
    """Het Stripe-prijsnummer voor deze keuze, of None als die (nog) niet te koop is.

    Plus, Ultra en elk jaarplan zijn pas te koop als de schakelaar aan staat EN het
    prijsnummer ingesteld is. Light en Pro per maand blijven zoals ze waren.
    """
    if plan not in _MAAND_VELD:
        return None
    nieuw = jaar or plan in (PLAN_PLUS, PLAN_ULTRA)
    if nieuw and not settings.nieuwe_plannen_aan:
        return None
    veld = (_JAAR_VELD if jaar else _MAAND_VELD)[plan]
    return (getattr(settings, veld, "") or "").strip() or None


_RANG = {PLAN_LIGHT: 0, PLAN_PRO: 1, PLAN_PLUS: 2, PLAN_ULTRA: 3}


def plan_en_jaar(prijs_id: str | None) -> tuple[str, bool]:
    """(plan, is_jaar) bij een Stripe-prijs. Onbekend is ('pro', False)."""
    pid = (prijs_id or "").strip()
    if pid:
        for plan, veld in _JAAR_VELD.items():
            if pid == (getattr(settings, veld, "") or "").strip():
                return plan, True
    return plan_uit_prijs_id(pid), False


def wissel_toegestaan(huidig: tuple[str, bool], doel: tuple[str, bool]) -> bool:
    """Alleen omhoog, of van maand naar jaar binnen hetzelfde plan. Omlaag, terug
    naar maand of een gelijke keuze gaan via het klantportaal."""
    (p0, j0), (p1, j1) = huidig, doel
    if (p0, j0) == (p1, j1) or p0 not in _RANG or p1 not in _RANG:
        return False
    if _RANG[p1] > _RANG[p0]:
        return not (j0 and not j1)      # van jaar naar maand omhoog is een portaalzaak
    return _RANG[p1] == _RANG[p0] and j1 and not j0
