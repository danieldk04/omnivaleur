"""
Beheer- en afmeldroutes voor de "verbinding"-campagne (docs/team-notes.md,
21-09-2026). De verstuurlogica zelf staat in backend/services/mail_verbinding.py;
hier alleen de HTTP-laag.

Volgorde die Daniel altijd aanhoudt: eerst /admin/test (komt alleen bij hemzelf
aan), dan pas /admin/verstuur voor een groep, en dat laatste standaard als
dry_run zodat hij eerst de lijst ziet voor er iets weggaat.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from backend.api.deps import get_current_user_full
from backend.services.billing import is_owner_email as _is_owner_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail-verbinding", tags=["mail-verbinding"])


@router.get("/admin/segmenten")
def admin_segmenten(user=Depends(get_current_user_full)):
    """Wie zit er nu in welke groep. Leest alleen, verstuurt niets."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import segmenten

    try:
        s = segmenten()
    except Exception as e:
        logger.exception("Kon segmenten niet ophalen")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    return {groep: {"aantal": len(leden), "voorbeeld": [r["email"] for r in leden[:10]]}
            for groep, leden in s.items()}


@router.post("/admin/test")
def admin_test(groep: str, user=Depends(get_current_user_full)):
    """Stuurt de [TEST]-versie naar de ingelogde eigenaar zelf. Raakt geen
    enkele klantrij aan."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import GROEPEN, verstuur_test

    if groep not in GROEPEN:
        raise HTTPException(status_code=400, detail=f"Onbekende groep: {groep}")
    try:
        verstuur_test(groep, naar=user.email)
    except Exception as e:
        logger.exception("Testmail verbindingscampagne mislukt")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    return {"ok": True, "sent_to": user.email, "groep": groep}


@router.post("/admin/verstuur")
def admin_verstuur(groep: str, dry_run: bool = True, user=Depends(get_current_user_full)):
    """De echte verzending naar een hele groep. dry_run=true (standaard) laat
    alleen zien wie het zou krijgen en verandert niets."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import GROEPEN, verstuur_groep

    if groep not in GROEPEN:
        raise HTTPException(status_code=400, detail=f"Onbekende groep: {groep}")
    try:
        return verstuur_groep(groep, dry_run=dry_run)
    except Exception as e:
        logger.exception("Verbindingscampagne mislukt")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")


# Engels eerst, Nederlands er kleiner onder — zelfde opbouw als de mail zelf
# (zie backend/services/mail_verbinding.py): er is geen betrouwbaar taalveld
# per gebruiker, dus deze pagina is voor iedereen hetzelfde.
_BEVESTIGING = """<!doctype html><html><head><meta charset="utf-8">
<title>{titel_en} — Omnivaleur</title>
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
background:#f0f9ff;margin:0;padding:60px 20px;text-align:center;color:#0f172a">
<div style="max-width:420px;margin:0 auto;background:#fff;border-radius:14px;padding:32px 28px">
<h1 style="font-size:18px;margin:0 0 10px">{titel_en}</h1>
<p style="font-size:14px;color:#334155;line-height:1.6;margin:0 0 14px">{tekst_en}</p>
<h2 style="font-size:14px;margin:0 0 6px;color:#334155">{titel_nl}</h2>
<p style="font-size:12.5px;color:#94a3b8;line-height:1.55;margin:0;font-style:italic">{tekst_nl}</p>
</div></body></html>"""


def _verwerk_afmelding(u: str, t: str) -> bool:
    from backend.services.mail_verbinding import token_geldig

    if not token_geldig(u, t):
        return False
    from backend.database import get_admin_db

    db = get_admin_db()
    try:
        gebruiker = db.auth.admin.get_user_by_id(u)
        email = gebruiker.user.email if gebruiker and gebruiker.user else ""
    except Exception:
        email = ""
    db.table("mail_unsubscribed").upsert({
        "user_id": u, "email": email, "bron": "link",
    }, on_conflict="user_id").execute()
    logger.info(f"Afgemeld voor updates: {u}")
    return True


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_get(u: str = "", t: str = ""):
    """Klik op de zichtbare afmeldlink onderaan de mail. Geen inlog nodig: dat
    zou de link zelf onbruikbaar maken voor wie net wil afmelden."""
    if not u or not t or not _verwerk_afmelding(u, t):
        return HTMLResponse(_BEVESTIGING.format(
            titel="Link klopt niet",
            tekst="Deze afmeldlink is niet geldig meer. Mail gerust naar "
                  "info@revaleur.com als je toch niet meer wilt ontvangen."),
            status_code=400)
    return HTMLResponse(_BEVESTIGING.format(
        titel="Je bent afgemeld",
        tekst="Je krijgt geen updates zoals deze meer van Omnivaleur. Mail en "
              "meldingen over je eigen account (zoals je proefperiode) blijven "
              "gewoon werken."))


@router.post("/unsubscribe")
async def unsubscribe_post(request: Request):
    """List-Unsubscribe-Post (RFC 8058): mailprogramma's als Gmail sturen dit
    zelf, zonder dat er iemand op een link klikt. Moet altijd 200 geven, ook
    als de token niet meer klopt — een mailclient toont de fout toch niet."""
    form = await request.form()
    u = str(form.get("u") or request.query_params.get("u") or "")
    t = str(form.get("t") or request.query_params.get("t") or "")
    if u and t:
        _verwerk_afmelding(u, t)
    return {"ok": True}
