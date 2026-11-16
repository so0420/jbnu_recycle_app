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
MAX_PIXELS = 40_000_000          # 약 8000×5000. 이보다 크면 거절 (압축 폭탄 방지)
MAX_EDGE_IN = 10_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class BadImage(Exception):
    pass


def open_image(data: bytes) -> Image.Image:
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            if w * h > MAX_PIXELS or max(w, h) > MAX_EDGE_IN:
                raise BadImage("사진이 너무 커요")
            if img.format == "JPEG":
                img.draft("RGB", (2048, 2048))     # 큰 JPEG 는 축소해서 읽는다
            img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning,
            ValueError) as e:
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


def remove(rel_path: str) -> None:
    """요청이 실패했을 때 저장해 둔 사진을 지운다."""
    if rel_path:
        (Path(settings.UPLOAD_DIR) / rel_path).unlink(missing_ok=True)
