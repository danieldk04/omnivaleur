from fastapi import APIRouter, HTTPException, Header
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
        res = db.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {"email_redirect_to": "https://omnivaleur.com/"},
        })
        if res.user is None:
            raise HTTPException(status_code=400, detail="Registration failed")
        return {"ok": True, "message": "Account created. Check your email to confirm."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ResetRequest(BaseModel):
    email: str


@router.post("/forgot-password")
async def forgot_password(body: ResetRequest):
    db = get_db()
    try:
        db.auth.reset_password_for_email(
            body.email,
            options={"redirect_to": "https://omnivaleur.com/reset-password.html"}
        )
    except Exception:
        pass
    return {"ok": True, "message": "If this email is registered, you will receive a reset link."}


@router.post("/resend-confirmation")
async def resend_confirmation(body: ResetRequest):
    """Re-send the signup confirmation email. Best-effort: always returns ok so
    an unregistered/already-confirmed address can't be probed."""
    db = get_db()
    try:
        db.auth.resend({
            "type": "signup",
            "email": body.email,
            "options": {"email_redirect_to": "https://omnivaleur.com/"},
        })
    except Exception:
        pass
    return {"ok": True, "message": "If this email needs confirming, a new link is on its way."}


class PasswordUpdate(BaseModel):
    password: str


@router.post("/reset-password")
async def reset_password(body: PasswordUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = get_db()
    try:
        db.auth.set_session(token, "")
        db.auth.update_user({"password": body.password})
        return {"ok": True, "message": "Password updated."}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Password update failed. The link may have expired.")


@router.post("/login")
async def login(body: AuthRequest):
    db = get_db()
    try:
        res = db.auth.sign_in_with_password({"email": body.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {
            "ok": True,
            "access_token": res.session.access_token,
            "user": {"id": res.user.id, "email": res.user.email},
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")
