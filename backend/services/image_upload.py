"""Upload photos to Supabase Storage and return public URLs."""
import asyncio

from backend.database import get_db

BUCKET = "photos"


def upload_image_sync(file_bytes: bytes, filename: str) -> str:
    """Blocking upload. Only call this off the event loop (see upload_image)."""
    db = get_db()

    db.storage.from_(BUCKET).upload(
        path=filename,
        file=file_bytes,
        file_options={"upsert": "true"},
    )

    return db.storage.from_(BUCKET).get_public_url(filename)


async def upload_image(file_bytes: bytes, filename: str) -> str:
    """Upload raw bytes to Supabase Storage. Returns the public URL.

    The Supabase client is SYNCHRONOUS: awaiting this used to run a multi-second
    upload straight on the event loop, freezing every other request for its
    duration. Mirroring an import means dozens of these back to back, so the
    blocking call goes to a worker thread.
    """
    return await asyncio.to_thread(upload_image_sync, file_bytes, filename)
