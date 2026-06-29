from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(body: AuthRequest):
    db = get_db()
    try:
        res = db.auth.sign_up({"email": body.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=400, detail="Registratie mislukt")
        return {"ok": True, "message": "Account aangemaakt. Check je e-mail om te bevestigen."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(body: AuthRequest):
    db = get_db()
    try:
        res = db.auth.sign_in_with_password({"email": body.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=401, detail="Onjuiste inloggegevens")
        return {
            "ok": True,
            "access_token": res.session.access_token,
            "user": {"id": res.user.id, "email": res.user.email},
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Onjuiste inloggegevens")
