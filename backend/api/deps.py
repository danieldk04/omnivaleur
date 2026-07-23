import asyncio
from fastapi import Header, HTTPException
from backend.database import get_db


async def get_current_user(authorization: str = Header(...)) -> str:
    user = await get_current_user_full(authorization)
    return user.id


async def get_current_user_full(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Niet ingelogd")
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
        res = await asyncio.to_thread(get_db().auth.get_user, token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Sessie verlopen")
        return res.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Sessie verlopen")
