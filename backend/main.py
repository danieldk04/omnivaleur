import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
from backend.api import items, listings, platforms, webhooks, jobs, uploads, shopify, auth, billing, imports, content, notifications
from backend.scheduler import start_scheduler, stop_scheduler

FRONTEND = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
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
