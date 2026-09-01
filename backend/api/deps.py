import asyncio
import hashlib
import logging
import time

from fastapi import Depends, Header, HTTPException
from backend.database import (AuthTijdelijkOnbereikbaar, auth_met_herkansing,
                               get_auth_db, get_db)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HET INLOGBEWIJS WORDT EEN MINUUT ONTHOUDEN
#
# WAAROM (01-09-2026). Deze controle draait op zo goed als elk verzoek, en elke
# controle was een apart verzoek aan Supabase: 61.030 stuks in één etmaal, voor
# zeven gebruikers. Een token verandert in die tijd niet, dus dat waren 61.000
# keer dezelfde vraag met hetzelfde antwoord — dataverkeer, wachttijd, en een
# extra kans dat er precies daar iets wegvalt (waarna de gebruiker "je sessie is
# verlopen" te zien kreeg terwijl er niets verlopen was).
#
# De prijs: wie uitlogt of wiens token wordt ingetrokken, kan hooguit nog een
# minuut door. Dat is bewust. Alles wat geld of toegang raakt hangt niet aan dit
# antwoord maar aan `require_active_subscription`, en die kijkt wél elke keer.
_AUTH_GELDIG_SECONDEN = 60
_AUTH_MAX_ONTHOUDEN = 2000
_auth_cache: dict[str, tuple[float, object]] = {}


def _cache_sleutel(token: str) -> str:
    # Gehasht, zodat er geen bruikbaar inlogbewijs in een geheugendump of een
    # foutrapport belandt.
    return hashlib.sha256(token.encode()).hexdigest()


def _uit_cache(sleutel: str):
    gevonden = _auth_cache.get(sleutel)
    if not gevonden:
        return None
    verloopt, user = gevonden
    if verloopt < time.monotonic():
        _auth_cache.pop(sleutel, None)
        return None
    return user


def _in_cache(sleutel: str, user) -> None:
    # Geen slimme uitwerpregel: bij een volle cache gaat alles weg wat verlopen
    # is, en helpt dat niet, dan de hele cache. Hij is per definitie opnieuw op
    # te bouwen, dus dat kost één trage ronde en nooit een verkeerd antwoord.
    if len(_auth_cache) >= _AUTH_MAX_ONTHOUDEN:
        nu = time.monotonic()
        for k in [k for k, (v, _) in _auth_cache.items() if v < nu]:
            _auth_cache.pop(k, None)
        if len(_auth_cache) >= _AUTH_MAX_ONTHOUDEN:
            _auth_cache.clear()
    _auth_cache[sleutel] = (time.monotonic() + _AUTH_GELDIG_SECONDEN, user)


def vergeet_inlogbewijs(token: str = "") -> None:
    """Bij uitloggen of wachtwoordwijziging: meteen vergeten, niet pas na een
    minuut."""
    if token:
        _auth_cache.pop(_cache_sleutel(token.removeprefix("Bearer ").strip()), None)
    else:
        _auth_cache.clear()


async def get_current_user(authorization: str = Header(...)) -> str:
    user = await get_current_user_full(authorization)
    return user.id


async def get_current_user_full(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
    sleutel = _cache_sleutel(token)
    onthouden = _uit_cache(sleutel)
    if onthouden is not None:
        return onthouden
    try:
        # supabase-py's client is synchronous (blocking httpx.Client underneath).
        # Uvicorn runs a single worker/event loop here, so calling it directly
        # froze the ENTIRE process for every other in-flight request — including
        # unrelated ones like /health — for as long as this call took. Under any
        # concurrent load that queued up into multi-second, then 20s+, stalls
        # (visible as the climbing Response Time metric in Railway) and
        # occasionally a request got its connection cut mid-response. This
        # dependency runs on nearly every authenticated request, so offloading
        # it to a thread removes the single biggest source of that contention.
        res = await asyncio.to_thread(
            lambda: auth_met_herkansing(lambda: get_auth_db().auth.get_user(token)))
        if not res.user:
            raise HTTPException(status_code=401, detail="Your session expired — please sign in again")
        _in_cache(sleutel, res.user)
        return res.user
    except HTTPException:
        raise
    except AuthTijdelijkOnbereikbaar as e:
        # 503, geen 401. Dit draait op ZO GOED ALS ELK verzoek, en het dashboard
        # gooit je bij een 401 meteen naar het inlogscherm. Eén weggevallen
        # verbinding richting Supabase — iets wat hier volgens database.py
        # geregeld gebeurt — betekende dus: midden in je werk eruit gegooid, met
        # "je sessie is verlopen" terwijl er niets verlopen was. Precies wat
        # Egbert Brouwer meldde: "eerst een aantal keren uitgegooid vlak nadat ik
        # was ingelogd".
        logger.error("Kon het inlogbewijs niet controleren: %s", e)
        raise HTTPException(status_code=503,
                            detail="Connection hiccup — you're still signed in. Please try again in a moment.")
    except Exception:
        raise HTTPException(status_code=401, detail="Your session expired — please sign in again")


async def require_active_subscription(user=Depends(get_current_user_full)) -> str:
    """
    Gate for everything that creates value: crosslisting, publishing and the
    extension's job queue. Until now the paywall was a panel in the browser, so
    an expired account could keep working simply by not looking at it.

    Returns the user id, or raises 402 with a message the app shows verbatim.
    """
    from backend.services.billing import check_access

    verdict = await check_access(user.id, user.email)
    if verdict["allowed"]:
        return user.id

    if verdict["reason"] == "past_due":
        detail = "Your subscription is on hold because a payment failed. Update your payment details to restore access."
    elif verdict["reason"] in ("active_zonder_betaling", "period_ended"):
        detail = "We could not find an active payment for your account. Activate Pro to continue crosslisting."
    else:
        detail = "Your free trial has ended. Activate Pro to continue crosslisting."
    raise HTTPException(status_code=402, detail=detail)
