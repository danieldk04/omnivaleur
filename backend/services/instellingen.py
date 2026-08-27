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

from backend.database import get_db, fetch_all

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
# LET OP: deze lijst moet gelijk blijven aan GROEPEN in platformregels.py en aan
# VINTED_GROEPEN in frontend/app.html. Loopt hij achter, dan ontstaat het ergste
# soort fout: het dashboard zegt dat een artikel op Vinted mag en de server
# blokkeert het alsnog, met een reden die naar een instelling wijst die de
# verkoper nooit heeft kunnen aanvinken. Precies dat gebeurde met "wonen" (sinds
# augustus 2026) en zou met "audio" ook zijn gebeurd; beide op 27-08-2026
# toegevoegd. test_vinted_voorkeur bewaakt het nu.
VINTED_GROEPEN_GELDIG = ("dames", "heren", "kinderen", "unisex", "sieraden",
                         "antiek", "kunst", "muziek", "games", "electronics",
                         "wonen", "audio")

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

# Hoe deze verkoper levert. Stond alleen in de extensie-instellingen, waar
# vrijwel niemand komt: Jaap verzendt uitsluitend, en kreeg bij elke advertentie
# "Ophalen of Verzenden" — een belofte die hij niet kan waarmaken. Hoort bij het
# account, dus hier, en gaat mee in elke opdracht.
LEVERING_GELDIG = ("beide", "verzenden", "ophalen")

# Pakketgrootte op prijs. Marktplaats kent XS (brievenbuspakje), S, M en L
# (groot pakket). Onder de grens het kleine, daarboven het grote; 0 = laat
# Marktplaats het zelf bepalen. Bewust een grens in euro's en geen slimmigheid
# met afmetingen: de verkoper weet zelf welke waarde hij niet in een
# brievenbuspakje wil hebben, wij kunnen dat niet zien aan een foto.
PAKKET_GRENS_MAX = 5000

STANDAARD = {"relist_dagen": RELIST_DAGEN_STANDAARD, "vinted_groepen": [],
             "auto_relist": True,
             "fabrikant_naam": "", "fabrikant_adres": "", "fabrikant_email": "",
             "levering": "beide", "pakket_grens": 0}


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
    lev = str(rauw.get("levering") or "").strip().lower()
    if lev in LEVERING_GELDIG:
        uit["levering"] = lev
    if "pakket_grens" in rauw:
        try:
            uit["pakket_grens"] = max(0, min(int(float(rauw.get("pakket_grens") or 0)),
                                             PAKKET_GRENS_MAX))
        except (TypeError, ValueError):
            uit["pakket_grens"] = 0
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
        # fetch_all: een gewone select stopt stilzwijgend bij 1.000 rijen, en dan
        # draaien de verkopers daarboven op de standaardinstelling in plaats van
        # de hunne.
        for rij in fetch_all(lambda: get_db().table("platform_credentials")
                             .select("user_id,extra_data").eq("platform", RIJ)):
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


# De radiowaarden zoals Marktplaats ze zelf op het formulier zet, live afgelezen
# op 21-08-2026: XS = Brievenbuspakje (0-2kg), S = Klein (0-3kg),
# M = Gemiddeld (0-10kg), L = Groot pakket (10-23kg).
PAKKET_KLEIN = "XS"
PAKKET_GROOT = "L"


def verzendkeuzes(user_id: str, prijs) -> dict:
    """Levering en pakketgrootte voor één advertentie.

    De pakketgrootte hangt van de prijs af: onder de door de verkoper ingestelde
    grens past het in een brievenbuspakje, daarboven wil hij het als groot pakket
    verzekerd versturen. Staat de grens op 0, dan bemoeien we ons er niet mee."""
    s = lees(user_id)
    uit = {"levering": s.get("levering") or "beide"}
    grens = int(s.get("pakket_grens") or 0)
    if grens:
        try:
            uit["pakket"] = PAKKET_KLEIN if float(prijs or 0) < grens else PAKKET_GROOT
        except (TypeError, ValueError):
            pass
    return uit
