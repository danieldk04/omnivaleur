"""Shrink a photo before it goes into our storage bucket.

A marketplace photo arrives at whatever the source CDN serves — often 2000+ px
and ~1 MB. Nothing we do with it needs that: every channel re-encodes on their
side, and the dashboard shows it at a few hundred pixels. Storing the original
filled the Supabase bucket to 346% of the free plan.

Deliberately conservative, because a lost or broken photo costs far more than a
few megabytes:

  * The FORMAT is preserved in spirit — a photo with transparency stays PNG,
    everything else becomes JPEG. Never WebP: Etsy's upload posts our bytes as
    image/jpeg and the extension hands the file straight to a marketplace form,
    so an exotic format would be rejected at exactly the moment it matters.
  * EXIF orientation is baked in before re-encoding. Re-saving strips EXIF, and
    without this an iPhone photo would come out sideways on every channel.
  * Anything unexpected — Pillow missing, a broken file, an animated GIF, a
    result that is not actually smaller — returns the ORIGINAL bytes unchanged.
    This function can only ever make a photo lighter, never absent.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

MAX_EDGE = 1600          # ruim boven wat elk kanaal toont; 4000px is puur ballast
JPEG_QUALITY = 82        # visueel niet te onderscheiden van het origineel
_WORTH_IT = 0.95         # onder de 5% winst laten we het origineel staan

_EXT_FALLBACK = "jpg"


def optimize_image(data: bytes, ext_hint: str = "") -> tuple[bytes, str]:
    """Return (bytes, extension). Falls back to the original on any doubt."""
    if not data:
        return data, (ext_hint or _EXT_FALLBACK)

    hint = (ext_hint or "").lower().lstrip(".")

    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001 - Pillow is optional at runtime
        logger.debug("image optimize: Pillow unavailable, storing original")
        return data, (hint or _EXT_FALLBACK)

    try:
        img = Image.open(io.BytesIO(data))
        source_format = (img.format or "").upper()

        # An animated GIF loses its animation on re-encode. Leave it alone.
        if source_format == "GIF" or getattr(img, "n_frames", 1) > 1:
            return data, (hint or "gif")

        img = ImageOps.exif_transpose(img) or img

        resized = False
        if max(img.size) > MAX_EDGE:
            img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            resized = True

        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )

        buf = io.BytesIO()
        if has_alpha:
            img.convert("RGBA").save(buf, format="PNG", optimize=True)
            ext = "png"
        else:
            img.convert("RGB").save(
                buf, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
            )
            ext = "jpg"
        out = buf.getvalue()

        # A photo that is already small can come out BIGGER after re-encoding.
        # Only take the new bytes when they are genuinely lighter.
        if not out or len(out) > len(data) * _WORTH_IT:
            return data, (hint or ext)

        logger.info(
            "image optimize: %s KB -> %s KB (%s%s)",
            len(data) // 1024, len(out) // 1024, ext, ", resized" if resized else "",
        )
        return out, ext
    except Exception as e:  # noqa: BLE001 - never lose a photo over an optimisation
        logger.warning("image optimize failed (%s), storing original", e)
        return data, (hint or _EXT_FALLBACK)
