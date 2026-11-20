"""Routes van het AI-pakket (20-11-2026). Alles hangt aan settings.ai_pakket_aan.

Staat de vlag uit (standaard), dan antwoordt elke route 404 en gebeurt er niets:
geen model-aanroep, geen schrijfactie. Zo is het pakket onzichtbaar tot Daniel
het aanzet.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user
from backend.config import settings
from backend.database import get_db, fetch_all, execute_with_retry, IN_BROK
from backend.services import ai_bulk, ai_quota

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-pakket", tags=["ai-pakket"])

_LEES = "id,title,description,price," + ",".join(ai_bulk.PRIJSVELD.values())


def _aan() -> None:
    if not settings.ai_pakket_aan:
        raise HTTPException(status_code=404, detail="Not found")


def _lees_items(user_id: str) -> list[dict]:
    db = get_db()
    return fetch_all(lambda: db.table("items").select(_LEES).eq("user_id", user_id))


@router.get("/status")
def status(user_id: str = Depends(get_current_user)):
    _aan()
    return {"aan": True, "plafond": ai_quota.PLAFOND,
            "gebruikt": {k: ai_quota.gebruikt(user_id, k) for k in ai_quota.PLAFOND},
            "ongedaan_mogelijk": bool(ai_quota.lees_los(user_id, "laatste"))}


@router.post("/bulk/voorbeeld")
async def bulk_voorbeeld(body: dict, user_id: str = Depends(get_current_user)):
    _aan()
    opdracht = str((body or {}).get("opdracht") or "").strip()
    if not opdracht or len(opdracht) > 400:
        raise HTTPException(status_code=400, detail="Describe the change in one short sentence")
    if not ai_quota.ruimte(user_id, "bulk"):
        raise HTTPException(status_code=429, detail="Monthly limit of AI bulk edits reached")
    ai_quota.tel(user_id, "bulk")
    bew, reden = await asyncio.to_thread(ai_bulk.vraag_model, opdracht)
    if bew is None:
        if reden == "storing":
            raise HTTPException(status_code=503, detail="The AI is not available right now. Nothing was changed.")
        return {"begrepen": False, "reden": reden,
                "hint": "Say it with one change, for example: raise all prices by 10%"}
    items = await asyncio.to_thread(_lees_items, user_id)
    v = ai_bulk.voorbeeld(items, bew)
    if v["te_veel"]:
        return {"begrepen": True, "uitvoerbaar": False, "reden": "te_veel",
                "bewerking": bew, **v}
    if v["wijzigingen"] == 0:
        return {"begrepen": True, "uitvoerbaar": False, "reden": "niets_te_doen",
                "bewerking": bew, **v}
    vid = uuid.uuid4().hex[:12]
    ai_quota.bewaar(user_id, "voorbeeld", {"id": vid, "tijd": time.time(), "bewerking": bew})
    return {"begrepen": True, "uitvoerbaar": True, "voorbeeld_id": vid, "bewerking": bew, **v}


def _schrijf(db, user_id: str, wijzigingen: list[dict], nieuw: bool) -> list[str]:
    """Zet per artikel de velden. Geeft de id's die echt veranderden."""
    per_item: dict[str, dict] = {}
    for x in wijzigingen:
        per_item.setdefault(x["id"], {})[x["veld"]] = x["nieuw"] if nieuw else x["oud"]
    gedaan = []
    for iid, velden in per_item.items():
        rij = execute_with_retry(db.table("items").update(velden)
                                 .eq("id", iid).eq("user_id", user_id))
        if getattr(rij, "data", None):
            gedaan.append(iid)
    return gedaan


async def _prijzen_doorgeven(user_id: str, ids: list[str]) -> None:
    from backend.services.crosslist import sync_price_to_platforms
    for iid in ids:
        try:
            await sync_price_to_platforms(iid, user_id)
        except Exception:  # noqa: BLE001 - een kanaal dat weigert mag de rest niet stoppen
            logger.exception("AI-bulk: prijs doorgeven mislukt voor %s", iid)


@router.post("/bulk/uitvoeren")
async def bulk_uitvoeren(body: dict, user_id: str = Depends(get_current_user)):
    _aan()
    body = body or {}
    plan_op = ai_quota.lees_los(user_id, "voorbeeld")
    if (not isinstance(plan_op, dict) or plan_op.get("id") != body.get("voorbeeld_id")
            or time.time() - float(plan_op.get("tijd") or 0) > ai_bulk.VOORBEELD_GELDIG_S):
        raise HTTPException(status_code=409, detail="This preview has expired. Ask again.")
    if body.get("bevestig") is not True:
        raise HTTPException(status_code=400, detail="Confirmation is required")
    bew = ai_bulk.valideer(__import__("json").dumps(plan_op["bewerking"]))
    if bew is None:
        raise HTTPException(status_code=409, detail="This preview is no longer valid. Ask again.")
    items = await asyncio.to_thread(_lees_items, user_id)
    p = ai_bulk.plan(items, bew)
    if (p["onder_1"] or p["dubbel"]) and body.get("bevestig_extra") is not True:
        raise HTTPException(status_code=409, detail="Extra confirmation is required: some prices drop below 1 euro or more than double")
    w = p["wijzigingen"]
    if not w or len({x["id"] for x in w}) > ai_bulk.MAX_ARTIKELEN:
        raise HTTPException(status_code=409, detail="Nothing to change or too many items")
    blok = ai_bulk.ongedaan_blok(w)
    if blok is None:
        raise HTTPException(status_code=413, detail="Too much to undo safely. Select fewer items.")
    # EERST de oude waarden bewaren, dan pas schrijven: faalt het schrijven halverwege,
    # dan kan ongedaan maken het nog herstellen.
    ai_quota.bewaar(user_id, "laatste", blok)
    ai_quota.bewaar(user_id, "voorbeeld", None)
    db = get_db()
    gedaan = await asyncio.to_thread(_schrijf, db, user_id, w, True)
    prijs_ids = [i for i in gedaan if any(x["id"] == i and x["veld"].startswith("price") for x in w)]
    if prijs_ids:
        asyncio.create_task(_prijzen_doorgeven(user_id, prijs_ids))
    return {"gewijzigd": len(gedaan), "ongedaan_id": blok["id"]}


@router.post("/bulk/ongedaan")
async def bulk_ongedaan(body: dict, user_id: str = Depends(get_current_user)):
    _aan()
    blok = ai_quota.lees_los(user_id, "laatste")
    if not isinstance(blok, dict) or blok.get("id") != (body or {}).get("ongedaan_id"):
        raise HTTPException(status_code=404, detail="Nothing to undo")
    ids = list(blok["items"])
    db = get_db()

    def _doe() -> tuple[int, int]:
        huidig = {}
        for i in range(0, len(ids), IN_BROK):
            for r in fetch_all(lambda s=ids[i:i + IN_BROK]: db.table("items").select(_LEES)
                               .eq("user_id", user_id).in_("id", s)):
                huidig[r["id"]] = r
        terug, overgeslagen = [], 0
        for iid, velden in blok["items"].items():
            for veld, (oud, nieuw) in velden.items():
                nu = (huidig.get(iid) or {}).get(veld)
                # Alleen terugzetten wat nog is zoals wij het zetten; een latere
                # handmatige wijziging van de klant blijft staan.
                if iid in huidig and _gelijk(nu, nieuw):
                    terug.append({"id": iid, "veld": veld, "oud": oud, "nieuw": oud})
                else:
                    overgeslagen += 1
        return len(_schrijf(db, user_id, terug, True)), overgeslagen

    n, over = await asyncio.to_thread(_doe)
    ai_quota.bewaar(user_id, "laatste", None)
    prijs_ids = [i for i, v in blok["items"].items() if any(k.startswith("price") for k in v)]
    if prijs_ids:
        asyncio.create_task(_prijzen_doorgeven(user_id, prijs_ids))
    return {"teruggezet": n, "overgeslagen": over}


def _gelijk(a, b) -> bool:
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return (a or "") == (b or "")
