"""
Photo upload endpoint — stores to Cloudinary, returns public URL.
"""
import uuid
import mimetypes
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from backend.api.deps import get_current_user
from backend.services.image_upload import upload_image

router = APIRouter(prefix="/uploads", tags=["uploads"])
MAX_SIZE = 25 * 1024 * 1024  # 25 MB
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}


@router.post("/photo")
async def upload_photo(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or GIF allowed")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 25 MB)")

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    filename = f"{user_id}/{uuid.uuid4()}.{ext}"

    try:
        url = await upload_image(data, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return {"url": url, "path": filename}
