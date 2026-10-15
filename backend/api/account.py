"""
Eigen gegevens: downloaden en het account helemaal wissen (AVG art. 15, 17 en 20).

Aanleiding (15-10-2026, Benedikt): "er is geen knop om je account te wissen" en
"waar staat mijn data?". Tot nu toe kon wissen alleen door Daniel met de hand.

Wat er bij wissen gebeurt, in deze volgorde:
  1. wachtwoord controleren (een gekaapte sessie alleen mag dit niet kunnen)
  2. lopende Stripe-abonnementen stopzetten. Lukt dat niet, dan stoppen we: een
     klant wissen die nog betaalt is het ergste wat hier kan gebeuren
  3. foto's weg (Cloudflare R2 en Supabase Storage, alles onder `<user_id>/`)
  4. rijen weg: advertenties, opdrachten, artikelen, koppelingen, tellers
  5. het inlogaccount zelf, als laatste, zodat een mislukte poging opnieuw kan

Blijft bewust staan: de Stripe-klant met zijn facturen (7 jaar bewaarplicht) en
`mail_unsubscribed`, zodat iemand die zich afmeldde geen mail krijgt als hij zich
later opnieuw aanmeldt. Beide staan in de privacyverklaring.

Advertenties die op Vinted, Marktplaats enzovoort staan raken we niet aan; die
staan bij die platforms onder het account van de klant zelf.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from backend.api.deps import get_current_user_full, vergeet_inlogbewijs
from backend.database import (
    IN_BROK, execute_with_retry, fetch_all, get_admin_db, get_db, verse_auth_client,
)
from backend.services import r2_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["account"])

# Wat meegaat in de download. Bewust GEEN inlogsleutels van platforms, geen
# Stripe-nummers en geen `payload`/`result` van opdrachten (technisch en groot).
_EXPORT_JOBS = "id,item_id,platform,action,status,created_at,claimed_at,done_at"
_EXPORT_SUB = "plan,status,trial_ends_at,current_period_end,created_at"
_EXPORT_KOPPELING = "platform,created_at"

# Rijen die direct aan het account hangen: (tabel, kolom). Items, advertenties,
# opdrachten en sync_events gaan apart, in brokken (zie _wis_artikelen).
_WIS_PER_GEBRUIKER = [
    ("import_candidates", "user_id"),
    ("platform_credentials", "user_id"),
    ("platform_notifications", "user_id"),
    ("refresh_quota", "user_id"),
    ("extension_heartbeat", "user_id"),
    ("extension_stiltes", "user_id"),
    ("mail_campaign_log", "user_id"),
    ("referral_codes", "owner_user_id"),
    ("referrals", "user_id"),
    ("referral_rewards", "referrer_user_id"),
    ("referral_rewards", "referred_user_id"),
    ("subscriptions", "user_id"),
]

_LOPEND = {"active", "trialing", "past_due", "unpaid", "incomplete"}


class WisVerzoek(BaseModel):
    password: str


def _lees(db, tabel: str, kolommen: str, kolom: str, uid: str, order_by: str = "id") -> list[dict]:
    try:
        return fetch_all(lambda: db.table(tabel).select(kolommen).eq(kolom, uid), order_by=order_by)
    except Exception:
        # Een tabel die niet bestaat (migratie niet gedraaid) mag de download
        # niet breken; wat er niet is kan ook niet in het bestand.
        logger.warning("Download: tabel %s niet te lezen, overgeslagen", tabel, exc_info=True)
        return []


def bouw_download(uid: str, email: str, aangemaakt) -> dict:
    db = get_db()
    artikelen = _lees(db, "items", "*", "user_id", uid)
    advertenties: list[dict] = []
    ids = [a["id"] for a in artikelen]
    for i in range(0, len(ids), IN_BROK):
        stuk = ids[i:i + IN_BROK]
        advertenties.extend(fetch_all(lambda s=stuk: db.table("listings").select("*").in_("item_id", s)))
    return {
        "gemaakt_op": datetime.now(timezone.utc).isoformat(),
        "account": {"id": uid, "email": email, "aangemaakt": str(aangemaakt or "")},
        "abonnement": _lees(db, "subscriptions", _EXPORT_SUB, "user_id", uid),
        "artikelen": artikelen,
        "advertenties": advertenties,
        "opdrachten": _lees(db, "jobs", _EXPORT_JOBS, "user_id", uid),
        "gekoppelde_platforms": _lees(db, "platform_credentials", _EXPORT_KOPPELING, "user_id", uid),
        "gevonden_advertenties_bij_import": _lees(db, "import_candidates", "*", "user_id", uid),
    }


@router.get("/export")
async def download_mijn_gegevens(user=Depends(get_current_user_full)):
    data = await asyncio.to_thread(bouw_download, user.id, user.email, getattr(user, "created_at", None))
    inhoud = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=inhoud,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="omnivaleur-mijn-gegevens.json"'},
    )


# ── wissen ────────────────────────────────────────────────────────────────────

def _stop_abonnementen(uid: str) -> int:
    """Zet elk lopend Stripe-abonnement van deze gebruiker stop. Gooit bij falen."""
    db = get_db()
    rijen = execute_with_retry(
        db.table("subscriptions").select("stripe_customer_id,stripe_subscription_id").eq("user_id", uid)
    ).data or []
    klanten = {r["stripe_customer_id"] for r in rijen if r.get("stripe_customer_id")}
    sub_ids = {r["stripe_subscription_id"] for r in rijen if r.get("stripe_subscription_id")}
    # Een klant kan er twee hebben (zie kennisbank): daarom bij Stripe navragen
    # per klant en niet alleen het ene nummer in onze tabel vertrouwen.
    for klant in klanten:
        for s in stripe.Subscription.list(customer=klant, status="all", limit=100).data or []:
            if (s.get("status") if isinstance(s, dict) else s.status) in _LOPEND:
                sub_ids.add(s["id"])
    gestopt = 0
    for sid in sub_ids:
        try:
            stripe.Subscription.cancel(sid)
            gestopt += 1
        except Exception as e:
            if "No such subscription" in str(e) or getattr(e, "code", None) == "resource_missing":
                continue
            # Al geannuleerd telt ook als klaar; alles anders is een echte fout.
            if "canceled" in str(e).lower() and "already" in str(e).lower():
                continue
            raise
    return gestopt


def _wis_foto_bestanden(uid: str) -> int:
    """Alle foto's onder `<uid>/`, in R2 en in Supabase Storage."""
    voorvoegsel = f"{uid}/"
    weg = 0
    if r2_storage.is_configured():
        sleutels, token = [], None
        client = r2_storage.get_client()
        from backend.config import settings
        while True:
            args = {"Bucket": settings.r2_bucket, "Prefix": voorvoegsel}
            if token:
                args["ContinuationToken"] = token
            antw = client.list_objects_v2(**args)
            sleutels += [o["Key"] for o in antw.get("Contents", [])]
            if not antw.get("IsTruncated"):
                break
            token = antw.get("NextContinuationToken")
        weg += r2_storage.delete(sleutels)
    emmer = get_db().storage.from_("photos")
    for map_ in (uid, f"{uid}/imported"):
        while True:
            bestanden = emmer.list(path=map_, options={"limit": 500}) or []
            namen = [f"{map_}/{b['name']}" for b in bestanden if b.get("name") and b.get("id")]
            if not namen:
                break
            emmer.remove(namen)
            weg += len(namen)
    return weg


def _wis_artikelen(uid: str) -> int:
    """Artikelen met alles eraan, in brokken. Eén grote delete liep eerder tegen
    de tijdslimiet van de database (57014, 12-10-2026)."""
    db = get_db()
    ids = [r["id"] for r in fetch_all(lambda: db.table("items").select("id").eq("user_id", uid))]
    for i in range(0, len(ids), IN_BROK):
        stuk = ids[i:i + IN_BROK]
        adv = [r["id"] for r in fetch_all(lambda s=stuk: db.table("listings").select("id").in_("item_id", s))]
        for j in range(0, len(adv), IN_BROK):
            execute_with_retry(db.table("sync_events").delete().in_("listing_id", adv[j:j + IN_BROK]))
        execute_with_retry(db.table("listings").delete().in_("item_id", stuk))
        execute_with_retry(db.table("jobs").delete().in_("item_id", stuk))
        execute_with_retry(db.table("items").delete().in_("id", stuk))
    execute_with_retry(db.table("jobs").delete().eq("user_id", uid))
    return len(ids)


def wis_account(uid: str) -> dict:
    uitkomst = {"abonnementen_gestopt": _stop_abonnementen(uid)}
    uitkomst["foto_bestanden"] = _wis_foto_bestanden(uid)
    uitkomst["artikelen"] = _wis_artikelen(uid)
    db = get_db()
    for tabel, kolom in _WIS_PER_GEBRUIKER:
        try:
            execute_with_retry(db.table(tabel).delete().eq(kolom, uid))
        except Exception:
            # Tabel ontbreekt of kolom bestaat niet: dan staat er ook niets. Een
            # echte storing komt bij de volgende poging weer boven.
            logger.warning("Wissen: %s.%s niet gelukt of niet aanwezig", tabel, kolom, exc_info=True)
            if _tabel_heeft_rijen(db, tabel, kolom, uid):
                raise
    get_admin_db().auth.admin.delete_user(uid)
    vergeet_inlogbewijs()
    return uitkomst


def _tabel_heeft_rijen(db, tabel: str, kolom: str, uid: str) -> bool:
    try:
        return bool(execute_with_retry(db.table(tabel).select(kolom).eq(kolom, uid).limit(1)).data)
    except Exception:
        return False


def _wachtwoord_klopt(email: str, wachtwoord: str) -> bool:
    try:
        res = verse_auth_client().auth.sign_in_with_password({"email": email, "password": wachtwoord})
        return res.user is not None
    except Exception:
        return False


@router.post("/delete")
async def verwijder_mijn_account(body: WisVerzoek, user=Depends(get_current_user_full)):
    """POST en geen DELETE: het wachtwoord hoort in de body, niet in een adres."""
    if not body.password or not await asyncio.to_thread(_wachtwoord_klopt, user.email, body.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    try:
        uitkomst = await asyncio.to_thread(wis_account, user.id)
    except Exception:
        logger.exception("Account wissen mislukt voor %s", user.id)
        raise HTTPException(
            status_code=500,
            detail="We could not finish deleting your account. Nothing is lost on your side, "
                   "please try again in a few minutes or email info@omnivaleur.com.",
        )
    logger.info("Account %s gewist: %s", user.id, uitkomst)
    return {"ok": True}
