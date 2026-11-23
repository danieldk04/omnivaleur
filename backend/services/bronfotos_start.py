"""Start de GitHub-taak "Bronfoto's" zodra een artikel op zijn foto's wacht.

GitHub draait de geplande taak maar 3 tot 5 keer per dag (gemeten 15 tot 23-11),
terwijl een plaatsing hooguit 2 uur wacht (_FOTO_GEDULD in api/jobs.py). Daarom
start de server de taak zelf. Zonder GITHUB_DISPATCH_TOKEN (Railway-variabele,
fine-grained token met alleen Actions: read and write op deze repo) doet dit niets.
Een fout hier mag een publicatie nooit raken.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

REPO = "danieldk04/omnivaleur"
WORKFLOW = "bronfotos.yml"
MIN_TUSSENTIJD = 180.0  # seconden; de taak zelf draait ook maar één keer tegelijk

_laatste = 0.0


async def start_bronfotos() -> bool:
    global _laatste
    token = os.environ.get("GITHUB_DISPATCH_TOKEN", "").strip()
    if not token:
        return False
    nu = time.monotonic()
    if _laatste and nu - _laatste < MIN_TUSSENTIJD:
        return False
    _laatste = nu
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"},
                json={"ref": "main"})
        if r.status_code != 204:
            logger.warning(f"[bronfotos-start] GitHub gaf {r.status_code}")
            return False
        logger.info("[bronfotos-start] taak gestart")
        return True
    except Exception as e:  # nooit een publicatie breken
        logger.warning(f"[bronfotos-start] mislukt: {e}")
        return False
