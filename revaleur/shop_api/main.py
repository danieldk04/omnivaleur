"""Revaleur-webshop API. Start: uvicorn revaleur.shop_api.main:app (aparte Railway-dienst, niet die van Omnivaleur)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .checkout import router
from .config import settings

app = FastAPI(title="Revaleur shop API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.site_url, "https://www.revaleur.com", *[o for o in settings.extra_origins.split(",") if o]],
    allow_origin_regex=r"https://revaleur[a-z0-9-]*\.pages\.dev",
    allow_methods=["POST", "GET"], allow_headers=["*"],
)
app.include_router(router, prefix="/api")
