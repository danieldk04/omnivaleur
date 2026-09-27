"""Verzendkosten op 2dehands: de ronde over bestaande zoekertjes en de eigen keuze
per artikel. Het waarom staat in backend/services/verzending_2dh.py.

Bewust niet onder /items: daar vangt /items/{item_id} alles wat erachter komt.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user, require_active_subscription
from backend.database import fetch_all, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verzending-2dh", tags=["verzending"])


@router.get("")
def lees(user_id: str = Depends(get_current_user)):
    """De lopende of laatste ronde, en of zijn extensie het werk kan doen."""
    from backend.services.verzending_2dh_ronde import extensie_kan_bijwerken, openbaar, stand
    return {"ronde": openbaar(stand(user_id)),
            "extensie_kan_bijwerken": extensie_kan_bijwerken(user_id)}


@router.post("/ronde")
def start_ronde(body: dict | None = None, user_id: str = Depends(require_active_subscription)):
    """Zijn zoekertjes op 2dehands bijwerken naar zijn keuze bij Preferences.
    Met {"opnieuw": true} alleen wat de vorige ronde niet kon lezen."""
    from backend.services.verzending_2dh_ronde import openbaar, start
    try:
        st = start(user_id, opnieuw_niet_gelezen=bool((body or {}).get("opnieuw")))
    except Exception as e:  # noqa: BLE001
        logger.exception("verzendronde niet te starten voor %s", user_id)
        raise HTTPException(status_code=503, detail=f"Could not start: {e}")
    return {"ronde": openbaar(st)}


@router.get("/artikelen")
def lees_artikelen(user_id: str = Depends(get_current_user)):
    """{item_id: centen | "bpost"} voor artikelen met een eigen keuze."""
    from backend.services.verzending_2dh import eigen_keuzes
    eigen = eigen_keuzes(user_id)
    if eigen is None:
        raise HTTPException(status_code=503, detail="Could not read your shipping choices, try again.")
    return {"artikelen": eigen}


def _op_2dehands(user_id: str, ids: list[str]) -> list[str]:
    """Welke van deze artikelen nu een zoekertje op 2dehands hebben. Eén
    gekoppelde vraag over zijn hele voorraad, geen brokken van 200 (kennisbank
    gekoppelde-vraag-ipv-brokken)."""
    db = get_db()
    online = {str(r["item_id"]) for r in fetch_all(
        lambda: db.table("listings").select("id,item_id,items!inner(user_id)")
        .eq("items.user_id", user_id).eq("platform", "2dehands").eq("status", "active")
        .not_.is_("platform_listing_id", "null"))}
    return [i for i in ids if i in online]


@router.post("/artikelen")
def zet_artikelen(body: dict, user_id: str = Depends(require_active_subscription)):
    """Een eigen verzendkeuze voor deze artikelen: {"item_ids": [...], "keuze":
    "volg" | "bpost" | centen}. Staat er al een zoekertje op 2dehands en is de
    keuze een bedrag of "volg", dan werkt de ronde het bij."""
    from backend.services.verzending_2dh import BPOST, zet_eigen_keuze
    from backend.services.verzending_2dh_ronde import openbaar, start
    ids, keuze = (body or {}).get("item_ids"), (body or {}).get("keuze")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="Select at least one item.")
    try:
        uit = zet_eigen_keuze(user_id, ids, keuze)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("eigen verzendkeuze niet opgeslagen voor %s", user_id)
        raise HTTPException(status_code=503, detail=f"Could not save: {e}")
    online = _op_2dehands(user_id, uit["ids"])
    ronde = None
    if online and keuze != BPOST:
        try:
            ronde = openbaar(start(user_id, item_ids=online))
        except Exception as e:  # noqa: BLE001 — de keuze staat, nieuwe zoekertjes krijgen hem
            logger.warning("verzendronde voor eigen keuze niet gestart (%s): %s", user_id, e)
    return {"gezet": uit["gezet"], "op_2dehands": len(online), "ronde": ronde}
