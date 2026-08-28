import asyncio
import logging

from fastapi import Depends, Header, HTTPException
from backend.database import (AuthTijdelijkOnbereikbaar, auth_met_herkansing,
                               get_auth_db, get_db)

logger = logging.getLogger(__name__)


async def get_current_user(authorization: str = Header(...)) -> str:
    user = await get_current_user_full(authorization)
    return user.id


async def get_current_user_full(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in")
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
