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

# Welke categoriegroepen deze verkoper op Vinted wil hebben. Leeg = alles wat
# Vinted zelf toestaat. Dit is een VOORKEUR, geen platformregel: Jaap
# Zilverwebsite wil er alleen sieraden op, maar zijn buurman mag daar prima
# elektronica verkopen. Die twee dingen moeten uit elkaar blijven, anders staat
# de voorkeur van de een als verbod in de weg bij de ander.
VINTED_GROEPEN_GELDIG = ("dames", "heren", "kinderen", "unisex", "sieraden",
                         "antiek", "kunst", "muziek", "games", "electronics")

# De EU verplicht sinds de GPSR bij vrijwel elke advertentie een
# "verantwoordelijke partij": naam, postadres en e-mailadres van de fabrikant of
# van de EU-gemachtigde. Marktplaats markeert die drie velden inmiddels als
# verplicht, en zonder ingevulde waarde weigert het formulier te plaatsen.
#
# Dit hoort NIET geraden te worden. Hier stond ooit Revaleur als vaste waarde,
# waardoor elke klant publiceerde met andermans bedrijfsnaam als aansprakelijke
# partij — juridisch onjuist en niet iets waar een verkoper om heeft gevraagd.
# De verkoper vult het één keer zelf in en het gaat daarna overal mee.
FABRIKANT_VELDEN = ("fabrikant_naam", "fabrikant_adres", "fabrikant_email")

STANDAARD = {"relist_dagen": RELIST_DAGEN_STANDAARD, "vinted_groepen": [],
             "auto_relist": True,
             "fabrikant_naam": "", "fabrikant_adres": "", "fabrikant_email": ""}


def _schoon(rauw: dict | None) -> dict:
    uit = dict(STANDAARD)
    if not isinstance(rauw, dict):
        return uit
    try:
        dagen = int(rauw.get("relist_dagen", RELIST_DAGEN_STANDAARD))
    except (TypeError, ValueError):
        dagen = RELIST_DAGEN_STANDAARD
    uit["relist_dagen"] = max(RELIST_DAGEN_MIN, min(dagen, RELIST_DAGEN_MAX))
    # Alleen groepen die echt bestaan. Een typefout of een verzonnen naam zou
    # anders stilzwijgend álles blokkeren — de instelling zou dan precies het
    # tegenovergestelde doen van wat er staat.
    # Automatisch herplaatsen kan uit. Niet iedereen wil dat zijn advertenties
    # buiten hem om verdwijnen en terugkomen: "hij begint ineens random dingen te
    # listen op marktplaats" is een terechte klacht als je die knop niet hebt.
    if "auto_relist" in rauw:
        uit["auto_relist"] = bool(rauw.get("auto_relist"))
    # Marktplaats kapt deze velden zelf af op 255 tekens; langer opslaan zou
    # betekenen dat het scherm iets anders toont dan wat er geplaatst wordt.
    for veld in FABRIKANT_VELDEN:
        if veld in rauw:
            uit[veld] = str(rauw.get(veld) or "").strip()[:255]
    groepen = rauw.get("vinted_groepen")
    if isinstance(groepen, list):
        uit["vinted_groepen"] = [g for g in
                                 dict.fromkeys(str(x).strip().lower() for x in groepen)
                                 if g in VINTED_GROEPEN_GELDIG]
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


def fabrikant(user_id: str) -> dict:
    """De verantwoordelijke partij van deze verkoper, of een leeg blok.

    Apart van `lees` omdat de publicatiekant hier maar drie velden van nodig
    heeft en die één op één de namen van het Marktplaats-formulier volgen."""
    s = lees(user_id)
    return {
        "manufacturer_name": s.get("fabrikant_naam") or "",
        "manufacturer_address": s.get("fabrikant_adres") or "",
        "manufacturer_email": s.get("fabrikant_email") or "",
    }


def fabrikant_compleet(user_id: str) -> bool:
    return all(fabrikant(user_id).values())
