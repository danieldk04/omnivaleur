"""Nieuwe WooCommerce-producten vanzelf in Omnivaleur, elk uur.

Dezelfde regels als de Shopify-versie (services/shopify_auto_import.py, Janneke
08-10-2026), want daar is uitgezocht wat er mis kan gaan:
  1. Alleen bij verkopers voor wie de winkel de bron is: ze importeerden zelf
     ooit uit WooCommerce, of zetten het bewust aan. Wie alleen NAAR WooCommerce
     publiceert krijgt niets, anders wordt elk product dat niet op nummer te
     koppelen is een tweede artikel.
  2. Alleen producten die Omnivaleur nog nooit zag, en eens per dag de
     achterstand: kandidaten die bij een eerdere scan bleven liggen ('pending')
     en nog te koop staan. 'Ignored' is een keuze van de verkoper en blijft.
  3. Dezelfde opslag en dezelfde importbeslissing als de knop; twijfel blijft
     onder "To check" staan.
  4. Producten van minder dan een kwartier oud wachten een ronde, zodat een
     product dat Omnivaleur net zelf in de winkel zette nooit terugkomt als nieuw.

Anders dan bij Shopify: elk uur leest deze ronde alleen wat er sinds de vorige
keer in de winkel veranderde (modified_after). Mikkis heeft 2.504 producten en
verbrak de verbinding bij snel bladeren; elk uur alles lezen is 26 pagina's die
de winkel niet nodig heeft. De dagelijkse achterstandsronde leest wel alles.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import fetch_all, fetch_all_in, get_db, naast_de_lus
from backend.platforms.woocommerce import PLATFORM, WooFout, client_uit
from backend.services import shopify_auto_import as sai

logger = logging.getLogger(__name__)

INSTELLING = "woocommerce_auto_import"
STAND = "woocommerce_auto_import_stand"
OVERLAP = timedelta(minutes=15)


def is_bron(db, user_id: str) -> bool:
    rij = (db.table("import_candidates").select("id")
           .eq("user_id", user_id).eq("platform", PLATFORM).eq("status", "imported")
           .limit(1).execute().data or [])
    return bool(rij)


def staat_aan(db, user_id: str, inst: dict) -> bool:
    keuze = inst.get(INSTELLING)
    if keuze is True or keuze is False:
        return keuze
    try:
        return is_bron(db, user_id)
    except Exception as e:  # noqa: BLE001 — bij twijfel niets importeren
        logger.warning("woocommerce-auto-import: bron niet te bepalen voor %s: %s", user_id, e)
        return False


def _bekende_productnummers(db, user_id: str) -> set[str]:
    bekend = {str(r["platform_listing_id"]) for r in fetch_all(
        lambda: db.table("import_candidates").select("platform_listing_id")
        .eq("user_id", user_id).eq("platform", PLATFORM))
        if r.get("platform_listing_id")}
    item_ids = [r["id"] for r in fetch_all(lambda: db.table("items").select("id").eq("user_id", user_id))]
    if item_ids:
        for r in fetch_all_in(lambda: db.table("listings").select("platform,platform_listing_id"),
                              "item_id", item_ids):
            if r.get("platform") == PLATFORM and r.get("platform_listing_id"):
                bekend.add(str(r["platform_listing_id"]))
    return bekend


def _oud_genoeg(product: dict, nu: datetime) -> bool:
    ts = product.get("date_created_gmt")
    if not ts:
        return True
    return sai._oud_genoeg({"created_at": ts + ("" if ts.endswith("Z") else "Z")}, nu)


def nieuwe_producten(producten: list[dict], bekend: set[str], nu: datetime) -> list[dict]:
    from backend.services.woocommerce_scan import uitverkocht
    return [p for p in producten
            if p.get("id") is not None and str(p["id"]) not in bekend
            and not uitverkocht(p) and _oud_genoeg(p, nu)]


def _achterstand(db, user_id: str, producten: list[dict]) -> list[str]:
    from backend.services.woocommerce_scan import uitverkocht
    te_koop = {str(p["id"]) for p in producten if p.get("id") is not None and not uitverkocht(p)}
    return [c["id"] for c in fetch_all(
        lambda: db.table("import_candidates").select("id,platform_listing_id,status")
        .eq("user_id", user_id).eq("platform", PLATFORM).eq("status", "pending"))
        if str(c.get("platform_listing_id")) in te_koop]


def _scan_loopt(db, user_id: str) -> bool:
    import time
    from backend.api.imports import _BULK_IMPORT_CACHE

    entry = _BULK_IMPORT_CACHE.get(user_id)
    if entry and time.monotonic() - entry.get("ts", 0) < sai.HANDMATIG_RUST_S:
        return True
    return bool(db.table("jobs").select("id").eq("user_id", user_id).eq("platform", PLATFORM)
                .eq("action", "scan").in_("status", ["pending", "claimed"]).limit(1).execute().data)


def _bewaar_stand(user_id: str, **velden) -> None:
    from backend.services import instellingen
    try:
        vorige = instellingen.lees(user_id).get(STAND) or {}
        instellingen.schrijf(user_id, {STAND: {**vorige, **velden}})
    except Exception as e:  # noqa: BLE001 — de stand is een melding, geen voorwaarde
        logger.warning("woocommerce-auto-import: stand niet bewaard voor %s: %s", user_id, e)


def _sinds(stand: dict) -> str | None:
    """Vanaf wanneer de winkel gelezen moet worden, als WooCommerce-tijd (UTC, zonder zone)."""
    vorige = stand.get("gecontroleerd")
    if not vorige:
        return None
    try:
        t = datetime.fromisoformat(str(vorige).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (t - OVERLAP).astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


async def importeer_nieuwe_producten(user_id: str) -> dict:
    from backend.api.imports import _BULK_IMPORT_CACHE, bulk_import_candidates
    from backend.api.jobs import _store_scan_results
    from backend.services import instellingen
    from backend.services.woocommerce_scan import (bewaar_modus, markeer_als_voorraadwinkel,
                                                   naar_scanregel)

    db = get_db()
    inst = await naast_de_lus(lambda: instellingen.lees(user_id))
    if not await naast_de_lus(lambda: staat_aan(db, user_id, inst)):
        return {"overgeslagen": "uit"}
    if await naast_de_lus(lambda: _scan_loopt(db, user_id)):
        return {"overgeslagen": "scan of import loopt"}
    if not await sai._mag_importeren(user_id):
        return {"overgeslagen": "geen toegang"}
    rij = ((await naast_de_lus(lambda: db.table("platform_credentials")
                               .select("user_id,access_token,refresh_token,extra_data")
                               .eq("user_id", user_id).eq("platform", PLATFORM)
                               .limit(1).execute())).data or [])
    client = client_uit(rij[0]) if rij else None
    if not client:
        return {"overgeslagen": "niet gekoppeld"}
    from backend.services.woocommerce_browser import bereikbaar
    if not bereikbaar(rij[0]):
        # Alleen via de browser van de klant, en die is dicht: volgend uur weer.
        return {"overgeslagen": "wacht op browser"}

    nu = datetime.now(timezone.utc)
    stand = inst.get(STAND) or {}
    achterstand_nu = sai._achterstand_aan_de_beurt(stand, nu)
    try:
        producten = await client.producten(None if achterstand_nu else _sinds(stand))
    except WooFout as e:
        await naast_de_lus(lambda: _bewaar_stand(user_id, gecontroleerd=stand.get("gecontroleerd"),
                                                 fout=str(e)))
        return {"overgeslagen": f"winkel niet gelezen: {e.soort}"}
    finally:
        await bewaar_modus(db, user_id, client)

    bekend = await naast_de_lus(lambda: _bekende_productnummers(db, user_id))
    nieuw = nieuwe_producten(producten, bekend, nu)
    achterstand_ids = (await naast_de_lus(lambda: _achterstand(db, user_id, producten))
                       if achterstand_nu else [])
    if not nieuw and not achterstand_ids:
        velden = {"gecontroleerd": nu.isoformat(), "fout": None}
        if achterstand_nu:
            velden["achterstand_om"] = nu.isoformat()
        await naast_de_lus(lambda: _bewaar_stand(user_id, **velden))
        return {"nieuw": 0}

    try:
        await markeer_als_voorraadwinkel(db, user_id, producten)
    except Exception:  # noqa: BLE001
        logger.exception("woocommerce-auto-import: voorraadvlag niet gezet voor %s", user_id)

    ids: list[str] = []
    if nieuw:
        regels = [naar_scanregel(p) for p in nieuw]
        job = {"id": None, "user_id": user_id, "platform": PLATFORM}
        await naast_de_lus(lambda: _store_scan_results(db, job, regels))
        pids = [r["platform_listing_id"] for r in regels]
        kandidaten = await naast_de_lus(lambda: fetch_all_in(
            lambda: db.table("import_candidates").select("id,status")
            .eq("user_id", user_id).eq("platform", PLATFORM), "platform_listing_id", pids))
        ids = [c["id"] for c in kandidaten if c.get("status") == "pending"]
    ids += [i for i in achterstand_ids if i not in ids]

    _BULK_IMPORT_CACHE.pop(user_id, None)
    toegevoegd = gekoppeld = mislukt = te_controleren = 0
    try:
        for start in range(0, len(ids), sai.GROEP):
            groep = ids[start:start + sai.GROEP]
            offset = 0
            for _ in range(sai.MAX_RONDES):
                uit = await bulk_import_candidates(
                    {"platform": PLATFORM, "candidate_ids": groep, "limit": 25, "offset": offset},
                    user_id=user_id)
                toegevoegd += uit.get("created", 0)
                gekoppeld += uit.get("linked", 0)
                mislukt += uit.get("failed", 0)
                te_controleren += uit.get("parked", 0)
                offset = uit.get("next_offset", offset)
                if uit.get("remaining", 0) <= offset:
                    break
                if not (uit.get("created", 0) + uit.get("linked", 0) + uit.get("failed", 0)
                        + uit.get("parked", 0) + uit.get("light_parked", 0)):
                    break
    finally:
        _BULK_IMPORT_CACHE.pop(user_id, None)

    nieuwe_stand = {"gecontroleerd": nu.isoformat(), "fout": None,
                    "laatst_nieuw": toegevoegd + gekoppeld, "te_controleren": te_controleren}
    if achterstand_nu:
        nieuwe_stand["achterstand_om"] = nu.isoformat()
    if toegevoegd or gekoppeld:
        nieuwe_stand["laatst_toegevoegd_om"] = nu.isoformat()
        nieuwe_stand["totaal_toegevoegd"] = int(stand.get("totaal_toegevoegd") or 0) + toegevoegd
    await naast_de_lus(lambda: _bewaar_stand(user_id, **nieuwe_stand))
    logger.info("woocommerce-auto-import %s: %d nieuw, %d toegevoegd, %d gekoppeld, "
                "%d te controleren, %d mislukt", user_id, len(nieuw), toegevoegd, gekoppeld,
                te_controleren, mislukt)
    return {"nieuw": len(nieuw), "achterstand": len(achterstand_ids), "toegevoegd": toegevoegd,
            "gekoppeld": gekoppeld, "te_controleren": te_controleren, "mislukt": mislukt}


async def importeer_alle_winkels() -> dict:
    db = get_db()
    rijen = ((await naast_de_lus(lambda: db.table("platform_credentials")
             .select("user_id").eq("platform", PLATFORM).execute())).data or [])
    totaal = {"winkels": len(rijen), "toegevoegd": 0, "gekoppeld": 0}
    for rij in rijen:
        try:
            uit = await importeer_nieuwe_producten(rij["user_id"])
            totaal["toegevoegd"] += uit.get("toegevoegd", 0)
            totaal["gekoppeld"] += uit.get("gekoppeld", 0)
        except Exception:  # noqa: BLE001 — één winkel mag de rest niet blokkeren
            logger.exception("woocommerce-auto-import mislukt voor %s", rij["user_id"])
    return totaal
