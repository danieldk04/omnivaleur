"""Het persoonlijke adres waar een klant zijn Vinted-verkoopmails naartoe stuurt.

Elke klant krijgt één geheim adres. Alleen wie het adres kent kan mail laten
meetellen, en een verkoop telt bovendien alleen als de mail aantoonbaar van Vinted
komt (zie backend/services/vinted_verkoopmail.py).
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user_full
from backend.config import settings
from backend.database import get_admin_db, naast_de_lus
from backend.services.billing import is_owner_email

router = APIRouter(prefix="/api/vinted-mail", tags=["vinted-mail"])


@router.get("/adres")
async def mijn_adres(user=Depends(get_current_user_full)):
    """Geeft het persoonlijke ontvangstadres, en maakt het aan bij het eerste verzoek."""
    if not settings.vinted_inbound_domain:
        raise HTTPException(status_code=503, detail="Not available yet")
    if not settings.vinted_mail_open_voor_klanten and not is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Not available yet")
    db = get_admin_db()
    rij = (await naast_de_lus(lambda: db.table("platform_credentials").select("extra_data")
           .eq("user_id", user.id).eq("platform", "vinted_mail").limit(1).execute())).data
    token = ((rij[0].get("extra_data") or {}).get("token") if rij else None)
    if not token:
        token = secrets.token_hex(12)  # 24 tekens, past op adres_token()
        await naast_de_lus(lambda: db.table("platform_credentials").upsert(
            {"user_id": user.id, "platform": "vinted_mail", "extra_data": {"token": token}},
            on_conflict="user_id,platform").execute())
    return {"adres": f"vinted-{token}@{settings.vinted_inbound_domain}"}
