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
        res = get_db().auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Sessie verlopen")
        return res.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Sessie verlopen")
