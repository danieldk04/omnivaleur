"""
Copy photos from a marketplace CDN into our own Supabase Storage.

Imported listings used to keep the SOURCE url (e.g. images1.vinted.net). That
broke publishing in two ways, both confirmed live:

  * Vinted's CDN refuses a cross-origin fetch from marktplaats.nl, so the
    extension — which downloads from the marketplace page's origin — could never
    read those photos. The item published without a single image.
  * Those urls are signed and can expire, so even a working item can silently
    lose its photos later.

Mirroring at import time removes both. The backend has no CORS to satisfy and
the resulting url lives on our own public bucket, which every channel (and the
extension) can read.

Best-effort by design: a photo we can't copy keeps its original url, so an
import never loses an image just because the mirror failed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes

from backend.services.image_optimize import optimize_image
from backend.services.image_upload import upload_image

logger = logging.getLogger(__name__)

MAX_BYTES = 15 * 1024 * 1024          # skip anything absurd; listing photos are ~1 MB
MAX_CONCURRENCY = 3                    # polite to the source CDN, still quick
REQUEST_TIMEOUT = 30.0

# Hosts that already serve our own storage — mirroring those again would just
# duplicate bytes on every re-import.
_OWN_HOSTS = ("supabase.co", "supabase.in")

_EXT_BY_TYPE = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
    "image/webp": "webp", "image/gif": "gif", "image/heic": "heic",
    "image/heif": "heif", "image/bmp": "bmp",
}

# Vinted (and most CDNs) reject requests without a normal browser fingerprint.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def is_mirrored(url: str) -> bool:
    if not isinstance(url, str):
        return False
    from backend.services import r2_storage
    if r2_storage.is_configured() and url.startswith(r2_storage.public_base() + "/"):
        return True
    return any(h in url for h in _OWN_HOSTS)


async def mirror_photos_bulk(url_lists: list[list[str] | None], user_id: str) -> list[list[str]]:
    """Mirror several listings' photos at once, sharing ONE concurrency budget.

    Calling mirror_photos per candidate in a gather would multiply the limit by
    the batch size — 25 candidates would hammer the source CDN with 125 parallel
    downloads and invite rate limiting.
    """
    import asyncio as _asyncio
    sem = _asyncio.Semaphore(MAX_CONCURRENCY)
    return list(await _asyncio.gather(*(mirror_photos(u, user_id, _sem=sem) for u in url_lists)))


async def mirror_photos(urls: list[str] | None, user_id: str, _sem=None) -> list[str]:
    """Copy every remote photo into our bucket. Returns the urls to store.

    Order is preserved — the first photo is the listing's main image on several
    platforms, so shuffling here would change how items look.
    """
    if not urls:
        return []
    # Anything that isn't a downloadable http(s) url is passed through UNCHANGED
    # rather than filtered out. Dropping it would shorten the list and silently
    # delete a photo from the item — the one thing this function must never do.
    if not any(isinstance(u, str) and u.startswith(("http://", "https://")) for u in urls):
        return list(urls)

    import httpx

    sem = _sem or asyncio.Semaphore(MAX_CONCURRENCY)

    async def fetch_with_retry(client: "httpx.AsyncClient", url: str):
        """Transient network failures are the norm here, not the exception.
        Downloading a whole wardrobe hit '[Errno 35] Resource temporarily
        unavailable' on every photo of a 9-photo item while single-photo items
        sailed through — a local socket/DNS hiccup under concurrency, not the CDN
        refusing us. Without a retry those photos were written off as permanently
        unreachable and the item kept its dead urls."""
        last = None
        for attempt in range(3):
            try:
                return await client.get(url, headers=_HEADERS, follow_redirects=True)
            except Exception as e:  # noqa: BLE001
                last = e
                await asyncio.sleep(0.5 * (attempt + 1))
        raise last

    async def one(client: "httpx.AsyncClient", url) -> str:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return url
        if is_mirrored(url):
            return url
        async with sem:
            try:
                resp = await fetch_with_retry(client, url)
                if resp.status_code != 200:
                    logger.warning("photo mirror: %s returned HTTP %s", url[:120], resp.status_code)
                    return url
                data = source_bytes = resp.content
                if not data or len(data) > MAX_BYTES:
                    logger.warning("photo mirror: %s has unusable size %s", url[:120], len(data or b""))
                    return url

                content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    logger.warning("photo mirror: %s is not an image (%s)", url[:120], content_type)
                    return url

                ext = (_EXT_BY_TYPE.get(content_type)
                       or (mimetypes.guess_extension(content_type) or ".jpg").lstrip("."))
                # Store a sane size instead of whatever the CDN happened to
                # serve. Returns the original bytes if it can't do better, so a
                # photo is never lost here.
                data, ext = optimize_image(data, ext)
                # Content-addressed: re-importing the same listing, or two items
                # sharing a photo, reuses one object instead of growing the bucket
                # every time. Still namespaced per user, so nothing is shared
                # across accounts. The digest stays over the SOURCE bytes, so
                # re-importing the same listing keeps landing on the same path
                # even if the optimiser changes.
                digest = hashlib.sha256(source_bytes).hexdigest()[:32]
                path = f"{user_id}/imported/{digest}.{ext}"
                return await upload_image(data, path)
            except Exception as e:  # noqa: BLE001 - keep the original url, never fail the import
                logger.warning("photo mirror failed for %s: %s", url[:120], e)
                return url

    # Cap the connection pool as well as the semaphore: httpx otherwise opens a
    # fresh connection per request, which is what exhausted local sockets on a
    # multi-photo item.
    limits = httpx.Limits(max_connections=MAX_CONCURRENCY, max_keepalive_connections=MAX_CONCURRENCY)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, limits=limits) as client:
        return ontdubbel(list(await asyncio.gather(*(one(client, u) for u in urls))))


def ontdubbel(urls: list[str]) -> list[str]:
    """Dezelfde foto maar één keer, op de plek waar hij het eerst stond.

    WAAROM DIT HIER MOET (30-08-2026). De naam in onze eigen opslag is de
    vingerafdruk van de INHOUD (zie `digest` hierboven). Twee foto's die bij
    Marktplaats onder verschillende nummers staan maar dezelfde afbeelding zijn
    — een verkoper die dezelfde foto twee keer uploadde — komen hier dus als
    twee identieke adressen uit. Die gingen allebei mee naar het formulier, en
    dan staat dezelfde foto twee keer in de advertentie. Gemeld door Amanda:
    "Of plaatst de foto's dubbel". Gemeten op 30-08-2026: 71 artikelen over vier
    accounts hadden zo'n dubbele regel.

    Volgorde blijft heilig: de eerste foto is op elk platform de omslagfoto.
    """
    gezien: set[str] = set()
    uit: list[str] = []
    for u in urls:
        sleutel = u.split("?")[0] if isinstance(u, str) else repr(u)
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uit.append(u)
    return uit
