import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import asyncio
from backend.api import items, listings, platforms, webhooks, jobs, uploads, shopify, auth, billing, imports, content, notifications
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
            "owner_email": _s.owner_email,
        },
    }


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


@app.get("/marketplaces")
async def marketplaces_page():
    return FileResponse(FRONTEND / "marketplaces.html")


# Serve frontend static assets (CSS, images, JS) — must come last
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
