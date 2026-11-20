"""Achtergrond van een productfoto verwijderen via Modal (20-11-2026).

De foto gaat naar onze eigen poort bij Modal (T4-videokaart, BiRefNet lite, MIT),
en komt terug als JPEG op wit. Kosten worden in vier lagen begrensd, zodat een
klant nooit op Daniels portemonnee kan lopen:

  1. maandplafond per klant (ai_quota.PLAFOND["achtergronden"]);
  2. een dagplafond voor ALLE klanten samen (DAGPLAFOND hieronder);
  3. max_containers=2 in het Modal-script;
  4. een uitgavenlimiet in het Modal-dashboard (usage limit, spend limit $0).

Bij twijfel NEE: is de poort niet ingesteld, de dag vol of het antwoord geen echte
foto, dan blijft de originele foto gewoon staan en meldt de knop "tijdelijk niet
beschikbaar".
"""
from __future__ import annotations

import io
import logging
import re
import threading
from datetime import datetime, timezone

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

DAGPLAFOND = 600          # foto's per dag voor iedereen samen
MAX_PER_KEER = 10         # foto's per opdracht
MAX_BYTES = 12 * 1024 * 1024
_slot = threading.Lock()
_dag = {"dag": "", "n": 0}


STANDAARD_KLEUR = "#ffffff"


def geldige_kleur(kleur) -> bool:
    return isinstance(kleur, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", kleur) is not None


class NietBeschikbaar(Exception):
    """De dienst is niet ingesteld, de dag is vol of Modal antwoordde niet."""


def ingesteld() -> bool:
    return bool(settings.achtergrond_url and settings.achtergrond_sleutel)


def _vandaag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def dag_ruimte(n: int = 1) -> bool:
    with _slot:
        if _dag["dag"] != _vandaag():
            _dag["dag"], _dag["n"] = _vandaag(), 0
        return _dag["n"] + n <= DAGPLAFOND


def dag_tel(n: int = 1) -> None:
    with _slot:
        if _dag["dag"] != _vandaag():
            _dag["dag"], _dag["n"] = _vandaag(), 0
        _dag["n"] += n


def is_echte_jpeg(data: bytes) -> bool:
    """Alleen een leesbare afbeelding van redelijke grootte telt als antwoord."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.verify()
        return im.format == "JPEG" and im.width >= 64 and im.height >= 64
    except Exception:  # noqa: BLE001
        return False


def knip(foto: bytes, kleur: str = STANDAARD_KLEUR, client: httpx.Client | None = None) -> bytes:
    """Blokkerend: gebruik via asyncio.to_thread. Een tweede poging vangt een koude start."""
    if not ingesteld():
        raise NietBeschikbaar("niet ingesteld")
    if not geldige_kleur(kleur):
        raise ValueError("ongeldige kleur")
    if not foto or len(foto) > MAX_BYTES:
        raise ValueError("foto te groot of leeg")
    if not dag_ruimte():
        raise NietBeschikbaar("dagplafond bereikt")
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(150.0, connect=15.0))
    try:
        laatste = None
        for poging in range(2):
            dag_tel()  # elke aanroep telt, ook een mislukte: die kost ook rekentijd
            try:
                r = client.post(settings.achtergrond_url, content=foto,
                                headers={"x-sleutel": settings.achtergrond_sleutel,
                                         "x-kleur": kleur,
                                         "content-type": "application/octet-stream"})
            except httpx.HTTPError as e:
                laatste = e
                continue
            if r.status_code == 200 and is_echte_jpeg(r.content):
                return r.content
            laatste = RuntimeError(f"status {r.status_code}")
            if r.status_code in (401, 413, 415):   # opnieuw proberen verandert niets
                break
        raise NietBeschikbaar(str(laatste))
    finally:
        if own:
            client.close()
