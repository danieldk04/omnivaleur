"""Upload photos to Supabase Storage and return public URLs."""
import asyncio
import threading

from backend.database import get_db

BUCKET = "photos"

# get_db() hands out ONE shared Supabase client, and its storage client is not
# thread-safe: uploading from several worker threads at once corrupts the request
# it builds, which the API rejects as "new row violates row-level security
# policy" — an authorisation error for what is really a race. Observed while
# mirroring a 9-photo item: sequential uploads all succeeded, concurrent ones
# failed 8 out of 9. Uploads are therefore serialised; the slow part (downloading
# from the source CDN) stays fully concurrent.
_UPLOAD_LOCK = threading.Lock()


def upload_image_sync(file_bytes: bytes, filename: str) -> str:
    """Blocking upload. Only call this off the event loop (see upload_image)."""
    db = get_db()

    with _UPLOAD_LOCK:
        try:
            db.storage.from_(BUCKET).upload(
                path=filename,
                file=file_bytes,
                file_options={"upsert": "true"},
            )
        except Exception:
            # The upsert flag is not honoured by every storage backend/key: writing
            # to a path that already exists comes back as "new row violates
            # row-level security policy", which reads like an auth problem but is
            # really a duplicate. The mirror addresses objects by the SHA-256 of
            # their bytes, so an object already sitting at this path IS this
            # image — re-uploading it would be a no-op anyway. Confirm it's there
            # and use it; only a genuinely missing object is an error.
            if not _object_exists(filename):
                raise
        return db.storage.from_(BUCKET).get_public_url(filename)


def _object_exists(filename: str) -> bool:
    try:
        folder, _, name = filename.rpartition("/")
        listing = get_db().storage.from_(BUCKET).list(path=folder) or []
        return any(entry.get("name") == name for entry in listing)
    except Exception:
        return False


async def upload_image(file_bytes: bytes, filename: str) -> str:
    """Upload raw bytes to Supabase Storage. Returns the public URL.

    The Supabase client is SYNCHRONOUS: awaiting this used to run a multi-second
    upload straight on the event loop, freezing every other request for its
    duration. Mirroring an import means dozens of these back to back, so the
    blocking call goes to a worker thread.
    """
    return await asyncio.to_thread(upload_image_sync, file_bytes, filename)
