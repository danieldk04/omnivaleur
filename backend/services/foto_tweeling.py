"""Hetzelfde stuk herkennen aan de foto, niet aan de titel.

WAAROM (19-11-2026, Esther, hetisvintastisch, 3eeceb51)
Esther importeerde haar Shopify-winkel terwijl ~180 van dezelfde stukken al via
Marktplaats bij ons stonden. De tweelingzoeker (taalmodel plus controle op
kleur, merk en prijs) vond er vrijwel geen: het model koppelde willekeurig
("eierdop" aan "Dralon deken") en de controle keurde de echte paren af
("lichtgrijs" tegen "grijs", webshopprijs anders dan Marktplaatsprijs). Alles
werd een tweede artikel, en een verkoop in haar webshop haalde de Marktplaats-
advertentie dus nergens weg; de nachtelijke herplaatsing zette hem zelfs opnieuw
online.

Een verkoper gebruikt overal dezelfde foto's. Gemeten op haar 188 paren: de
eerste foto van het Marktplaats-artikel en een foto van het Shopify-product
verschillen 0 tot 2 bits (64-bits verschilhash), terwijl verschillende stukken
ruim boven de 10 zitten. Dit is daarom een zeker signaal, zonder model en zonder
kosten.

Gebruik in imports._find_twins: een kandidaat met een vrijwel identieke foto als
een artikel op een ANDER kanaal wordt nooit stil een nieuw artikel; hij komt
onder "To check" met het artikel als voorstel (de regel dat een tweeling nooit
vanzelf wordt samengevoegd blijft staan).
"""
from __future__ import annotations

import asyncio
import io
import logging
from collections import OrderedDict

import httpx

logger = logging.getLogger(__name__)

MAX_VERSCHIL = 4          # bits van 64; gemeten paren 0-2, verschillende stukken ruim > 10
_TEGELIJK = 8
_CACHE: "OrderedDict[str, int | None]" = OrderedDict()
_CACHE_MAX = 20000


def verschilhash(data: bytes) -> int | None:
    """64-bits dHash van een plaatje (9x8 grijs, links tegen rechts)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("L").resize((9, 8), Image.LANCZOS)
    except Exception:  # noqa: BLE001 — een kapotte foto bewijst niets
        return None
    px = list(im.getdata())
    h = 0
    for rij in range(8):
        for kol in range(8):
            h = (h << 1) | (1 if px[rij * 9 + kol] > px[rij * 9 + kol + 1] else 0)
    return h


def verschil(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _klein(url: str) -> str:
    # Shopify's CDN levert op verzoek een kleine versie; scheelt 95% downloaden.
    if "cdn.shopify.com" in url:
        return url + ("&" if "?" in url else "?") + "width=256"
    return url


async def _hash_van(client: httpx.AsyncClient, url: str, rem: asyncio.Semaphore) -> int | None:
    if not url:
        return None
    if url in _CACHE:
        _CACHE.move_to_end(url)
        return _CACHE[url]
    async with rem:
        try:
            r = await client.get(_klein(url))
            h = verschilhash(r.content) if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            h = None
    _CACHE[url] = h
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return h


async def foto_tweelingen(kandidaten: list[dict], artikelen: list[dict],
                          tijdslimiet: float = 90.0) -> dict[str, str]:
    """kandidaat-id -> artikel-id voor vrijwel identieke foto's, alleen één-op-één.

    `kandidaten` dragen photo_urls of photo_url; `artikelen` dragen photo_urls.
    Per kant tellen de eerste twee foto's. Leeg bij een storing: dan geldt de
    oude weg, met een waarschuwing in het log zodat het opvalt.
    """
    def fotos(x: dict) -> list[str]:
        lijst = list(x.get("photo_urls") or [])
        if not lijst and x.get("photo_url"):
            lijst = [x["photo_url"]]
        return [u for u in lijst[:2] if isinstance(u, str) and u.startswith("http")]

    if not kandidaten or not artikelen:
        return {}
    rem = asyncio.Semaphore(_TEGELIJK)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            async def alle(rijen):
                return await asyncio.gather(*(
                    asyncio.gather(*(_hash_van(client, u, rem) for u in fotos(x))) for x in rijen))
            k_hash, a_hash = await asyncio.wait_for(
                asyncio.gather(alle(kandidaten), alle(artikelen)), timeout=tijdslimiet)
    except Exception as e:  # noqa: BLE001
        logger.warning("fototweeling: vergelijking niet gelukt (%s); alleen de oude tweelingzoeker", e)
        return {}

    treffers: dict[str, list[str]] = {}
    for k, kh in zip(kandidaten, k_hash):
        kh = [h for h in kh if h is not None]
        if not kh:
            continue
        for a, ah in zip(artikelen, a_hash):
            if any(verschil(x, y) <= MAX_VERSCHIL for x in kh for y in ah if y is not None):
                treffers.setdefault(k["id"], []).append(a["id"])
    per_artikel: dict[str, int] = {}
    for lijst in treffers.values():
        for a in set(lijst):
            per_artikel[a] = per_artikel.get(a, 0) + 1
    uit = {k: lijst[0] for k, lijst in treffers.items()
           if len(set(lijst)) == 1 and per_artikel[lijst[0]] == 1}
    if uit:
        logger.info("fototweeling: %d kandidaat(en) zijn op de foto hetzelfde stuk als een "
                    "bestaand artikel", len(uit))
    return uit
