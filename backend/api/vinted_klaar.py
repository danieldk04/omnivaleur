"""Vinted plaatsklaar: Omnivaleur maakt de advertentie klaar, de verkoper plakt zelf.

WAAROM (Daniel, 22-11-2026): Vinted verbiedt externe software op het account. In de
stand "plaatsklaar" (instellingen.VINTED_MODUS) raakt Omnivaleur Vinted nooit aan: geen
opdrachten, geen scans. Deze routes geven de verkoper alles wat hij nodig heeft om het
zelf te doen: tekst en foto's om te kopiëren, en een lijstje van wat nog op Vinted moet
(verwijderen na een verkoop elders, prijs aanpassen). Meldt hij iets als gedaan, dan
volgt de administratie, zodat verkoopherkenning via mail (vinted_verkoopmail.py) en de
rest van het dashboard blijven kloppen.
"""
import io
import logging
import re
import zipfile
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from backend.api.deps import get_current_user
from backend.database import get_db, naast_de_lus
from backend.services import instellingen

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vinted-klaar", tags=["vinted-klaar"])

MAX_FOTOS = 20
_VINTED_URL = re.compile(r"^https://(?:www\.)?vinted\.[a-z.]{2,6}/items/(\d+)[^\s]*$", re.IGNORECASE)


def _vinted_nummer_uit_url(url: str | None) -> tuple[str | None, str | None]:
    """(schone url, nummer) als dit echt een Vinted-advertentieadres is, anders (None, None)."""
    m = _VINTED_URL.match((url or "").strip())
    if not m:
        return None, None
    return m.group(0), m.group(1)


async def _eigen_artikel(db, user_id: str, item_id: str) -> dict:
    rij = (await naast_de_lus(lambda: db.table("items").select("*")
           .eq("id", item_id).eq("user_id", user_id).limit(1).execute())).data
    if not rij:
        raise HTTPException(status_code=404, detail="Item not found")
    return rij[0]


@router.get("/pakket/{item_id}")
async def pakket(item_id: str, user_id: str = Depends(get_current_user)):
    """Alles voor één Vinted-advertentie, klaar om te kopiëren."""
    from backend.api.jobs import vinted_omschrijving
    from backend.services.crosslist import omschrijving_met_slot, slotteksten_van

    db = get_db()
    item = await _eigen_artikel(db, user_id, item_id)
    inst = instellingen.lees(user_id)
    engels = inst.get("vinted_taal") == "en"
    titel = (item.get("title_en") if engels and item.get("title_en") else item.get("title")) or ""
    tekst = (item.get("description_en") if engels and item.get("description_en")
             else item.get("description")) or ""
    standaard, vinted_slot = slotteksten_van(user_id)
    tekst = omschrijving_met_slot(tekst, "vinted", standaard, vinted_slot)
    tekst = vinted_omschrijving(tekst, vinted_slot)
    prijs = item.get("price_vinted") if item.get("price_vinted") else item.get("price")
    staat = inst.get(instellingen.VINTED_STAAT) or item.get("condition")
    fotos = [u for u in (item.get("photo_urls") or [])
             if isinstance(u, str) and u.startswith("https://")][:MAX_FOTOS]
    lijst = (await naast_de_lus(lambda: db.table("listings")
             .select("status,platform_listing_url").eq("item_id", item_id)
             .eq("platform", "vinted").limit(1).execute())).data
    return {
        "item_id": item_id,
        "titel": titel[:100],
        "omschrijving": tekst,
        "prijs": prijs,
        "staat": staat,
        "merk": item.get("brand"),
        "maat": item.get("size"),
        "kleur": item.get("color"),
        "categorie": item.get("category"),
        "fotos": fotos,
        "vinted_status": (lijst[0]["status"] if lijst else None),
        "vinted_url": (lijst[0].get("platform_listing_url") if lijst else None),
    }


@router.get("/fotos/{item_id}")
async def foto_zip(item_id: str, user_id: str = Depends(get_current_user)):
    """De foto's van het artikel in één zipbestand, in de juiste volgorde."""
    db = get_db()
    item = await _eigen_artikel(db, user_id, item_id)
    urls = [u for u in (item.get("photo_urls") or [])
            if isinstance(u, str) and u.startswith("https://")][:MAX_FOTOS]
    if not urls:
        raise HTTPException(status_code=404, detail="This item has no photos")

    def _bouw() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z, httpx.Client(timeout=20, follow_redirects=True) as c:
            for n, u in enumerate(urls, 1):
                r = c.get(u)
                r.raise_for_status()
                ext = ".png" if "png" in r.headers.get("content-type", "") else ".jpg"
                z.writestr(f"{n:02d}{ext}", r.content)
        return buf.getvalue()

    import asyncio
    try:
        data = await asyncio.to_thread(_bouw)
    except Exception as e:  # noqa: BLE001
        logger.warning("foto-zip mislukt voor %s: %s", item_id, e)
        raise HTTPException(status_code=502, detail="Could not collect the photos. Try again in a moment.")
    naam = re.sub(r"[^a-z0-9]+", "-", (item.get("title") or "photos").lower()).strip("-")[:40] or "photos"
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{naam}.zip"'})


@router.post("/geplaatst/{item_id}")
async def geplaatst(item_id: str, body: dict | None = None, user_id: str = Depends(get_current_user)):
    """De verkoper heeft het zelf op Vinted gezet. Vastleggen zodat het artikel als 'op Vinted'
    telt (nodig voor verkoopherkenning en voor het verwijderlijstje na een verkoop elders).
    Een geplakt Vinted-adres is optioneel; een ander adres wordt niet opgeslagen."""
    db = get_db()
    await _eigen_artikel(db, user_id, item_id)
    url, nummer = _vinted_nummer_uit_url((body or {}).get("url"))
    nu = datetime.now(timezone.utc).isoformat()
    velden = {"status": "active", "listed_at": nu, "error_message": None}
    if url:
        velden.update({"platform_listing_url": url, "platform_listing_id": nummer})
    bestaand = (await naast_de_lus(lambda: db.table("listings").select("id")
                .eq("item_id", item_id).eq("platform", "vinted").limit(1).execute())).data
    if bestaand:
        await naast_de_lus(lambda: db.table("listings").update(velden).eq("id", bestaand[0]["id"]).execute())
    else:
        await naast_de_lus(lambda: db.table("listings").insert(
            {"item_id": item_id, "platform": "vinted", **velden}).execute())
    return {"ok": True, "url_bewaard": bool(url)}


_TAAKACTIES = ("create", "delete", "edit")


@router.get("/taken")
async def taken(user_id: str = Depends(get_current_user)):
    """Wat er op Vinted nog door de verkoper zelf gedaan moet worden."""
    db = get_db()
    rijen = (await naast_de_lus(lambda: db.table("jobs")
             .select("id,item_id,action,payload,created_at")
             .eq("user_id", user_id).eq("platform", "vinted").eq("status", "pending")
             .in_("action", list(_TAAKACTIES)).order("created_at").limit(200).execute())).data or []
    ids = list({r["item_id"] for r in rijen if r.get("item_id")})
    titels = {}
    if ids:
        for i in (await naast_de_lus(lambda: db.table("items").select("id,title,price")
                  .eq("user_id", user_id).in_("id", ids[:100]).execute())).data or []:
            titels[i["id"]] = i
    uit = []
    for r in rijen:
        it = titels.get(r.get("item_id"))
        if not it:
            continue
        pl = r.get("payload") or {}
        uit.append({"job_id": r["id"], "item_id": r["item_id"], "actie": r["action"],
                    "titel": it["title"], "prijs": it.get("price"),
                    "url": pl.get("platform_listing_url")})
    return {"taken": uit}


@router.post("/taak/{job_id}/klaar")
async def taak_klaar(job_id: str, user_id: str = Depends(get_current_user)):
    """De verkoper heeft deze Vinted-taak zelf gedaan."""
    db = get_db()
    rij = (await naast_de_lus(lambda: db.table("jobs").select("id,item_id,action,status")
           .eq("id", job_id).eq("user_id", user_id).eq("platform", "vinted").limit(1).execute())).data
    if not rij or rij[0]["status"] != "pending" or rij[0]["action"] not in _TAAKACTIES:
        raise HTTPException(status_code=404, detail="Task not found")
    taak = rij[0]
    nu = datetime.now(timezone.utc).isoformat()
    await naast_de_lus(lambda: db.table("jobs").update(
        {"status": "cancelled", "result": {"done_by_seller": True, "at": nu}})
        .eq("id", job_id).execute())
    if taak["action"] == "delete":
        await naast_de_lus(lambda: db.table("listings").update({"status": "delisted"})
                           .eq("item_id", taak["item_id"]).eq("platform", "vinted")
                           .eq("status", "active").execute())
    elif taak["action"] == "create":
        return await geplaatst(taak["item_id"], None, user_id)
    return {"ok": True}
