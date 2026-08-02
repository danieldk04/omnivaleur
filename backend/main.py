import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import threading
import time
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


# ── Tijdelijk meetpunt ───────────────────────────────────────────────────────
# Storingen op de server zijn tot nu toe onzichtbaar: de logs zijn niet van
# buitenaf te lezen, dus bij een 502 was er niets om op af te gaan. Dit houdt de
# laatste honderd verzoeken bij — alleen methode, route, status en duur, geen
# inhoud, geen tokens, geen id's — plus hoe druk de server het heeft. Zo is
# achteraf te zien of een verzoek de server überhaupt bereikte en waar de tijd
# bleef.
from backend.diag import RECENT as _RECENT, ERRORS as _ERRORS  # noqa: E402


def _route_of(path: str) -> str:
    """Route zonder id's, zodat hier geen gegevens van gebruikers in belanden."""
    delen = [d for d in path.split("/") if d]
    schoon = ["{id}" if (len(d) > 20 or d.isdigit()) else d for d in delen]
    return "/" + "/".join(schoon)


@app.middleware("http")
async def _trace_requests(request, call_next):
    entry = {
        "op": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "methode": request.method,
        "route": _route_of(request.url.path),
        "status": "BEZIG",
        "ms": None,
    }
    _RECENT.append(entry)
    start = time.monotonic()
    try:
        response = await call_next(request)
        entry["status"] = response.status_code
        return response
    except Exception as e:  # noqa: BLE001 - alleen vastleggen, dan doorgooien
        entry["status"] = "CRASH"
        entry["fout"] = f"{type(e).__name__}: {e}"[:300]
        raise
    finally:
        entry["ms"] = round((time.monotonic() - start) * 1000)


@app.get("/__diag/recent")
async def _diag_recent():
    # Loop-vertraging: hoe lang een taakje dat direct aan de beurt zou moeten
    # zijn, moet wachten. Alles boven een paar honderd ms betekent dat de server
    # geblokkeerd wordt door werk dat niet op de gedeelde lijn thuishoort.
    t = time.monotonic()
    await asyncio.sleep(0)
    lag_ms = round((time.monotonic() - t) * 1000, 1)
    loop = asyncio.get_running_loop()
    ex = getattr(loop, "_default_executor", None)
    return {
        "loop_vertraging_ms": lag_ms,
        "threads_actief": threading.active_count(),
        "thread_namen": sorted({t.name.split("_")[0] for t in threading.enumerate()}),
        "executor_max": getattr(ex, "_max_workers", None),
        "database_fouten": list(_ERRORS),
        "openstaand": [e for e in _RECENT if e["status"] == "BEZIG"],
        "laatste": list(_RECENT)[-40:],
    }


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
    return {"status": "ok", "service": "omnivaleur"}


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
