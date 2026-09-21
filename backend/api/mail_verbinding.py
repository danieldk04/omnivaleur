"""
Beheer- en afmeldroutes voor de "verbinding"-campagne (docs/team-notes.md,
21-09-2026). De verstuurlogica zelf staat in backend/services/mail_verbinding.py;
hier alleen de HTTP-laag.

Volgorde die Daniel altijd aanhoudt: eerst /admin/test (komt alleen bij hemzelf
aan), dan pas /admin/verstuur voor een groep, en dat laatste standaard als
dry_run zodat hij eerst de lijst ziet voor er iets weggaat.
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from backend.api.deps import get_current_user_full
from backend.config import settings
from backend.services.billing import is_owner_email as _is_owner_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail-verbinding", tags=["mail-verbinding"])


def _vereis_automatiseringsgeheim(x_admin_secret: str | None) -> None:
    """Voor de lokale, geplande sessie (zie de LaunchAgent-instructies in
    docs/team-notes.md): die logt niet in als Daniel, dus geen JWT. Zelfde
    patroon als backend/api/content.py: SECRET_KEY als gedeeld geheim, via de
    X-Admin-Secret-header. Nooit voor de knoppen die Daniel zelf gebruikt —
    die blijven op zijn eigen login staan."""
    if not settings.secret_key or settings.secret_key == "change-me" or x_admin_secret != settings.secret_key:
        raise HTTPException(status_code=401, detail="unauthorized")


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


def _blokjes_voor_bron(bron: str) -> list[dict] | None:
    """None = vaste (evergreen) inhoud. 'update' = de wekelijkse conceptmail,
    als die er is — anders een duidelijke fout, nooit stil terugvallen op iets
    anders dan wat er echt klaarstaat."""
    if bron != "update":
        return None
    from backend.services.mail_verbinding import huidige_weekupdate

    update = huidige_weekupdate()
    if not update:
        raise HTTPException(status_code=404, detail="Er staat geen wekelijkse update klaar.")
    return update["blokjes"]


@router.post("/admin/test")
def admin_test(groep: str, naar: str = "", bron: str = "evergreen", user=Depends(get_current_user_full)):
    """Stuurt de [TEST]-versie naar de ingelogde eigenaar zelf, of naar een
    ander adres als `naar` is meegegeven (bijvoorbeeld een mail-tester.com-adres
    of een los Gmail/Outlook/iCloud-adres voor de spamproef uit de opdracht).
    Raakt geen enkele klantrij aan."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import GROEPEN, verstuur_test

    if groep not in GROEPEN:
        raise HTTPException(status_code=400, detail=f"Onbekende groep: {groep}")
    blokjes = _blokjes_voor_bron(bron)
    doel = naar.strip() or user.email
    try:
        verstuur_test(groep, naar=doel, blokjes=blokjes)
    except Exception as e:
        logger.exception("Testmail verbindingscampagne mislukt")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    return {"ok": True, "sent_to": doel, "groep": groep}


@router.post("/admin/verstuur")
def admin_verstuur(groep: str, dry_run: bool = True, bron: str = "evergreen",
                   user=Depends(get_current_user_full)):
    """De echte verzending naar een hele groep. dry_run=true (standaard) laat
    alleen zien wie het zou krijgen en verandert niets."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import GROEPEN, verstuur_groep

    if groep not in GROEPEN:
        raise HTTPException(status_code=400, detail=f"Onbekende groep: {groep}")
    blokjes = _blokjes_voor_bron(bron)
    if bron == "update" and not dry_run and blokjes:
        from backend.services.mail_verbinding import ontbrekende_screenshots

        ontbrekend = ontbrekende_screenshots(blokjes)
        if ontbrekend:
            raise HTTPException(
                status_code=400,
                detail="Nog geen screenshot voor: " + ", ".join(ontbrekend)
                       + ". Voeg de afbeelding_url toe voor je hem echt verstuurt.",
            )
    try:
        uitslag = verstuur_groep(groep, dry_run=dry_run, blokjes=blokjes,
                                 kind_label="update" if bron == "update" else "verbinding")
    except Exception as e:
        logger.exception("Verbindingscampagne mislukt")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    if bron == "update" and not dry_run and uitslag.get("verstuurd"):
        from backend.database import get_admin_db
        get_admin_db().table("mail_update_actueel").update(
            {"status": "verstuurd"}).eq("id", "current").execute()
    return uitslag


@router.get("/admin/weekupdate")
def admin_weekupdate(user=Depends(get_current_user_full)):
    """Wat er nu klaarstaat vanuit de lokale geplande sessie, of niets."""
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not allowed")
    from backend.services.mail_verbinding import huidige_weekupdate, ontbrekende_screenshots

    update = huidige_weekupdate()
    if not update:
        return {"status": "leeg"}
    update["ontbrekende_screenshots"] = ontbrekende_screenshots(update["blokjes"])
    return update


@router.post("/automation/weekupdate")
def automation_weekupdate(body: dict, x_admin_secret: str | None = Header(None)):
    """Voor de lokale, wekelijks geplande sessie: legt de nieuwe conceptinhoud
    vast. Verstuurt zelf niets — dat blijft aan Daniel via beheer.html, of aan
    /automation/weekupdate/test voor de review-testmail."""
    _vereis_automatiseringsgeheim(x_admin_secret)
    from backend.services.mail_verbinding import stel_weekupdate_op

    blokjes = body.get("blokjes")
    week_van = body.get("week_van", "")
    if not isinstance(blokjes, list):
        raise HTTPException(status_code=400, detail="'blokjes' moet een lijst zijn")
    try:
        stel_weekupdate_op(blokjes, week_van)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "aantal_blokjes": len(blokjes), "week_van": week_van}


@router.post("/automation/weekupdate/test")
def automation_weekupdate_test(groep: str = "customer", x_admin_secret: str | None = Header(None)):
    """Voor dezelfde sessie: stuurt de zojuist vastgelegde update als [TEST]
    naar de eigenaar, zodat hij hem in zijn eigen inbox ziet staan zonder zelf
    te hoeven inloggen op het beheerpaneel."""
    _vereis_automatiseringsgeheim(x_admin_secret)
    from backend.config import settings as _settings
    from backend.services.mail_verbinding import GROEPEN, huidige_weekupdate, verstuur_test

    if groep not in GROEPEN:
        raise HTTPException(status_code=400, detail=f"Onbekende groep: {groep}")
    update = huidige_weekupdate()
    if not update:
        raise HTTPException(status_code=404, detail="Er staat geen wekelijkse update klaar.")
    try:
        verstuur_test(groep, naar=_settings.owner_email, blokjes=update["blokjes"])
    except Exception as e:
        logger.exception("Testmail wekelijkse update mislukt")
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    return {"ok": True, "sent_to": _settings.owner_email}


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
            titel_en="This link isn't valid",
            tekst_en="This unsubscribe link is no longer valid. Feel free to email "
                     "info@revaleur.com if you'd still like to stop receiving these.",
            titel_nl="Link klopt niet",
            tekst_nl="Deze afmeldlink is niet geldig meer. Mail gerust naar "
                     "info@revaleur.com als je toch niet meer wilt ontvangen."),
            status_code=400)
    return HTMLResponse(_BEVESTIGING.format(
        titel_en="You're unsubscribed",
        tekst_en="You won't get updates like this from Omnivaleur anymore. Mail and "
                 "notifications about your own account (like your trial) keep working "
                 "as usual.",
        titel_nl="Je bent afgemeld",
        tekst_nl="Je krijgt geen updates zoals deze meer van Omnivaleur. Mail en "
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
