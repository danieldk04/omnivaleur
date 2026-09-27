"""Verzendkosten op 2dehands: per verkoper, per artikel, en ook voor wat al online staat.

WAAROM (27-09-2026, Egbert Brouwer / Papa's Plectrums; Daniel). Tot vandaag kon
een verkoper bij Preferences alleen een regel zetten (briefgrens en titelwoorden),
en die gold alleen voor nieuwe zoekertjes. Wat al op 2dehands stond veranderde pas
als wij met de hand scripts/verzendkosten_2dehands_bijwerken.py draaiden, en een
uitzondering (een bandana die toch een brief is) kon alleen via een nieuw
titelwoord. Daniel: "ervoor zorgen dat ik niet constant iedereen individueel zit
te berichten". Daarom drie dingen die de verkoper zelf doet:

1. Een keuze per verkoper (VERZENDING_2DH_MODUS in instellingen.py): altijd
   Bpost, het Marktplaats-bedrag voor brieven, of het Marktplaats-bedrag voor alles.
2. Een eigen keuze per artikel (EIGEN hieronder): Bpost of een vast bedrag, gezet
   vanuit de voorraad met "2dehands shipping…". Gaat voor de regel en heeft
   Marktplaats niet nodig, dus werkt ook voor wat daar niet staat (Vinted-import).
3. Een ronde op de server die zoekertjes die al online staan bijwerkt (RONDE).

WAT NIET KAN: een zoekertje dat al online staat met een eigen bedrag terugzetten
naar Bpost. De extensie (vanaf 1.0.354) zet op het wijzigformulier alleen "Zelf
versturen" met een bedrag (verzendingBijwerken in tweedehands.js). Bpost geldt dan
voor nieuwe zoekertjes; het scherm zegt dat erbij.

Alles staat in platform_credentials, net als de instellingen zelf: een nieuwe
kolom of tabel vraagt handwerk in Supabase, en tot dat gebeurt werkt niets (zie de
kop van instellingen.py).
"""
from __future__ import annotations

import logging

from backend.database import fetch_all, get_db

logger = logging.getLogger(__name__)

STANDAARD = {"soort": "standaard"}

# ── de eigen keuze per artikel ────────────────────────────────────────────────
# Eén rij per verkoper: {"artikelen": {item_id: centen | "bpost"}}. Geen sleutel =
# het artikel volgt de keuze bij Preferences.
RIJ_EIGEN = "_verzending_2dh_artikelen"
BPOST = "bpost"
VOLG = "volg"
EIGEN_MAX_CENTEN = 9999        # EUR 99,99; daarboven is het een tikfout
EIGEN_MAX_ARTIKELEN = 20000
# Voor de ronde (verzending_2dh_ronde.py): hooguit eens per minuut deze rij lezen.
_EIGEN_CACHE: dict[str, tuple[float, dict]] = {}


def _schone_keuze(waarde):
    if waarde == BPOST:
        return BPOST
    if isinstance(waarde, bool) or not isinstance(waarde, int):
        return None
    return waarde if 0 <= waarde <= EIGEN_MAX_CENTEN else None


def eigen_keuzes(user_id: str, db=None) -> dict | None:
    """{item_id: centen | "bpost"} van deze verkoper. None = niet te lezen: een
    storing is geen antwoord, dus dan legt de aanroeper niets vast."""
    try:
        rij = ((db or get_db()).table("platform_credentials").select("extra_data")
               .eq("user_id", user_id).eq("platform", RIJ_EIGEN).limit(1).execute().data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("eigen verzendkeuzes niet gelezen voor %s: %s", user_id, e)
        return None
    rauw = ((rij[0].get("extra_data") or {}) if rij else {}).get("artikelen")
    if not isinstance(rauw, dict):
        return {}
    uit = {}
    for sleutel, waarde in rauw.items():
        schoon = _schone_keuze(waarde)
        if schoon is not None:
            uit[str(sleutel)] = schoon
    return uit


def keuze_uit_invoer(keuze):
    """Wat het scherm stuurt ("volg", "bpost" of centen) als opslagwaarde.
    None = volgen (sleutel weg). ValueError bij iets anders."""
    if keuze == VOLG:
        return None
    if keuze == BPOST:
        return BPOST
    try:
        centen = int(keuze)
    except (TypeError, ValueError):
        raise ValueError("unknown choice") from None
    if isinstance(keuze, bool) or not 0 <= centen <= EIGEN_MAX_CENTEN:
        raise ValueError("amount out of range")
    return centen


def zet_eigen_keuze(user_id: str, item_ids, keuze, db=None) -> dict:
    """De keuze voor deze artikelen opslaan. Alleen artikelen van deze verkoper:
    de lijst komt van buiten. Geeft {"gezet": n, "ids": [...]} terug."""
    waarde = keuze_uit_invoer(keuze)
    db = db or get_db()
    gevraagd = list(dict.fromkeys(str(i) for i in (item_ids or []) if i))
    eigen = {r["id"] for r in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", user_id))}
    ids = [i for i in gevraagd if i in eigen]
    huidig = eigen_keuzes(user_id, db)
    if huidig is None:
        raise RuntimeError("could not read the current choices")
    for i in ids:
        if waarde is None:
            huidig.pop(i, None)
        else:
            huidig[i] = waarde
    if len(huidig) > EIGEN_MAX_ARTIKELEN:
        raise ValueError("too many items with their own shipping choice")
    db.table("platform_credentials").upsert(
        {"user_id": user_id, "platform": RIJ_EIGEN, "extra_data": {"artikelen": huidig}},
        on_conflict="user_id,platform").execute()
    _EIGEN_CACHE.pop(user_id, None)
    return {"gezet": len(ids), "ids": ids}


def doel(regel: dict, eigen, titel: str, mp) -> dict | None:
    """Wat het zoekertje op 2dehands hoort te tonen.

    eigen  de keuze voor dit artikel: centen, BPOST, of None (volgt de regel)
    mp     wat Marktplaats toont, in de vorm van verzending_uit_html; {} = staat
           niet (meer) op Marktplaats; None = niet te lezen
    Terug: {"soort": "zelf", "cents": n}, STANDAARD (Bpost), of None als het
    zonder Marktplaats niet te zeggen is. Een storing wordt nooit Bpost.
    """
    from backend.services.instellingen import heeft_marktplaats_nodig, neemt_bedrag_over
    if eigen == BPOST:
        return dict(STANDAARD)
    if isinstance(eigen, int) and not isinstance(eigen, bool):
        return {"soort": "zelf", "cents": eigen}
    if not heeft_marktplaats_nodig(regel, titel):
        return dict(STANDAARD)
    if mp is None:
        return None
    if mp.get("soort") == "zelf" and neemt_bedrag_over(regel, titel, mp.get("cents")):
        return {"soort": "zelf", "cents": mp["cents"]}
    return dict(STANDAARD)
