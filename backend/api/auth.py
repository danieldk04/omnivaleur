import asyncio
import logging
import re
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from backend.database import (AuthTijdelijkOnbereikbaar, auth_met_herkansing,
                               get_admin_db, get_db, verse_auth_client)
from backend.api.deps import get_current_user_full, vergeet_inlogbewijs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(body: AuthRequest):
    db = get_db()
    try:
        res = verse_auth_client().auth.sign_up({
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
        verse_auth_client().auth.reset_password_for_email(
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
        verse_auth_client().auth.resend({
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
        #
        # LET OP — verse_auth_client(), niet de gedeelde verbinding.
        # `update_user` schrijft het wachtwoord naar de sessie die IN DE CLIENT
        # staat, niet naar de gebruiker die dit verzoek doet. Op een gedeelde
        # verbinding zette elke inlog of tokenvernieuwing van een willekeurige
        # andere klant daar een andere sessie neer, en belandde dit wachtwoord
        # dus op het account van die vreemde. Zie verse_auth_client() in
        # database.py.
        auth_db = verse_auth_client()
        auth_db.auth.set_session(token, body.refresh_token)
        auth_db.auth.update_user({"password": body.password})
        # Het inlogbewijs wordt een minuut onthouden (zie deps.py). Na een
        # wachtwoordwijziging mag dat niet blijven staan.
        vergeet_inlogbewijs(token)
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
        # verse_auth_client(): inloggen laat een sessie achter in de client.
        # Op een gedeelde verbinding werd die sessie het doelwit van andermans
        # wachtwoordwijziging. Zie verse_auth_client() in database.py.
        res = await asyncio.to_thread(
            lambda: auth_met_herkansing(
                lambda: verse_auth_client().auth.sign_in_with_password(
                    {"email": body.email, "password": body.password})
            )
        )
        if res.user is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {
            "ok": True,
            "access_token": res.session.access_token,
            # The extension caches this and mints fresh access tokens on its own
            # via /auth/refresh, so background jobs (sold-detector, delete) stop
            # dying with "Sessie verlopen" when the ~1h access token expires and
            # no dashboard tab is open to re-push one.
            "refresh_token": res.session.refresh_token,
            "user": {"id": res.user.id, "email": res.user.email},
        }
    except HTTPException:
        raise
    except AuthTijdelijkOnbereikbaar as e:
        # De verbinding met Supabase viel weg, ook na herkansen. Dit als
        # "verkeerd wachtwoord" tonen is precies wat Egbert Brouwer op 28-08-2026
        # zijn ochtend kostte: hij typte het goede wachtwoord en las dat het fout
        # was.
        logger.error("Inloggen onbereikbaar voor %s: %s", body.email, e)
        raise HTTPException(
            status_code=503,
            detail="We couldn't reach the sign-in service. Your password is fine — please try again in a moment.",
        )
    except Exception as e:
        # Niet elke mislukte inlog is een verkeerd wachtwoord. Stond hier alles
        # onder één noemer, dan zag de verkoper "Invalid email or password"
        # terwijl Supabase in werkelijkheid "te veel pogingen" of "e-mailadres
        # nog niet bevestigd" zei — en dan gaat hij zijn wachtwoord opnieuw
        # proberen, wat het alleen erger maakt. Nu staat de echte reden in het
        # serverlogboek en krijgt hij het juiste antwoord te zien.
        melding = str(e)
        logger.warning("Inloggen mislukt voor %s: %s", body.email, melding)
        laag = melding.lower()
        if "rate limit" in laag or "too many" in laag or "429" in laag:
            raise HTTPException(
                status_code=429,
                detail="Too many sign-in attempts. Please wait a few minutes and try again.",
            )
        if "not confirmed" in laag or "email_not_confirmed" in laag:
            raise HTTPException(
                status_code=403,
                detail="Your email address hasn't been confirmed yet. Check your inbox for the confirmation link.",
            )
        if "invalid login credentials" not in laag and "invalid" not in laag:
            # Iets anders ging stuk (verbinding, Supabase zelf). Dat is geen
            # wachtwoordprobleem en moet niet zo klinken.
            raise HTTPException(
                status_code=503,
                detail="We couldn't reach the sign-in service. Your password is fine — please try again in a moment.",
            )
        raise HTTPException(status_code=401, detail="Invalid email or password")


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    """
    Exchange a Supabase refresh token for a fresh access token. Used by the
    browser extension so its long-running background work keeps a valid token
    without the dashboard having to be open. Keeps the Supabase anon key on the
    server rather than shipping it into the extension.
    """
    if not (body.refresh_token or "").strip():
        raise HTTPException(status_code=401, detail="Your session expired — please sign in again")
    db = get_db()
    try:
        # Ook dit zet een sessie op de client waarop het gebeurt. Elke extensie
        # ververst zelf, dus dit is verreweg de drukste sessie-schrijver van de
        # hele server — precies wat de gedeelde verbinding onbruikbaar maakte.
        res = await asyncio.to_thread(
            lambda: auth_met_herkansing(
                lambda: verse_auth_client().auth.refresh_session(body.refresh_token))
        )
        if not res.session:
            raise HTTPException(status_code=401, detail="Your session expired — please sign in again")
        return {
            "ok": True,
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }
    except HTTPException:
        raise
    except AuthTijdelijkOnbereikbaar as e:
        # Géén 401. Op een 401 gooit het dashboard de verkoper eruit en wist de
        # extensie haar inlogbewijs — voor iets wat alleen een hik in de
        # verbinding was.
        logger.error("Tokenvernieuwing onbereikbaar: %s", e)
        raise HTTPException(status_code=503, detail="Connection hiccup — please try again in a moment.")
    except Exception:
        raise HTTPException(status_code=401, detail="Your session expired — please sign in again")


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
        res = verse_auth_client().auth.sign_in_with_password({"email": user.email, "password": body.password})
        if res.user is None:
            raise HTTPException(status_code=401, detail="Wrong password")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Wrong password")

    try:
        # Bewust get_admin_db(): een regel hierboven loggen we de gebruiker in om
        # zijn wachtwoord te controleren, en dat maakt de client waarop dat gebeurt
        # tot díé gebruiker. Op dezelfde client zou deze beheerdersactie dus altijd
        # "User not allowed" geven — daarom heeft e-mail wijzigen nooit gewerkt.
        get_admin_db().auth.admin.update_user_by_id(user.id, {"email": new_email, "email_confirm": True})
        # Het onthouden inlogbewijs draagt het OUDE e-mailadres bij zich, en
        # daar hangt de abonnementscontrole aan. Meteen vergeten dus.
        vergeet_inlogbewijs()
    except Exception as e:
        msg = str(e).lower()
        if "already" in msg or "registered" in msg or "exists" in msg:
            raise HTTPException(status_code=409, detail="That email is already in use by another account")
        raise HTTPException(status_code=400, detail=f"Could not change email: {e}")

    return {"ok": True, "email": new_email, "message": "Email updated. Use it next time you log in."}
