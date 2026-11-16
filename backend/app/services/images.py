"""업로드 사진 처리: 디코드, 방향 보정, 축소, 저장, 지각 해시, EXIF 촬영 시각."""
import base64
import io
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.services.clock import now

MAX_EDGE_STORE = 1280


class BadImage(Exception):
    pass


def open_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise BadImage("이미지를 읽을 수 없습니다") from e
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def exif_taken_at(data: bytes) -> datetime | None:
    try:
        img = Image.open(io.BytesIO(data))
        exif = img.getexif()
        sub = exif.get_ifd(ExifTags.IFD.Exif)
        raw = sub.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


def resized(img: Image.Image, edge: int) -> Image.Image:
    w, h = img.size
    scale = edge / max(w, h)
    if scale >= 1:
        return img
    return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def to_b64_jpeg(img: Image.Image, edge: int, quality: int = 85) -> str:
    buf = io.BytesIO()
    resized(img, edge).save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def save(img: Image.Image, kind: str) -> str:
    d = now()
    rel = Path(kind) / d.strftime("%Y%m") / f"{d.strftime('%d%H%M%S')}_{uuid.uuid4().hex[:10]}.jpg"
    path = Path(settings.UPLOAD_DIR) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    resized(img, MAX_EDGE_STORE).save(path, "JPEG", quality=82)
    return rel.as_posix()


def phash(img: Image.Image) -> str:
    """DCT 기반 64비트 지각 해시 (16자리 hex)."""
    g = np.asarray(img.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float64)
    n = 32
    k = np.arange(n)
    c = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))  # DCT-II 행렬
    dct = c @ g @ c.T
    low = dct[:8, :8].flatten()
    med = np.median(low[1:])
    bits = low > med
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")
