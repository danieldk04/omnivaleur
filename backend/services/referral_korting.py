"""Korting per betalende vriend: alleen de rekenregels, zonder Stripe en zonder database.

Besloten door Daniel op 09-11-2026. Dit bestand bevat bewust geen
netwerkaanroepen, zodat elke regel met een test te bewijzen is voor er geld mee
beweegt. De ronde die het echt toekent staat apart (en volgt pas na een proef in
Stripe-testmodus).

De regels die je niet moet omdraaien:

  * Een vriend telt pas mee na een echte betaling, nooit bij aanmelding.
  * Alleen vanaf Pro. Een Light-vriend betaalt 9,99; 10 euro korting zou meer
    kosten dan hij oplevert.
  * De korting is nooit meer dan 50% van wat de vriend betaalde. Wie een
    tweede account op eigen kaart neemt, betaalt dus altijd meer dan hij
    terugkrijgt.
  * De korting is nooit meer dan de eigen rekening en wordt nooit contant
    uitgekeerd: er hoopt zich geen tegoed op boven één maandprijs.
  * Tot 01-01-2027 geldt 10 euro per vriend per betaalde maand, daarna 5 euro.
    Een vriend die vóór 01-01-2027 voor het eerst betaalde, houdt 10 euro
    zolang hij blijft betalen.
"""
from __future__ import annotations

from datetime import datetime, timezone

EINDE_ACTIE = datetime(2027, 1, 1, tzinfo=timezone.utc)
BEDRAG_ACTIE_CENTS = 1000
BEDRAG_NORMAAL_CENTS = 500
MIN_BEDRAG_CENTS = 100         # onder een euro boekt het niets (geen centen-ruis)
AANDEEL_NOOIT_MEER_DAN = 0.5   # van wat de vriend (incl. btw) betaalde
PLANNEN_DIE_TELLEN = {"pro", "plus", "ultra"}   # niet "light"

# De trap: aantal betalende vrienden dat een trede ontsluit.
TREDEN = (1, 3, 5)


def telt_mee(plan: str | None) -> bool:
    """Alleen een betalende vriend op Pro of hoger telt. Onbekend plan telt niet:
    liever een vriend te weinig dan korting die we niet kunnen verantwoorden."""
    return (plan or "").strip().lower() in PLANNEN_DIE_TELLEN


def bedrag_per_vriend_cents(eerste_betaling_op: datetime | None) -> int:
    """10 euro voor wie vóór de einddatum voor het eerst betaalde, anders 5.
    Zonder bekende datum geldt het lage bedrag (liever te weinig dan te veel)."""
    if eerste_betaling_op is None:
        return BEDRAG_NORMAAL_CENTS
    if eerste_betaling_op.tzinfo is None:
        eerste_betaling_op = eerste_betaling_op.replace(tzinfo=timezone.utc)
    return BEDRAG_ACTIE_CENTS if eerste_betaling_op < EINDE_ACTIE else BEDRAG_NORMAAL_CENTS


def korting_cents(
    *,
    vriend_plan: str | None,
    vriend_betaald_cents: int,
    vriend_eerste_betaling_op: datetime | None,
    eigen_maandprijs_cents: int,
    huidig_tegoed_cents: int,
) -> int:
    """Wat de aanbrenger krijgt voor één betaalde factuur van één vriend.

    vriend_betaald_cents: wat de vriend voor deze factuur betaalde INCLUSIEF btw,
        na eventuele teruggave. Bewust het bruto bedrag: het tegoed van de
        aanbrenger is ook bruto en verlaagt zijn btw mee, dus 50% bruto is voor ons
        precies 50% netto (Pro: 19,99 geeft 9,99 korting, kost ons 8,26 netto).
    huidig_tegoed_cents: wat de aanbrenger nu al aan niet-verbruikt tegoed
        heeft (positief getal).
    """
    if not telt_mee(vriend_plan) or vriend_betaald_cents <= 0:
        return 0
    bedrag = bedrag_per_vriend_cents(vriend_eerste_betaling_op)
    bedrag = min(bedrag, int(vriend_betaald_cents * AANDEEL_NOOIT_MEER_DAN))
    ruimte = max(0, int(eigen_maandprijs_cents) - max(0, int(huidig_tegoed_cents)))
    uitkomst = max(0, min(bedrag, ruimte))
    return uitkomst if uitkomst >= MIN_BEDRAG_CENTS else 0


def trede(aantal_betalende_vrienden: int) -> int:
    """De hoogste trede die dit aantal ontsluit: 0, 1, 3 of 5."""
    n = max(0, int(aantal_betalende_vrienden))
    hoogste = 0
    for t in TREDEN:
        if n >= t:
            hoogste = t
    return hoogste


def volgende_trede(aantal_betalende_vrienden: int) -> tuple[int, int] | None:
    """(trede, nog_te_gaan) voor de voortgangsbalk, of None als alles ontsloten is."""
    n = max(0, int(aantal_betalende_vrienden))
    for t in TREDEN:
        if n < t:
            return (t, t - n)
    return None
