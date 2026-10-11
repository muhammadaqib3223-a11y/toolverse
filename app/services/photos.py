"""Profile photos: check an uploaded picture and turn it into a small, clean JPEG.

The browser already shrinks the photo, but nothing from a browser is trusted: here we check it
really is a JPEG/PNG/WebP picture, crop it square, resize it and save it again. Saving again
drops all hidden data (EXIF: GPS location, camera, date), which is important for privacy.
"""
import base64
import binascii
import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 300 * 1024   # after the browser's compression; also the Storage bucket limit
MAX_SIDE = 512                  # pixels
MIN_SIDE = 64
JPEG_QUALITY = 85
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

_DATA_URL_RE = re.compile(r"^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=\s]+)$")

# A decompression bomb is a tiny file that expands to a gigantic picture; refuse those early.
Image.MAX_IMAGE_PIXELS = 25_000_000


class PhotoError(ValueError):
    """code: "photo_invalid" (not a usable picture) or "photo_too_large"."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def from_data_url(data_url):
    """Bytes of a `data:image/...;base64,...` string (what the browser sends)."""
    if not isinstance(data_url, str):
        raise PhotoError("photo_invalid")
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise PhotoError("photo_invalid")
    # Base64 is 4/3 of the real size: refuse a too-big photo before decoding it.
    if len(match.group(2)) > MAX_UPLOAD_BYTES * 4 // 3 + 16:
        raise PhotoError("photo_too_large")
    try:
        return base64.b64decode(match.group(2), validate=False)
    except (binascii.Error, ValueError):
        raise PhotoError("photo_invalid") from None


def to_data_url(jpeg_bytes):
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")


def clean_photo(raw):
    """A square JPEG (at most MAX_SIDE px, no hidden data) from uploaded picture bytes."""
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise PhotoError("photo_too_large" if raw else "photo_invalid")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ALLOWED_FORMATS:
                raise PhotoError("photo_invalid")
            image.load()
            image = ImageOps.exif_transpose(image)  # phones store "rotate me" in EXIF
            if min(image.size) < MIN_SIDE:
                raise PhotoError("photo_invalid")
            side = min(image.size)
            image = ImageOps.fit(image.convert("RGB"), (min(side, MAX_SIDE),) * 2, Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)  # no exif= : metadata dropped
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise PhotoError("photo_invalid") from None
    return out.getvalue()


def clean_data_url(data_url):
    """from_data_url() + clean_photo() in one step."""
    return clean_photo(from_data_url(data_url))
