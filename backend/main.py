import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.api import items, listings, platforms, webhooks, jobs, uploads, shopify, auth
from backend.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="CrossList EU",
    description="Crosslisting tool voor Europese tweedehands marktplaatsen",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "crosslist-eu"}
