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
    from backend.services import r2_storage

    # R2 is the destination once it is configured; without credentials this is
    # skipped entirely and everything behaves exactly as it did on Supabase.
    # An R2 failure also falls back rather than losing the photo.
    if r2_storage.is_configured():
        try:
            return r2_storage.upload(file_bytes, filename)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "R2 upload failed for %s (%s) — falling back to Supabase Storage", filename, e)

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


_PUBLIC_MARKER = f"/storage/v1/object/public/{BUCKET}/"


def storage_path_from_url(url: str) -> str | None:
    """Turn a public bucket url back into its object path, or None.

    Anything that is not unmistakably one of OUR objects returns None — a
    marketplace CDN url, a signed url, a malformed string. Callers use this to
    decide what to delete, so "not sure" must always mean "leave it alone".
    """
    if not isinstance(url, str) or _PUBLIC_MARKER not in url:
        return None
    path = url.split(_PUBLIC_MARKER, 1)[1].split("?", 1)[0].split("#", 1)[0]
    path = path.strip("/")
    # Traversal or an empty tail would address something we never wrote.
    if not path or ".." in path:
        return None
    return path


def locate_object(url: str) -> tuple[str, str] | None:
    """Find which storage a photo url lives on: ("r2"|"supabase", path), or None.

    During and after the migration both kinds of url exist side by side, so
    anything that wants to delete a photo has to ask this first.
    """
    from backend.services import r2_storage

    path = r2_storage.path_from_url(url)
    if path:
        return ("r2", path)
    path = storage_path_from_url(url)
    if path:
        return ("supabase", path)
    return None


def delete_objects(refs: list[tuple[str, str]]) -> int:
    """Delete located objects on whichever storage they live on."""
    from backend.services import r2_storage

    r2_paths = [p for backend, p in refs if backend == "r2"]
    sb_paths = [p for backend, p in refs if backend == "supabase"]
    return (r2_storage.delete(r2_paths) if r2_paths else 0) + \
           (delete_images_sync(sb_paths) if sb_paths else 0)


def delete_images_sync(paths: list[str]) -> int:
    """Remove objects from the bucket. Returns how many were accepted.

    Best-effort by design: storage may refuse the delete (the production key is
    the anon key, which RLS can block). A failure is logged and swallowed —
    nothing that calls this may break because a cleanup didn't happen.
    """
    paths = [p for p in paths if p]
    if not paths:
        return 0
    import logging
    try:
        with _UPLOAD_LOCK:
            verwijderd = get_db().storage.from_(BUCKET).remove(paths) or []
        # Storage raises nothing when row-level security refuses a delete — it
        # answers 200 with an empty list. Without this check a cleanup silently
        # does nothing and the bucket keeps growing while the logs stay clean.
        if len(verwijderd) != len(paths):
            logging.getLogger(__name__).warning(
                "storage delete removed %s of %s object(s) without an error — "
                "usually means the key may not delete", len(verwijderd), len(paths))
        return len(verwijderd)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("storage delete failed for %s object(s): %s", len(paths), e)
        return 0


async def upload_image(file_bytes: bytes, filename: str) -> str:
    """Upload raw bytes to Supabase Storage. Returns the public URL.

    The Supabase client is SYNCHRONOUS: awaiting this used to run a multi-second
    upload straight on the event loop, freezing every other request for its
    duration. Mirroring an import means dozens of these back to back, so the
    blocking call goes to a worker thread.
    """
    return await asyncio.to_thread(upload_image_sync, file_bytes, filename)
