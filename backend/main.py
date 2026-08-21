import logging
import os
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import asyncio
from backend.api import items, listings, platforms, webhooks, jobs, uploads, shopify, auth, billing, imports, content, notifications, beheer
from backend.scheduler import start_scheduler, stop_scheduler

FRONTEND = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Elk geauthenticeerd verzoek doet zijn inlogcontrole via asyncio.to_thread.
    # Die gebruikt standaard maar (aantal cpu's + 4) threads, en op een kleine
    # container zijn dat er een handvol. Zaten die vol met trage Supabase-
    # aanroepen, dan bleef een verzoek wachten vóórdat het de route bereikte —
    # de gateway gaf dan 502 terwijl de server zelf "gezond" leek. Ruim genoeg
    # threads dus: ze staan toch bijna altijd te wachten op het netwerk.
    asyncio.get_running_loop().set_default_executor(
        ThreadPoolExecutor(max_workers=48, thread_name_prefix="supabase")
    )
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Omnivaleur",
    description="Cross-listing tool for European second-hand marketplaces",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://omnivaleur.com",
        "https://www.omnivaleur.com",
        "https://omnivaleur.com",
        "https://api.omnivaleur.com",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def canonical_host(request: Request, call_next):
    """www.omnivaleur.com hoort door te sturen naar omnivaleur.com.

    Zonder deze redirect serveerde de www-variant gewoon de hele site met status
    200. De canonical-tag ving dat grotendeels op, maar Search Console telt het
    als een tweede property: bezoekers en zoekwoorden worden dan over twee
    domeinen verdeeld en linkwaarde lekt weg.
    """
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if host == "www.omnivaleur.com":
        # Scheme hard op https: achter de proxy komt het verzoek als http binnen,
        # dus zonder dit stuurde de redirect naar http:// en volgde er een tweede hop.
        target = request.url.replace(netloc="omnivaleur.com", scheme="https")
        return RedirectResponse(str(target), status_code=301)
    return await call_next(request)


app.include_router(items.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
app.include_router(platforms.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(shopify.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(content.router)
app.include_router(beheer.router)


def _supabase_key_role() -> str:
    """De rol uit de Supabase-sleutel ('anon' of 'service_role'), of 'onbekend'.

    Een JWT draagt zijn claims onversleuteld mee; alleen de handtekening is
    geheim. We lezen dus niets gevoeligs — maar het verschil bepaalt wel of de
    server e-mailadressen mag opzoeken, en dus of de proefherinneringen überhaupt
    verstuurd kunnen worden.
    """
    import base64
    import json as _json
    from backend.config import settings as _s
    try:
        payload = _s.supabase_key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return _json.loads(base64.urlsafe_b64decode(payload)).get("role") or "onbekend"
    except Exception:
        return "onbekend"


def _r2_configured() -> bool:
    """Pakt de server de R2-instellingen op? Nooit de sleutels zelf tonen."""
    try:
        from backend.services import r2_storage
        return r2_storage.is_configured()
    except Exception:
        return False


@app.get("/health")
async def health():
    # Alleen ja/nee per instelling, nooit de waarde zelf. Dagen zoekwerk gingen op
    # aan gokken of een sleutel wel bij de live server aankwam.
    from backend.config import settings as _s
    import os
    return {
        "status": "ok",
        "service": "omnivaleur",
        # Welke versie draait er nu écht? Zonder dit was er geen manier om te
        # zien of een net gepushte fix al live stond.
        "commit": (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "unknown")[:8],
        "config": {
            "stripe_secret_key": bool(_s.stripe_secret_key),
            "stripe_price_id": bool(_s.stripe_price_id),
            "stripe_webhook_secret": bool(_s.stripe_webhook_secret),
            "supabase_key": bool(_s.supabase_key),
            # Niet óf de sleutel er is, maar wélke. Met een anon-sleutel werkt
            # bijna alles gewoon (RLS staat uit op de meeste tabellen), maar het
            # opzoeken van een e-mailadres mag niet — en dan verdwijnen alle
            # herinneringsmails geruisloos. Dat is precies wat er gebeurd is.
            # De rol staat onversleuteld in de sleutel zelf; dit lekt niets.
            "supabase_key_role": _supabase_key_role(),
            "anthropic_api_key": bool(_s.anthropic_api_key),
            # Staat dit op false, dan schrijft de server nieuwe foto's nog steeds
            # naar Supabase Storage en loopt die bucket dus gewoon weer vol. Dat
            # is van buitenaf verder niet te zien, vandaar hier.
            "r2_photo_storage": _r2_configured(),
            # De koude-mailmachine. Draait alleen als leadgen_tick aan staat, en
            # kan alleen versturen als Resend er is (Railway blokkeert SMTP) en
            # alleen concepten klaarzetten als de postbus-gegevens er zijn.
            # Zonder deze regels moest je raden waarom er niets gebeurde.
            "leadgen_tick": bool(str(_s.leadgen_tick or "").strip() in ("1", "true", "True")),
            "leadgen_resend": bool(_s.resend_api_key),
            "leadgen_mailbox": bool(os.environ.get("MAIL_USER") and os.environ.get("MAIL_PASS")),
            # Shopify koppelen faalde bij een klant met "deze installatielink kan
            # niet worden gebruikt". Zonder deze regels was niet te zien of de
            # sleutels er überhaupt zijn, of dat het aan de app-instelling bij
            # Shopify zelf ligt.
            "shopify_client_id": bool(_s.shopify_client_id),
            "shopify_client_secret": bool(_s.shopify_client_secret),
            "owner_email": _s.owner_email,
        },
    }


@app.get("/health/resend")
def health_resend():
    """Welke domeinen mag Resend versturen?

    De koude mail gaat vanaf daniel@omnivaleur.nl. Staat dat domein niet als
    geverifieerd in Resend, dan weigert Resend elke mail en verstuurt de machine
    stilletjes niets. Dat was van buitenaf niet te zien; nu wel. Geeft alleen
    domeinnamen terug — die staan toch al in DNS, er lekt hier niets.
    """
    import httpx
    from backend.config import settings as _s
    if not _s.resend_api_key:
        return {"resend": "geen sleutel"}
    try:
        r = httpx.get("https://api.resend.com/domains",
                      headers={"Authorization": f"Bearer {_s.resend_api_key}"},
                      timeout=15)
        if r.status_code >= 300:
            return {"resend": f"fout {r.status_code}"}
        return {"domeinen": [{"naam": d.get("name"), "status": d.get("status")}
                             for d in (r.json().get("data") or [])]}
    except Exception as e:  # noqa: BLE001
        return {"resend": f"niet bereikbaar: {e}"}


@app.get("/privacy")
async def privacy():
    return FileResponse(FRONTEND / "privacy.html")


@app.get("/terms")
async def terms():
    return FileResponse(FRONTEND / "terms.html")


@app.get("/login")
async def login_page():
    return FileResponse(FRONTEND / "login.html")


@app.get("/register")
async def register_page():
    return FileResponse(FRONTEND / "register.html")


@app.get("/forgot-password")
async def forgot_password_page():
    return FileResponse(FRONTEND / "forgot-password.html")


@app.get("/reset-password")
async def reset_password_page():
    return FileResponse(FRONTEND / "reset-password.html")


@app.get("/app")
async def app_page():
    return FileResponse(FRONTEND / "app.html")


@app.get("/beheer")
async def beheer_page():
    """Het beheerscherm. Bewust een eigen adres en niet een tabblad in de app:
    het staat vol klantgegevens en hoort niet in hetzelfde scherm te zitten dat
    ook gewone gebruikers openen."""
    return FileResponse(FRONTEND / "beheer.html")


@app.get("/marketplaces")
async def marketplaces_page():
    return FileResponse(FRONTEND / "marketplaces.html")


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """Een dode link gaf kale JSON te zien: {"detail":"Not Found"}.

    De statuscode klopte, dus indexering ging goed, maar de bezoeker kreeg geen
    enkele weg terug de site op. API-verzoeken houden hun JSON — alleen wie een
    pagina opvraagt krijgt de echte 404-pagina.
    """
    wants_html = "text/html" in (request.headers.get("accept") or "")
    is_api = request.url.path.startswith("/api") or request.url.path == "/health"
    if exc.status_code == 404 and wants_html and not is_api:
        # Bewust niet "404.html": StaticFiles(html=True) serveert een bestand met
        # díe naam automatisch bij élke misser, ook op /api — dan kregen de app en
        # de extensie HTML terug waar ze JSON verwachten.
        return FileResponse(FRONTEND / "not-found.html", status_code=404)
    return await http_exception_handler(request, exc)


# Serve frontend static assets (CSS, images, JS) — must come last
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
