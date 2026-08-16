"""Cloudflare R2 as the home for listing photos.

Supabase Storage was never the right place for these. The free plan allows 1 GB
and serving a photo counts as egress; 3400 listing photos put the bucket at
346% and the egress meter over its limit as well. R2 gives 10 GB and charges
nothing for traffic, which removes both ceilings at once.

R2 speaks the S3 protocol, so this is a thin wrapper around boto3 with the
sharp edges handled:

  * NOT CONFIGURED IS A VALID STATE. With no credentials this module reports
    is_configured() == False and every caller falls back to Supabase exactly as
    before. That is what makes the switch reversible: empty the three settings
    and the app is back on its old storage without a deploy.
  * Photos are read by browsers, by the extension (from a marketplace page's
    origin) and by marketplace servers, so objects are public and the bucket
    needs a permissive CORS rule. ensure_cors() sets it.
  * The public url comes from our own domain (img.omnivaleur.com), never the
    r2.dev address — Cloudflare throttles that one and forbids it in production.
"""
from __future__ import annotations

import logging
import mimetypes
import threading

from backend.config import settings

logger = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()

_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "heic": "image/heic",
    "heif": "image/heif", "bmp": "image/bmp",
}

# A year: these objects are content-addressed, so a given url never changes
# content and every layer in between may cache it forever.
CACHE_CONTROL = "public, max-age=31536000, immutable"


def is_configured() -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
        and settings.r2_public_base_url
    )


def public_base() -> str:
    return settings.r2_public_base_url.rstrip("/")


def get_client():
    """One shared S3 client. boto3 clients are thread-safe."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import boto3
                from botocore.config import Config

                _client = boto3.client(
                    "s3",
                    endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
                    aws_access_key_id=settings.r2_access_key_id,
                    aws_secret_access_key=settings.r2_secret_access_key,
                    region_name="auto",
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
    return _client


def content_type_for(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _CONTENT_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def url_for(path: str) -> str:
    return f"{public_base()}/{path.lstrip('/')}"


def path_from_url(url: str) -> str | None:
    """Turn one of OUR public urls back into its object path, or None.

    Anything we are not certain about returns None — callers use this to decide
    what to delete, so "not sure" must always mean "leave it alone".
    """
    if not isinstance(url, str) or not is_configured():
        return None
    base = public_base() + "/"
    if not url.startswith(base):
        return None
    path = url[len(base):].split("?", 1)[0].split("#", 1)[0].strip("/")
    if not path or ".." in path:
        return None
    return path


def upload(data: bytes, path: str) -> str:
    """Store the bytes and return the public url. Raises on failure."""
    get_client().put_object(
        Bucket=settings.r2_bucket,
        Key=path,
        Body=data,
        ContentType=content_type_for(path),
        CacheControl=CACHE_CONTROL,
    )
    return url_for(path)


def delete(paths: list[str]) -> int:
    """Remove objects. Best-effort: logs and returns 0 rather than raising."""
    paths = [p for p in paths if p]
    if not paths:
        return 0
    try:
        removed = 0
        for i in range(0, len(paths), 1000):  # S3 caps a batch delete at 1000
            batch = paths[i:i + 1000]
            get_client().delete_objects(
                Bucket=settings.r2_bucket,
                Delete={"Objects": [{"Key": p} for p in batch], "Quiet": True},
            )
            removed += len(batch)
        return removed
    except Exception as e:  # noqa: BLE001
        logger.warning("R2 delete failed for %s object(s): %s", len(paths), e)
        return 0


def exists(path: str) -> bool:
    try:
        get_client().head_object(Bucket=settings.r2_bucket, Key=path)
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_cors() -> None:
    """Allow any origin to fetch a photo.

    The extension downloads a photo from whatever marketplace page it is
    standing on and hands the bytes to that site's upload form. Without this the
    browser blocks the read and items publish without a single image — the exact
    failure that made us mirror photos in the first place.
    """
    get_client().put_bucket_cors(
        Bucket=settings.r2_bucket,
        CORSConfiguration={
            "CORSRules": [{
                "AllowedOrigins": ["*"],
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["Content-Length", "Content-Type"],
                "MaxAgeSeconds": 86400,
            }]
        },
    )
