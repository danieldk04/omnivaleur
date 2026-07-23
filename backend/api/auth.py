import asyncio
import re
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from backend.database import get_db
from backend.api.deps import get_current_user_full

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    refresh_token: str = ""


@router.post("/reset-password")
async def reset_password(body: PasswordUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    db = get_db()
    try:
        # gotrue's set_session raises if the refresh token is empty, so pass the
        # real one from the recovery link hash. It travels alongside the access
        # token in the redirect fragment.
        db.auth.set_session(token, body.refresh_token)
        db.auth.update_user({"password": body.password})
        return {"ok": True, "message": "Password updated."}
    except Exception:
        raise HTTPException(status_code=400, detail="Password update failed. The link may have expired.")


@router.post("/login")
async def login(body: AuthRequest):
    db = get_db()
    try:
        # See get_current_user_full in deps.py: supabase-py is a blocking client,
        # so this call ran synchronously on the single event loop and could stall
        # every other in-flight request (login being the ONE endpoint every
        # anonymous visitor hits made it especially visible as a hang/empty
        # response under load).
        res = await asyncio.to_thread(
            db.auth.sign_in_with_password,
            {"email": body.email, "password": body.password},
        )
        if res.user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {
            "ok": True,
            "access_token": res.session.access_token,
            "user": {"id": res.user.id, "email": res.user.email},
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")


class ChangeEmailRequest(BaseModel):
    new_email: str
    password: str


@router.post("/change-email")
async def change_email(body: ChangeEmailRequest, user=Depends(get_current_user_full)):
    """Change the logged-in user's account email. Requires the current password
    (so a hijacked session alone can't move the account), then updates the email
    via the Supabase admin API and marks it confirmed so the user can log in with
    it right away."""
    new_email = (body.new_email or "").strip().lower()
    if not _EMAIL_RE.match(new_email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if new_email == (user.email or "").lower():
        raise HTTPException(status_code=400, detail="That's already your email")

    db = get_db()
    # Verify the current password against the account's current email.
    try:
        res = db.auth.sign_in_with_password({"email": user.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=401, detail="Wrong password")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Wrong password")

    try:
        db.auth.admin.update_user_by_id(user.id, {"email": new_email, "email_confirm": True})
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "registered" in msg or "exists" in msg:
            raise HTTPException(status_code=409, detail="That email is already in use by another account")
        raise HTTPException(status_code=400, detail=f"Could not change email: {e}")

    return {"ok": True, "email": new_email, "message": "Email updated. Use it next time you log in."}


class ChangeEmailRequest(BaseModel):
    new_email: str
    password: str


@router.post("/change-email")
async def change_email(body: ChangeEmailRequest, user=Depends(get_current_user_full)):
    """Change the logged-in user's account email. Requires the current password
    (so a hijacked session alone can't move the account), then updates the email
    via the Supabase admin API and marks it confirmed so the user can log in with
    it right away."""
    new_email = (body.new_email or "").strip().lower()
    if not _EMAIL_RE.match(new_email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if new_email == (user.email or "").lower():
        raise HTTPException(status_code=400, detail="That's already your email")

    db = get_db()
    # Verify the current password against the account's current email.
    try:
        res = db.auth.sign_in_with_password({"email": user.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=401, detail="Wrong password")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Wrong password")

    try:
        db.auth.admin.update_user_by_id(user.id, {"email": new_email, "email_confirm": True})
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "registered" in msg or "exists" in msg:
            raise HTTPException(status_code=409, detail="That email is already in use by another account")
        raise HTTPException(status_code=400, detail=f"Could not change email: {e}")

    return {"ok": True, "email": new_email, "message": "Email updated. Use it next time you log in."}
