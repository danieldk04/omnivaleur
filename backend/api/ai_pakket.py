"""Routes van het AI-pakket (20-11-2026). Alles hangt aan settings.ai_pakket_aan.

Staat de vlag uit (standaard), dan antwoordt elke route 404 en gebeurt er niets:
geen model-aanroep, geen schrijfactie. Zo is het pakket onzichtbaar tot Daniel
het aanzet.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.api.deps import get_current_user
from backend.config import settings
from backend.database import get_db, fetch_all, execute_with_retry, IN_BROK
from backend.services import ai_bulk, ai_quota, achtergrond

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-pakket", tags=["ai-pakket"])

_LEES = "id,title,description,price," + ",".join(ai_bulk.PRIJSVELD.values())


def _aan(user_id: str | None = None) -> None:
    """Vlag uit = 404 voor iedereen. Vlag aan = alleen wie het pakket heeft:
    Ultra, 3 betalende vrienden, of de eigenaar."""
    if not settings.ai_pakket_aan:
        raise HTTPException(status_code=404, detail="Not found")
    if user_id is not None and not heeft_pakket(user_id):
        raise HTTPException(status_code=403, detail="The AI package comes with Ultra, or with 3 paying friends")


def heeft_pakket(user_id: str) -> bool:
    try:
        from backend.services.light import plan_van_gebruiker
        from backend.services.vriendenvoordeel import heeft_ai_via_vrienden
        from backend.services.billing import is_owner_email
        from backend.services.referral_mail import email_van
        if is_owner_email(email_van(user_id)):
            return True
        return plan_van_gebruiker(user_id) == "ultra" or heeft_ai_via_vrienden(user_id)
    except Exception:
        logger.exception("Kon het pakket van %s niet nagaan", user_id)
        return False


def _lees_items(user_id: str) -> list[dict]:
    db = get_db()
    return fetch_all(lambda: db.table("items").select(_LEES).eq("user_id", user_id))


@router.get("/status")
def status(user_id: str = Depends(get_current_user)):
    _aan(user_id)
    return {"aan": True, "plafond": ai_quota.PLAFOND,
            "gebruikt": {k: ai_quota.gebruikt(user_id, k) for k in ai_quota.PLAFOND},
            "ongedaan_mogelijk": bool(ai_quota.lees_los(user_id, "laatste"))}


@router.post("/bulk/voorbeeld")
async def bulk_voorbeeld(body: dict, user_id: str = Depends(get_current_user)):
    _aan(user_id)
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
    _aan(user_id)
    body = body or {}
    plan_op = ai_quota.lees_los(user_id, "voorbeeld")
    if (not isinstance(plan_op, dict) or plan_op.get("id") != body.get("voorbeeld_id")
            or time.time() - float(plan_op.get("tijd") or 0) > ai_bulk.VOORBEELD_GELDIG_S):
        raise HTTPException(status_code=409, detail="This preview has expired. Ask again.")
    if body.get("bevestig") is not True:
        raise HTTPException(status_code=400, detail="Confirmation is required")
    bew = ai_bulk.valideer(json.dumps(plan_op["bewerking"]))
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
    prijs_set = {x["id"] for x in w if x["veld"].startswith("price")}
    prijs_ids = [i for i in gedaan if i in prijs_set]
    if prijs_ids:
        asyncio.create_task(_prijzen_doorgeven(user_id, prijs_ids))
    return {"gewijzigd": len(gedaan), "ongedaan_id": blok["id"]}


@router.post("/bulk/ongedaan")
async def bulk_ongedaan(body: dict, user_id: str = Depends(get_current_user)):
    _aan(user_id)
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


# ── achtergrond van de eerste foto verwijderen (Modal) ──────────────────────
# Zelfde veilige vorm als de bulkopdracht: voorbeeld (er verandert niets), bevestigen,
# 1 klik ongedaan. De originele foto blijft in de opslag staan; alleen het adres op
# plek 1 wijzigt. Plaatsingen die al online staan houden hun foto; nieuwe en
# herplaatste advertenties gebruiken de nieuwe.

def _haal_foto(url: str) -> bytes:
    import httpx
    with httpx.Client(timeout=30.0, follow_redirects=False) as c:
        r = c.get(url)
    if r.status_code != 200 or not r.content or len(r.content) > achtergrond.MAX_BYTES:
        raise ValueError("foto niet op te halen")
    return r.content


def _bewerk_een(user_id: str, item: dict, kleur: str = achtergrond.STANDAARD_KLEUR) -> dict:
    """Blokkerend. Geeft {'id','oud','nieuw'} of {'id','overgeslagen': reden}."""
    from backend.services import photo_mirror
    from backend.services.image_upload import upload_image_sync
    import hashlib
    fotos = item.get("photo_urls") or []
    if not fotos or not photo_mirror.is_mirrored(fotos[0]):
        return {"id": item["id"], "overgeslagen": "geen_eigen_foto"}
    oud = fotos[0]
    try:
        uit = achtergrond.knip(_haal_foto(oud), kleur)
    except achtergrond.NietBeschikbaar:
        raise
    except Exception:  # noqa: BLE001 - een foto die niet lukt mag de rest niet stoppen
        logger.exception("Achtergrond: foto van %s niet verwerkt", item["id"])
        return {"id": item["id"], "overgeslagen": "mislukt"}
    naam = "ai-achtergrond/" + hashlib.sha256(uit).hexdigest()[:40] + ".jpg"
    return {"id": item["id"], "oud": oud, "nieuw": upload_image_sync(uit, naam)}


@router.post("/achtergrond/voorbeeld")
async def achtergrond_voorbeeld(body: dict, user_id: str = Depends(get_current_user)):
    _aan(user_id)
    ids = [str(i) for i in ((body or {}).get("ids") or []) if i][:achtergrond.MAX_PER_KEER]
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one item")
    kleur = (body or {}).get("kleur") or achtergrond.STANDAARD_KLEUR
    if not achtergrond.geldige_kleur(kleur):
        raise HTTPException(status_code=400, detail="Choose a valid background colour")
    if not achtergrond.ingesteld():
        raise HTTPException(status_code=503, detail="Background removal is temporarily unavailable. Nothing was changed.")
    if not ai_quota.ruimte(user_id, "achtergronden", len(ids)):
        raise HTTPException(status_code=429, detail="Monthly limit of background removals reached")
    db = get_db()
    items = await asyncio.to_thread(lambda: fetch_all(
        lambda: db.table("items").select("id,photo_urls").eq("user_id", user_id).in_("id", ids)))
    resultaat, klaar = [], {}
    for it in items:
        try:
            r = await asyncio.to_thread(_bewerk_een, user_id, it, kleur)
        except achtergrond.NietBeschikbaar:
            raise HTTPException(status_code=503, detail="Background removal is temporarily unavailable. Nothing was changed.")
        if "nieuw" in r:
            ai_quota.tel(user_id, "achtergronden")
            klaar[r["id"]] = {"oud": r["oud"], "nieuw": r["nieuw"]}
        resultaat.append(r)
    if not klaar:
        return {"uitvoerbaar": False, "artikelen": resultaat}
    vid = uuid.uuid4().hex[:12]
    ai_quota.bewaar(user_id, "foto_voorbeeld", {"id": vid, "tijd": time.time(), "items": klaar})
    return {"uitvoerbaar": True, "voorbeeld_id": vid, "artikelen": resultaat}


@router.post("/achtergrond/uitvoeren")
async def achtergrond_uitvoeren(body: dict, user_id: str = Depends(get_current_user)):
    _aan(user_id)
    body = body or {}
    plan_op = ai_quota.lees_los(user_id, "foto_voorbeeld")
    if (not isinstance(plan_op, dict) or plan_op.get("id") != body.get("voorbeeld_id")
            or time.time() - float(plan_op.get("tijd") or 0) > ai_bulk.VOORBEELD_GELDIG_S):
        raise HTTPException(status_code=409, detail="This preview has expired. Ask again.")
    if body.get("bevestig") is not True:
        raise HTTPException(status_code=400, detail="Confirmation is required")
    wens = plan_op["items"]
    db = get_db()
    ids = list(wens)

    def _doe() -> list[str]:
        nu = {r["id"]: r for r in fetch_all(lambda: db.table("items").select("id,photo_urls")
                                            .eq("user_id", user_id).in_("id", ids))}
        gedaan, blok = [], {}
        for iid, w in wens.items():
            fotos = list((nu.get(iid) or {}).get("photo_urls") or [])
            # Alleen als de foto nog is zoals bij het voorbeeld; een latere wijziging van de klant wint.
            if fotos and fotos[0] == w["oud"]:
                blok[iid] = w
        if not blok:
            return []
        ai_quota.bewaar(user_id, "laatste_foto", {"id": uuid.uuid4().hex[:12], "items": blok})
        for iid, w in blok.items():
            fotos = list(nu[iid]["photo_urls"]); fotos[0] = w["nieuw"]
            rij = execute_with_retry(db.table("items").update({"photo_urls": fotos})
                                     .eq("id", iid).eq("user_id", user_id))
            if getattr(rij, "data", None):
                gedaan.append(iid)
        return gedaan

    gedaan = await asyncio.to_thread(_doe)
    ai_quota.bewaar(user_id, "foto_voorbeeld", None)
    laatste = ai_quota.lees_los(user_id, "laatste_foto") or {}
    return {"gewijzigd": len(gedaan), "ongedaan_id": laatste.get("id")}


@router.post("/achtergrond/ongedaan")
async def achtergrond_ongedaan(body: dict, user_id: str = Depends(get_current_user)):
    _aan(user_id)
    blok = ai_quota.lees_los(user_id, "laatste_foto")
    if not isinstance(blok, dict) or blok.get("id") != (body or {}).get("ongedaan_id"):
        raise HTTPException(status_code=404, detail="Nothing to undo")
    db = get_db()
    ids = list(blok["items"])

    def _doe() -> tuple[int, int]:
        nu = {r["id"]: r for r in fetch_all(lambda: db.table("items").select("id,photo_urls")
                                            .eq("user_id", user_id).in_("id", ids))}
        terug = over = 0
        for iid, w in blok["items"].items():
            fotos = list((nu.get(iid) or {}).get("photo_urls") or [])
            if fotos and fotos[0] == w["nieuw"]:
                fotos[0] = w["oud"]
                rij = execute_with_retry(db.table("items").update({"photo_urls": fotos})
                                         .eq("id", iid).eq("user_id", user_id))
                terug += 1 if getattr(rij, "data", None) else 0
            else:
                over += 1
        return terug, over

    n, over = await asyncio.to_thread(_doe)
    ai_quota.bewaar(user_id, "laatste_foto", None)
    return {"teruggezet": n, "overgeslagen": over}


@router.post("/achtergrond/upload")
async def achtergrond_upload(request: Request, kleur: str = achtergrond.STANDAARD_KLEUR,
                             user_id: str = Depends(get_current_user)):
    """Een eigen foto (de bytes als body): geeft de foto terug met de gekozen achtergrond.
    Er wordt niets opgeslagen en geen artikel gewijzigd; de klant bewaart het resultaat zelf."""
    _aan(user_id)
    if not achtergrond.geldige_kleur(kleur):
        raise HTTPException(status_code=400, detail="Choose a valid background colour")
    if not achtergrond.ingesteld():
        raise HTTPException(status_code=503, detail="Background removal is temporarily unavailable. Nothing was changed.")
    if not ai_quota.ruimte(user_id, "achtergronden"):
        raise HTTPException(status_code=429, detail="Monthly limit of background removals reached")
    foto = await request.body()
    if not foto or len(foto) > achtergrond.MAX_BYTES:
        raise HTTPException(status_code=413, detail="That photo is too large. Maximum is 12 MB.")
    ai_quota.tel(user_id, "achtergronden")
    try:
        uit = await asyncio.to_thread(achtergrond.knip, foto, kleur)
    except achtergrond.NietBeschikbaar:
        raise HTTPException(status_code=503, detail="Background removal is temporarily unavailable. Nothing was changed.")
    except ValueError:
        raise HTTPException(status_code=400, detail="That file could not be read as a photo.")
    return Response(content=uit, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
