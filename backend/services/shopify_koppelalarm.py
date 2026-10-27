"""Alarm bij een Shopify-koppeling die niet lukt, zonder valse meldingen.

Daniel, 27-10-2026: hij kreeg "Shopify koppelen mislukt" terwijl de klant een
minuut later gewoon gekoppeld was (voordeelsieraden, 09e089ec). De mail werd
verstuurd op het moment van de eerste weigering, en de zin "Lukt het, dan komt
er geen mail" in die mail was niet waar: niets keek ooit of het daarna lukte.
De eerste poging faalt bijna altijd (app nog niet geïnstalleerd), dus de meeste
mails waren onterecht.

Nu: een mislukte poging wordt alleen genoteerd. Een vaste ronde kijkt na
WACHT_MINUTEN of de klant inmiddels een koppeling heeft die echt werkt (een
live aanroep naar Shopify, niet alleen een rij in de database). Zo ja, dan komt
er geen mail. Zo nee, dan komt er één mail die zegt dat het NIET gelukt is.
De stand staat in de database, zodat een deploy hem niet kwijtmaakt (Railway
doodt dan alles wat loopt).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend.database import get_db

logger = logging.getLogger(__name__)

RIJ = "_shopify_mislukt"
WACHT_MINUTEN = 20
BEWAAR_DAGEN = 7


def _nu() -> datetime:
    return datetime.now(timezone.utc)


def noteer_mislukking(user_id: str, shop: str, fout: Exception) -> None:
    """Leg de poging vast. Geen mail: de ronde beslist later of die nodig is."""
    db = get_db()
    oud = (db.table("platform_credentials").select("extra_data").eq("user_id", user_id)
           .eq("platform", RIJ).limit(1).execute().data or [])
    eerder = (oud[0].get("extra_data") or {}) if oud else {}
    nu = _nu().isoformat()
    db.table("platform_credentials").upsert({
        "user_id": user_id,
        "platform": RIJ,
        "extra_data": {
            "shop": shop or "",
            "code": getattr(fout, "code", "") or "",
            "uitleg": getattr(fout, "uitleg", "") or "",
            "melding": str(fout),
            "sinds": eerder.get("sinds") or nu,
            "laatste": nu,
            "pogingen": int(eerder.get("pogingen") or 0) + 1,
            # Een nieuwe mislukking na een al verstuurde mail mag opnieuw gemeld
            # worden, maar pas na weer WACHT_MINUTEN.
            "gemeld": False,
        },
    }, on_conflict="user_id,platform").execute()


def wis_mislukking(user_id: str) -> None:
    """De klant is gekoppeld: de genoteerde mislukking is achterhaald."""
    try:
        (get_db().table("platform_credentials").delete()
         .eq("user_id", user_id).eq("platform", RIJ).execute())
    except Exception as e:
        logger.warning("Genoteerde Shopify-mislukking van %s niet gewist: %s", user_id, e)


async def werkt_de_koppeling(user_id: str) -> tuple[bool, str]:
    """Bewijs met een echte aanroep naar Shopify dat de koppeling nu werkt."""
    from backend.platforms.shopify import controleer_admin_token, controleer_app_gegevens

    rijen = (get_db().table("platform_credentials").select("access_token,extra_data")
             .eq("user_id", user_id).eq("platform", "shopify").limit(1).execute().data or [])
    if not rijen:
        return False, "er staat geen Shopify-koppeling in de database"
    extra = rijen[0].get("extra_data") or {}
    shop = extra.get("shop_domain") or ""
    try:
        if extra.get("koppeling") == "eigen_app":
            await controleer_app_gegevens(shop, extra.get("client_id"), extra.get("client_secret"))
        elif extra.get("koppeling") == "eigen_sleutel":
            await controleer_admin_token(shop, rijen[0].get("access_token"))
        else:
            # Koppeling via de App Store: geen geheim om opnieuw mee te vragen.
            return bool(rijen[0].get("access_token")), "koppeling via de App Store, sleutel aanwezig"
    except Exception as e:
        return False, f"Shopify weigert de opgeslagen koppeling: {e}"
    return True, "Shopify accepteert de opgeslagen koppeling"


def _mail(user_id: str, extra: dict, nu_stand: str) -> bool:
    from backend.services.email import send_email
    from backend.services.referral_mail import email_van

    adres = email_van(user_id) or user_id
    code = extra.get("code") or "geen"
    tekst = (
        f"{adres} wilde Shopify koppelen en dat is NIET gelukt.\n\n"
        f"De eerste poging was om {extra.get('sinds', '?')} (UTC), de laatste om "
        f"{extra.get('laatste', '?')}, in totaal {extra.get('pogingen', 1)} keer.\n"
        f"Ik heb {WACHT_MINUTEN} minuten na de laatste poging opnieuw gekeken: {nu_stand}.\n\n"
        f"Winkeladres: {extra.get('shop') or '(leeg)'}\n"
        f"Reden van Shopify: {code} {extra.get('uitleg') or ''}".rstrip() + "\n"
        f"Dit zag de klant op het scherm:\n{extra.get('melding') or ''}\n\n"
        "De klant staat dus nog zonder Shopify. Lukt het de klant later alsnog, "
        "dan krijg je hier geen tweede mail over.\n"
    )
    return bool(send_email(subject=f"Shopify koppelen NIET gelukt: {adres}", body=tekst))


async def controleer_mislukte_koppelingen() -> dict:
    """Ronde: wis wat inmiddels gelukt is, meld wat na WACHT_MINUTEN nog niet lukt."""
    db = get_db()
    rijen = (db.table("platform_credentials").select("user_id,extra_data")
             .eq("platform", RIJ).execute().data or [])
    uitslag = {"gelukt": 0, "gemeld": 0, "wachten": 0}
    nu = _nu()
    for r in rijen:
        uid, extra = r["user_id"], r.get("extra_data") or {}
        try:
            laatste = datetime.fromisoformat(extra.get("laatste"))
        except Exception:
            laatste = nu - timedelta(minutes=WACHT_MINUTEN)
        if nu - laatste < timedelta(minutes=WACHT_MINUTEN):
            uitslag["wachten"] += 1
            continue
        werkt, stand = await werkt_de_koppeling(uid)
        if werkt:
            wis_mislukking(uid)
            uitslag["gelukt"] += 1
            logger.info("Shopify-koppeling van %s is inmiddels gelukt, geen mail", uid)
            continue
        if nu - laatste > timedelta(days=BEWAAR_DAGEN):
            wis_mislukking(uid)
            continue
        if extra.get("gemeld"):
            continue
        if _mail(uid, extra, stand):
            extra["gemeld"] = True
            db.table("platform_credentials").update({"extra_data": extra}).eq(
                "user_id", uid).eq("platform", RIJ).execute()
            uitslag["gemeld"] += 1
    return uitslag
