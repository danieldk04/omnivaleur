"""
Persoonlijke instellingen per verkoper.

WAAROM HIER EN NIET IN EEN EIGEN TABEL
Een nieuwe tabel betekent dat Daniel eerst met de hand SQL moet draaien in
Supabase, en tot dat moment werkt de functie voor niemand. Dat is hier al vaker
gebeurd en dan blijft een afgebouwde knop weken dood liggen. `platform_credentials`
bestaat al, staat per gebruiker en heeft een vrij JSON-veld. Er wordt daarom één
rij per verkoper gebruikt met platform `_settings`; geen enkele platformcode kijkt
naar die naam, dus hij komt nergens anders bovendrijven.

Alles wat hier binnenkomt wordt begrensd. Een instelling die de verkoper zelf zet
mag nooit tot een waarde leiden die zijn account in gevaar brengt.
"""
from __future__ import annotations

import logging

from backend.database import get_db

logger = logging.getLogger(__name__)

RIJ = "_settings"

# Hoe vaak een advertentie opnieuw geplaatst mag worden.
#
# Ondergrens 7: vaker dan een keer per week is op Marktplaats geen onderhoud meer
# maar een patroon. Bovengrens 85: Marktplaats gooit een advertentie na 90 dagen
# zelf weg, dus daarboven zou de instelling stilzwijgend niets meer doen.
RELIST_DAGEN_STANDAARD = 27
RELIST_DAGEN_MIN = 7
RELIST_DAGEN_MAX = 85

STANDAARD = {"relist_dagen": RELIST_DAGEN_STANDAARD}


def _schoon(rauw: dict | None) -> dict:
    uit = dict(STANDAARD)
    if not isinstance(rauw, dict):
        return uit
    try:
        dagen = int(rauw.get("relist_dagen", RELIST_DAGEN_STANDAARD))
    except (TypeError, ValueError):
        dagen = RELIST_DAGEN_STANDAARD
    uit["relist_dagen"] = max(RELIST_DAGEN_MIN, min(dagen, RELIST_DAGEN_MAX))
    return uit


def lees(user_id: str) -> dict:
    """De instellingen van één verkoper, altijd compleet en altijd binnen bereik."""
    try:
        rij = (get_db().table("platform_credentials").select("extra_data")
               .eq("user_id", user_id).eq("platform", RIJ).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001 — een instelling mag nooit een pagina slopen
        logger.warning("instellingen niet gelezen voor %s: %s", user_id, e)
        return dict(STANDAARD)
    return _schoon(rij[0].get("extra_data") if rij else None)


def schrijf(user_id: str, wijziging: dict) -> dict:
    """Instellingen bijwerken. Geeft terug wat er daadwerkelijk is opgeslagen,
    zodat het scherm de begrensde waarde toont en niet wat er is ingetikt."""
    nieuw = _schoon({**lees(user_id), **(wijziging or {})})
    db = get_db()
    db.table("platform_credentials").upsert(
        {"user_id": user_id, "platform": RIJ, "extra_data": nieuw},
        on_conflict="user_id,platform",
    ).execute()
    return nieuw


def alle_relist_dagen() -> dict[str, int]:
    """Per verkoper het ingestelde aantal dagen, voor de dagelijkse ronde.

    Eén aanroep in plaats van een aanroep per advertentie: die ronde loopt over
    duizenden regels en mag de database niet duizend keer bevragen.
    """
    uit: dict[str, int] = {}
    try:
        for rij in (get_db().table("platform_credentials").select("user_id,extra_data")
                    .eq("platform", RIJ).limit(5000).execute().data or []):
            uit[rij["user_id"]] = _schoon(rij.get("extra_data"))["relist_dagen"]
    except Exception as e:  # noqa: BLE001
        logger.warning("instellingen niet gelezen: %s", e)
    return uit
