"""Is dit verzoek echt van onze eigen GitHub-taak? Zonder gedeelde sleutel.

GitHub geeft een taak die `id-token: write` heeft een kortlevend, door GitHub
ondertekend bewijs (OIDC). Daarin staat welke repo, welke tak, welk
workflowbestand en welke aanleiding. Wij controleren de handtekening met de
openbare sleutels van GitHub en eisen precies onze repo, main, ons bestand en
een geplande of handmatige start. Een pull request van buiten krijgt zo'n bewijs
niet, en een ander workflowbestand of een andere tak valt af op de inhoud.

Gebruikt door api/bronfotos.py (De Juiste Toon, 15-10-2026).
"""
from __future__ import annotations

import time

import httpx
from jose import jwt

UITGEVER = "https://token.actions.githubusercontent.com"
SLEUTELS_URL = UITGEVER + "/.well-known/jwks"
REPO = "danieldk04/omnivaleur"
AANLEIDINGEN = ("schedule", "workflow_dispatch")

_cache: dict = {"sleutels": None, "t": 0.0}


class Geweigerd(Exception):
    pass


async def _sleutels(vers: bool = False) -> dict:
    if vers or not _cache["sleutels"] or time.time() - _cache["t"] > 3600:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(SLEUTELS_URL)
            r.raise_for_status()
            _cache["sleutels"], _cache["t"] = r.json(), time.time()
    return _cache["sleutels"]


async def controleer(token: str, publiek: str, workflow: str) -> dict:
    """Geeft de inhoud van het bewijs terug, of gooit Geweigerd."""
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except Exception as e:  # noqa: BLE001
        raise Geweigerd(f"geen geldig bewijs: {e}") from e
    sleutels = await _sleutels()
    if kid and not any(k.get("kid") == kid for k in sleutels.get("keys", [])):
        sleutels = await _sleutels(vers=True)   # GitHub wisselde zijn sleutels
    try:
        inhoud = jwt.decode(token, sleutels, algorithms=["RS256"], audience=publiek, issuer=UITGEVER)
    except Exception as e:  # noqa: BLE001
        raise Geweigerd(f"handtekening of geldigheid klopt niet: {e}") from e
    verwacht = {
        "repository": REPO,
        "ref": "refs/heads/main",
        "workflow_ref": f"{REPO}/.github/workflows/{workflow}@refs/heads/main",
    }
    for veld, waarde in verwacht.items():
        if inhoud.get(veld) != waarde:
            raise Geweigerd(f"{veld} is {inhoud.get(veld)!r}")
    if inhoud.get("event_name") not in AANLEIDINGEN:
        raise Geweigerd(f"aanleiding {inhoud.get('event_name')!r}")
    return inhoud
