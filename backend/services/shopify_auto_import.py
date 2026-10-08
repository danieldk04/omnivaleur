"""Nieuwe Shopify-producten vanzelf in Omnivaleur, zonder op Import te drukken.

WAAROM (08-10-2026, Janneke 31d28378, Daniel: "bouw die automatische
Shopify-import maar meteen")
Janneke vroeg "en nieuwe producten worden vanzelf gesynchroniseerd?". Dat
werden ze niet. De dagelijkse ronde in shopify_reconcile.py koppelt alleen
artikelen die al in Omnivaleur staan aan hun product; een product dat ze nieuw
in haar winkel zet bleef onzichtbaar tot ze zelf weer Scannen en Alles
importeren deed. Wie zijn voorraad in Shopify bijhoudt verwacht dat de rest
vanzelf volgt.

WAT DEZE RONDE DOET (elk uur)
  1. Alleen bij verkopers voor wie Shopify de bron is: ze hebben zelf ooit
     producten uit Shopify geïmporteerd, of zetten het bewust aan. Wie Shopify
     alleen gebruikt om NAAR te publiceren (Revaleur) krijgt niets: daar zou
     elk product dat niet op nummer te koppelen is een tweede artikel worden.
  2. Alleen producten die Omnivaleur nog nooit zag: niet als importkandidaat,
     niet als eigen advertentie. Wat de verkoper eerder liet liggen of negeerde
     blijft van hem; dit pakt alleen wat sinds de vorige keer is bijgekomen.
  3. Precies dezelfde opslag en dezelfde importbeslissing als de knop
     (jobs._store_scan_results en imports.bulk_import_candidates). Wat daar
     twijfel is, blijft hier ook staan onder "To check".
  4. Producten van minder dan een kwartier oud wachten een ronde. Een product
     dat Omnivaleur zelf net naar Shopify publiceerde heeft zijn productnummer
     soms nog niet in de advertentierij; zo wordt het nooit een tweede artikel.

Wat er gebeurde staat in de instellingen van de verkoper (STAND), zodat het
importscherm kan zeggen wanneer er voor het laatst is gekeken en wat erbij kwam.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from backend.database import fetch_all, fetch_all_in, get_db, naast_de_lus

logger = logging.getLogger(__name__)

INSTELLING = "shopify_auto_import"        # True / False / None (= vanzelf bepaald)
STAND = "shopify_auto_import_stand"

MIN_LEEFTIJD = timedelta(minutes=15)
# Een import met de knop die net nog liep: niet tegelijk ernaast gaan werken.
HANDMATIG_RUST_S = 300
GROEP = 400                               # kandidaat-id's per importronde
MAX_RONDES = 40                           # ruim genoeg voor een groep van 400 per 25


def is_bron(db, user_id: str) -> bool:
    """Heeft deze verkoper ooit zelf producten uit Shopify geïmporteerd?"""
    rij = (db.table("import_candidates").select("id")
           .eq("user_id", user_id).eq("platform", "shopify").eq("status", "imported")
           .limit(1).execute().data or [])
    return bool(rij)


def staat_aan(db, user_id: str, inst: dict) -> bool:
    """De bewuste keuze van de verkoper, anders: aan zodra Shopify zijn bron is."""
    keuze = inst.get(INSTELLING)
    if keuze is True or keuze is False:
        return keuze
    try:
        return is_bron(db, user_id)
    except Exception as e:  # noqa: BLE001 — bij twijfel niets importeren
        logger.warning("shopify-auto-import: bron niet te bepalen voor %s: %s", user_id, e)
        return False


def _bekende_productnummers(db, user_id: str) -> set[str]:
    """Elk productnummer dat al als kandidaat of als eigen advertentie bestaat."""
    bekend = {str(r["platform_listing_id"]) for r in fetch_all(
        lambda: db.table("import_candidates").select("platform_listing_id")
        .eq("user_id", user_id).eq("platform", "shopify"))
        if r.get("platform_listing_id")}
    item_ids = [r["id"] for r in fetch_all(
        lambda: db.table("items").select("id").eq("user_id", user_id))]
    if item_ids:
        for r in fetch_all_in(lambda: db.table("listings").select("platform,platform_listing_id"),
                              "item_id", item_ids):
            if r.get("platform") == "shopify" and r.get("platform_listing_id"):
                bekend.add(str(r["platform_listing_id"]))
    return bekend


def _oud_genoeg(product: dict, nu: datetime) -> bool:
    ts = product.get("created_at")
    if not ts:
        return True
    try:
        gemaakt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return True
    if gemaakt.tzinfo is None:
        gemaakt = gemaakt.replace(tzinfo=timezone.utc)
    return nu - gemaakt >= MIN_LEEFTIJD


def nieuwe_producten(producten: list[dict], bekend: set[str], nu: datetime) -> list[dict]:
    """Wat er sinds de vorige keer in de winkel is bijgekomen en te koop staat."""
    from backend.services.shopify_scan import uitverkocht

    return [p for p in producten
            if p.get("id") is not None
            and str(p["id"]) not in bekend
            and not uitverkocht(p)
            and _oud_genoeg(p, nu)]


def _scan_loopt(db, user_id: str) -> bool:
    """Loopt er een scan of een import met de knop? Dan deze ronde overslaan."""
    from backend.api.imports import _BULK_IMPORT_CACHE

    entry = _BULK_IMPORT_CACHE.get(user_id)
    if entry and time.monotonic() - entry.get("ts", 0) < HANDMATIG_RUST_S:
        return True
    open_ = (db.table("jobs").select("id")
             .eq("user_id", user_id).eq("platform", "shopify").eq("action", "scan")
             .in_("status", ["pending", "claimed"]).limit(1).execute().data or [])
    return bool(open_)


async def _mag_importeren(user_id: str) -> bool:
    """Proef verlopen of betaling mislukt: dan maakt de ronde niets aan."""
    from backend.database import get_admin_db
    from backend.services.billing import check_access

    email = None
    try:
        gebruiker = await naast_de_lus(lambda: get_admin_db().auth.admin.get_user_by_id(user_id))
        email = getattr(getattr(gebruiker, "user", None), "email", None)
    except Exception as e:  # noqa: BLE001 — zonder adres beslist het abonnement zelf
        logger.info("shopify-auto-import: geen adres voor %s: %s", user_id, e)
    return bool((await check_access(user_id, email)).get("allowed"))


def _bewaar_stand(user_id: str, **velden) -> None:
    from backend.services import instellingen

    try:
        vorige = instellingen.lees(user_id).get(STAND) or {}
        instellingen.schrijf(user_id, {STAND: {**vorige, **velden}})
    except Exception as e:  # noqa: BLE001 — de stand is een melding, geen voorwaarde
        logger.warning("shopify-auto-import: stand niet bewaard voor %s: %s", user_id, e)


async def importeer_nieuwe_producten(user_id: str) -> dict:
    """Eén winkel: nieuwe producten opslaan als kandidaat en meteen importeren."""
    from backend.api.imports import _BULK_IMPORT_CACHE, bulk_import_candidates
    from backend.api.jobs import _store_scan_results
    from backend.platforms.shopify import _shop_creds
    from backend.services import instellingen
    from backend.services.shopify_scan import (lees_producten, naar_scanregel,
                                               winkelnaam_als_merk)

    db = get_db()
    inst = await naast_de_lus(lambda: instellingen.lees(user_id))
    if not await naast_de_lus(lambda: staat_aan(db, user_id, inst)):
        return {"overgeslagen": "uit"}
    if await naast_de_lus(lambda: _scan_loopt(db, user_id)):
        return {"overgeslagen": "scan of import loopt"}
    if not await _mag_importeren(user_id):
        return {"overgeslagen": "geen toegang"}

    rij = ((await naast_de_lus(lambda: db.table("platform_credentials")
                               .select("user_id,access_token,extra_data")
                               .eq("user_id", user_id).eq("platform", "shopify")
                               .limit(1).execute())).data or [])
    if not rij:
        return {"overgeslagen": "niet gekoppeld"}
    nu = datetime.now(timezone.utc)
    try:
        shop, token = await _shop_creds({**rij[0], "user_id": user_id})
        if not (shop and token):
            raise PermissionError("geen sleutel")
        producten = await lees_producten(shop, token)
    except PermissionError:
        await naast_de_lus(lambda: _bewaar_stand(
            user_id, gecontroleerd=nu.isoformat(),
            fout="Shopify refused access. Reconnect your store under Platforms."))
        return {"overgeslagen": "geen toegang tot Shopify"}
    except Exception as e:  # noqa: BLE001 — volgende uur gewoon opnieuw
        logger.warning("shopify-auto-import: winkel niet gelezen voor %s: %s", user_id, e)
        return {"overgeslagen": f"winkel niet gelezen: {type(e).__name__}"}

    bekend = await naast_de_lus(lambda: _bekende_productnummers(db, user_id))
    nieuw = nieuwe_producten(producten, bekend, nu)
    if not nieuw:
        await naast_de_lus(lambda: _bewaar_stand(user_id, gecontroleerd=nu.isoformat(), fout=None))
        return {"nieuw": 0}

    # Dezelfde voorraadvlag als de scan met de knop zet: zonder die vlag haalt
    # de eerste verkoop elders een product met voorraad uit de winkel.
    try:
        from backend.services.shopify_voorraad import markeer_als_voorraadwinkel
        await markeer_als_voorraadwinkel(db, user_id, producten)
    except Exception:  # noqa: BLE001
        logger.exception("shopify-auto-import: voorraadvlag niet gezet voor %s", user_id)

    winkelnaam = winkelnaam_als_merk(producten)
    regels = [naar_scanregel(p, shop, winkelnaam) for p in nieuw]
    job = {"id": None, "user_id": user_id, "platform": "shopify"}
    await naast_de_lus(lambda: _store_scan_results(db, job, regels))

    pids = [r["platform_listing_id"] for r in regels]
    kandidaten = await naast_de_lus(lambda: fetch_all_in(
        lambda: db.table("import_candidates").select("id,status")
        .eq("user_id", user_id).eq("platform", "shopify"),
        "platform_listing_id", pids))
    ids = [c["id"] for c in kandidaten if c.get("status") == "pending"]

    # De importbeslissing van de knop, beperkt tot precies deze kandidaten. Een
    # verse lezing van de voorraad: een cache van een eerdere sessie kent de
    # artikelen van het afgelopen uur niet.
    _BULK_IMPORT_CACHE.pop(user_id, None)
    toegevoegd = gekoppeld = mislukt = 0
    te_controleren = 0
    try:
        # In groepjes: de lijst gaat als filter in de URL mee (zie IN_BROK).
        for start in range(0, len(ids), GROEP):
            groep = ids[start:start + GROEP]
            offset = 0
            for _ in range(MAX_RONDES):
                uit = await bulk_import_candidates(
                    {"platform": "shopify", "candidate_ids": groep, "limit": 25, "offset": offset},
                    user_id=user_id)
                toegevoegd += uit.get("created", 0)
                gekoppeld += uit.get("linked", 0)
                mislukt += uit.get("failed", 0)
                te_controleren += uit.get("parked", 0)
                offset = uit.get("next_offset", offset)
                # Wat nog wacht staat allemaal vóór de offset (twijfel, Light
                # vol): dan is de rest gedaan.
                if uit.get("remaining", 0) <= offset:
                    break
                verwerkt = (uit.get("created", 0) + uit.get("linked", 0) + uit.get("failed", 0)
                            + uit.get("parked", 0) + uit.get("light_parked", 0))
                if not verwerkt:
                    break   # niets bewoog: nooit blijven rondjes draaien
    finally:
        _BULK_IMPORT_CACHE.pop(user_id, None)

    vorige = (inst.get(STAND) or {})
    stand = {"gecontroleerd": nu.isoformat(), "fout": None,
             "laatst_nieuw": toegevoegd + gekoppeld,
             "te_controleren": te_controleren}
    if toegevoegd or gekoppeld:
        stand["laatst_toegevoegd_om"] = nu.isoformat()
        stand["totaal_toegevoegd"] = int(vorige.get("totaal_toegevoegd") or 0) + toegevoegd
    await naast_de_lus(lambda: _bewaar_stand(user_id, **stand))
    logger.info("shopify-auto-import %s: %d nieuw in de winkel, %d toegevoegd, %d gekoppeld, "
                "%d te controleren, %d mislukt", user_id, len(nieuw), toegevoegd, gekoppeld,
                te_controleren, mislukt)
    return {"nieuw": len(nieuw), "toegevoegd": toegevoegd, "gekoppeld": gekoppeld,
            "te_controleren": te_controleren, "mislukt": mislukt}


async def importeer_alle_winkels() -> dict:
    """Elke gekoppelde Shopify-winkel een ronde. Draait elk uur (scheduler.py)."""
    db = get_db()
    rijen = ((await naast_de_lus(lambda: db.table("platform_credentials")
             .select("user_id").eq("platform", "shopify").execute())).data or [])
    totaal = {"winkels": len(rijen), "toegevoegd": 0, "gekoppeld": 0}
    for rij in rijen:
        try:
            uit = await importeer_nieuwe_producten(rij["user_id"])
            totaal["toegevoegd"] += uit.get("toegevoegd", 0)
            totaal["gekoppeld"] += uit.get("gekoppeld", 0)
        except Exception:  # noqa: BLE001 — één winkel mag de rest niet blokkeren
            logger.exception("shopify-auto-import mislukt voor %s", rij["user_id"])
    if totaal["toegevoegd"] or totaal["gekoppeld"]:
        logger.info("shopify-auto-import: %(toegevoegd)d toegevoegd, %(gekoppeld)d gekoppeld "
                    "over %(winkels)d winkel(s)", totaal)
    return totaal
