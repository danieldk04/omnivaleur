from fastapi import Header, HTTPException
from backend.database import get_db


async def get_current_user(authorization: str = Header(...)) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Niet ingelogd")
    try:
        res = get_db().auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Sessie verlopen")
        return res.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Sessie verlopen")
