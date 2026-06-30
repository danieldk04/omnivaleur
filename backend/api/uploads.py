"""
Photo upload endpoint — stores to Supabase Storage bucket 'photos'.
"""
import uuid
import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from backend.database import get_db
from backend.api.deps import get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])
BUCKET = "photos"
MAX_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/photo")
async def upload_photo(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF allowed")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 25 MB)")

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    path = f"{user_id}/{uuid.uuid4()}.{ext}"

    db = get_db()
    try:
        db.storage.from_(BUCKET).upload(path, data, file_options={"content-type": content_type})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    public_url = db.storage.from_(BUCKET).get_public_url(path)
    return {"url": public_url, "path": path}
