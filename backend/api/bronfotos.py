"""Bronfoto's die onze GitHub-taak ophaalde, hier afleveren.

Waarom dit bestaat staat bij photo_mirror.bronfotos_wachtrij. Alleen
.github/workflows/bronfotos.yml op main komt erin (services/github_oidc.py).
"""
from __future__ import annotations

import base64
import binascii
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from backend.services import github_oidc
from backend.services import photo_mirror as pm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intern/bronfotos", tags=["intern"])

PUBLIEK = "omnivaleur-bronfotos"
WORKFLOW = "bronfotos.yml"
MAX_FOTOS = 40
MAX_BYTES = 15 * 1024 * 1024


async def _github(authorization: str | None = Header(None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Geen bewijs van GitHub")
    try:
        return await github_oidc.controleer(token, PUBLIEK, WORKFLOW)
    except github_oidc.Geweigerd as e:
        logger.warning("bronfotos: verzoek geweigerd: %s", e)
        raise HTTPException(403, "Geweigerd") from e


class Foto(BaseModel):
    url: str
    type: str
    b64: str


class Aanlevering(BaseModel):
    user_id: str
    fotos: list[Foto]


@router.get("")
async def wachtrij(max_artikelen: int = 40, _=Depends(_github)) -> dict:
    return {"artikelen": await pm.bronfotos_wachtrij(min(max(max_artikelen, 1), 100))}


@router.post("/{item_id}")
async def aanleveren(item_id: str, body: Aanlevering, _=Depends(_github)) -> dict:
    fotos: dict = {}
    for f in body.fotos[:MAX_FOTOS]:
        try:
            data = base64.b64decode(f.b64, validate=True)
        except (binascii.Error, ValueError):
            continue
        if data and len(data) <= MAX_BYTES and f.type.lower().startswith("image/"):
            fotos[f.url] = (data, f.type.split(";")[0].strip().lower())
    if not fotos:
        raise HTTPException(422, "Geen bruikbare foto's")
    return await pm.aangeleverde_fotos_opslaan(body.user_id, item_id, fotos)
