"""Het klassement, de niveaus en de Founding Circle van de uitnodigactie.

Besluit Daniel 09-11-2026 (zie docs/team-notes.md):
- Maandelijks klassement, vrijwillig, met een zelfgekozen gebruikersnaam.
- Een vriend telt voor het klassement pas als hij 30 dagen betaalt en dan nog
  betaalt. Alleen Pro of hoger telt (zelfde regel als de korting).
- Drempel voor de prijs: 3 nieuwe betalende vrienden in de maand. Haalt niemand
  de drempel, dan rolt de prijs door. De prijs deelt Daniel zelf uit (een
  feature naar keuze, in overleg), hier staat alleen de ranglijst.
- Niveaus op het aantal betalende vrienden: Brons 1, Zilver 3, Goud 5, Platina 10.
- Founding Circle: de eerste 10 klanten die 5 betalende vrienden hebben.

Dit bestand rekent alleen. Het haalt niets op en schrijft niets: wie het aanroept
levert de rijen. Zo is elke regel hier met een paar rijen te bewijzen.

Founding Circle wordt bij elke aanroep opnieuw uitgerekend uit wie op dit moment
5 betalende vrienden heeft, gerangschikt op de datum waarop de vijfde vriend voor
het eerst betaalde. Valt iemand terug onder 5, dan schuift de volgende op. Dat
past bij "ontgrendeling geldt zolang zij blijven betalen"; een blijvend lidmaatschap
zou een eigen opslag nodig hebben.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.services.referral_korting import telt_mee

DREMPEL_PRIJS = 3          # nieuwe betalende vrienden in een maand voor de prijs
DAGEN_BETAALD = 30         # zo lang moet een vriend betaald hebben om mee te tellen
FOUNDING_PLEKKEN = 10
FOUNDING_VRIENDEN = 5
BORD_LENGTE = 10

# Hoogste eerst: de eerste die past is het niveau.
NIVEAUS = (("platinum", 10), ("gold", 5), ("silver", 3), ("bronze", 1))


def _tijd(waarde) -> datetime | None:
    if not waarde:
        return None
    if isinstance(waarde, datetime):
        dt = waarde
    else:
        try:
            dt = datetime.fromisoformat(str(waarde).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def niveau(aantal_betalende_vrienden: int) -> str | None:
    """bronze, silver, gold, platinum of None."""
    n = max(0, int(aantal_betalende_vrienden))
    for naam, vanaf in NIVEAUS:
        if n >= vanaf:
            return naam
    return None


def volgend_niveau(aantal_betalende_vrienden: int) -> tuple[str, int] | None:
    """(niveau, nog_te_gaan) of None als het hoogste niveau al is bereikt."""
    n = max(0, int(aantal_betalende_vrienden))
    for naam, vanaf in reversed(NIVEAUS):
        if n < vanaf:
            return (naam, vanaf - n)
    return None


def maand_van(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def bereken(verwijzingen: list[dict], code_eigenaar: dict[str, str],
            abos: dict[str, dict], namen: dict[str, str | None],
            nu: datetime | None = None) -> dict:
    """Alles in een keer.

    verwijzingen: rijen {user_id, code, first_paid_at}
    code_eigenaar: {code: user_id van de klant die de code bezit}; codes van
                   creators staan er niet in en tellen dus nooit mee
    abos: {user_id van de vriend: {status, plan, stripe_subscription_id}}
    namen: {user_id van de klant: gekozen klassementsnaam of None}
    """
    nu = nu or datetime.now(timezone.utc)
    maand = maand_van(nu)
    # per aanbrenger: lijst van (eerste betaling, mijlpaal van 30 dagen)
    betalend: dict[str, list[datetime]] = {}
    for v in verwijzingen:
        eigenaar = code_eigenaar.get(v.get("code"))
        if not eigenaar or eigenaar == v.get("user_id"):
            continue
        abo = abos.get(v.get("user_id")) or {}
        if abo.get("status") not in ("active", "payment_processing"):
            continue
        if not abo.get("stripe_subscription_id") or not telt_mee(abo.get("plan")):
            continue
        eerste = _tijd(v.get("first_paid_at"))
        if eerste is None:
            continue
        betalend.setdefault(eigenaar, []).append(eerste)

    per_gebruiker: dict[str, dict] = {}
    bord_regels = []
    founding_kandidaten = []
    for eigenaar, momenten in betalend.items():
        momenten.sort()
        n = len(momenten)
        # Een vriend die 30 dagen betaalt en nu nog betaalt, telt mee in de maand
        # waarin die 30 dagen vol werden.
        mijlpalen = sorted(m + timedelta(days=DAGEN_BETAALD) for m in momenten)
        rijp = [m for m in mijlpalen if m <= nu]
        deze_maand = [m for m in rijp if maand_van(m) == maand]
        per_gebruiker[eigenaar] = {
            "telt": n,
            "maand_telt": len(deze_maand),
            "niveau": niveau(n),
            "volgend": volgend_niveau(n),
            "founding": False,
        }
        if deze_maand:
            # Wie de stand eerder haalde staat bij gelijke stand hoger.
            bord_regels.append((eigenaar, len(deze_maand), deze_maand[-1]))
        if n >= FOUNDING_VRIENDEN:
            founding_kandidaten.append((momenten[FOUNDING_VRIENDEN - 1], eigenaar))

    founding_kandidaten.sort()
    for _, eigenaar in founding_kandidaten[:FOUNDING_PLEKKEN]:
        per_gebruiker[eigenaar]["founding"] = True

    # Alleen wie een naam koos staat op het bord. Zonder naam blijft iemand
    # onzichtbaar, ook voor de ranglijst zelf.
    bord_regels.sort(key=lambda r: (-r[1], r[2]))
    bord = []
    for eigenaar, aantal, _ in bord_regels:
        naam = namen.get(eigenaar)
        if not naam:
            continue
        bord.append({"user_id": eigenaar, "name": naam, "count": aantal,
                     "qualifies": aantal >= DREMPEL_PRIJS})
    for plek, regel in enumerate(bord, start=1):
        regel["rank"] = plek

    return {
        "month": maand,
        "threshold": DREMPEL_PRIJS,
        "board": bord,
        "per_user": per_gebruiker,
        "founding_taken": sum(1 for p in per_gebruiker.values() if p["founding"]),
        "founding_spots": FOUNDING_PLEKKEN,
    }


def voor_gebruiker(uitkomst: dict, user_id: str, eigen_naam: str | None) -> dict:
    """Wat het dashboard van één klant laat zien. Het bord bevat nooit user_id's."""
    ik = uitkomst["per_user"].get(user_id) or {
        "telt": 0, "maand_telt": 0, "niveau": None,
        "volgend": volgend_niveau(0), "founding": False,
    }
    volgend = ik["volgend"]
    mijn_plek = next((r["rank"] for r in uitkomst["board"] if r["user_id"] == user_id), None)
    return {
        "month": uitkomst["month"],
        "threshold": uitkomst["threshold"],
        "board": [{"rank": r["rank"], "name": r["name"], "count": r["count"],
                   "qualifies": r["qualifies"], "me": r["user_id"] == user_id}
                  for r in uitkomst["board"][:BORD_LENGTE]],
        "me": {
            "joined": bool(eigen_naam),
            "name": eigen_naam,
            "rank": mijn_plek,
            "month_count": ik["maand_telt"],
            "friends": ik["telt"],
            "level": ik["niveau"],
            "next_level": {"level": volgend[0], "to_go": volgend[1]} if volgend else None,
            "founding": ik["founding"],
        },
        "levels": [{"level": n, "from": v} for n, v in reversed(NIVEAUS)],
        "founding": {"taken": uitkomst["founding_taken"], "spots": uitkomst["founding_spots"],
                     "friends_needed": FOUNDING_VRIENDEN},
    }
