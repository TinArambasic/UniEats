from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from app.config import settings

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MENU_UPLOAD_PREFIX = "/static/uploads/menu/"
PROFILE_UPLOAD_PREFIX = "/static/uploads/profiles/"
STATIC_ROOT = Path.cwd() / "static"


def _ensure_upload_directory(upload_dir_raw: str) -> Path:
    upload_dir = Path(upload_dir_raw)
    if not upload_dir.is_absolute():
        upload_dir = Path.cwd() / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _build_public_url(path: Path) -> str:
    resolved_static = STATIC_ROOT.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_static):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload direktorij mora biti unutar /static",
        )
    rel = resolved_path.relative_to(resolved_static).as_posix()
    return f"/static/{rel}"


def _detect_mime_from_magic(content: bytes) -> str | None:
    if len(content) >= 3 and content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(content) >= 8 and content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _sanitize_image(
    content: bytes,
    detected_mime: str,
    *,
    max_width: int,
    max_height: int,
) -> bytes:
    try:
        with Image.open(BytesIO(content)) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            if width > max_width or height > max_height:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Dimenzije slike su prevelike. Maksimalno: "
                        f"{max_width}x{max_height}px"
                    ),
                )

            out = BytesIO()
            if detected_mime == "image/jpeg":
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(out, format="JPEG", quality=88, optimize=True)
            elif detected_mime == "image/png":
                if img.mode not in ("RGB", "RGBA", "L", "LA"):
                    img = img.convert("RGBA")
                img.save(out, format="PNG", optimize=True)
            else:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                img.save(out, format="WEBP", quality=88, method=6)

            return out.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datoteka nije valjana slika",
        ) from exc


async def _save_image(
    file: UploadFile,
    *,
    upload_dir_raw: str,
    max_bytes: int,
    max_width: int,
    max_height: int,
) -> str:
    declared_mime = (file.content_type or "").lower()
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datoteka je prazna",
        )
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Datoteka je prevelika. Maksimalna velicina je "
                f"{max_bytes // (1024 * 1024)} MB"
            ),
        )

    detected_mime = _detect_mime_from_magic(content)
    if detected_mime not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dozvoljeni formati su JPEG, PNG i WEBP",
        )
    if declared_mime and declared_mime != detected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MIME tip datoteke ne odgovara stvarnom sadrzaju",
        )

    sanitized = _sanitize_image(
        content,
        detected_mime,
        max_width=max_width,
        max_height=max_height,
    )
    if len(sanitized) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Obradena slika je prevelika",
        )

    upload_dir = _ensure_upload_directory(upload_dir_raw)
    ext = ALLOWED_IMAGE_TYPES[detected_mime]
    while True:
        filename = f"{uuid4().hex}{ext}"
        out_path = upload_dir / filename
        if not out_path.exists():
            break
    out_path.write_bytes(sanitized)
    return _build_public_url(out_path)


async def save_menu_item_image(file: UploadFile) -> str:
    return await _save_image(
        file,
        upload_dir_raw=settings.MENU_IMAGE_UPLOAD_DIR,
        max_bytes=settings.MENU_IMAGE_MAX_BYTES,
        max_width=settings.MENU_IMAGE_MAX_WIDTH,
        max_height=settings.MENU_IMAGE_MAX_HEIGHT,
    )


async def save_profile_image(file: UploadFile) -> str:
    return await _save_image(
        file,
        upload_dir_raw=settings.PROFILE_IMAGE_UPLOAD_DIR,
        max_bytes=settings.PROFILE_IMAGE_MAX_BYTES,
        max_width=settings.PROFILE_IMAGE_MAX_WIDTH,
        max_height=settings.PROFILE_IMAGE_MAX_HEIGHT,
    )


def _is_managed_upload(image_url: str | None, prefix: str) -> bool:
    return bool(image_url and image_url.startswith(prefix))


def is_managed_menu_upload(image_url: str | None) -> bool:
    return _is_managed_upload(image_url, MENU_UPLOAD_PREFIX)


def is_managed_profile_upload(image_url: str | None) -> bool:
    return _is_managed_upload(image_url, PROFILE_UPLOAD_PREFIX)


def _delete_image_file(image_url: str | None, prefix: str) -> None:
    if not _is_managed_upload(image_url, prefix):
        return
    rel = image_url.removeprefix("/static/")
    target = (STATIC_ROOT / rel).resolve()
    if not target.is_relative_to(STATIC_ROOT.resolve()):
        return
    if target.exists() and target.is_file():
        target.unlink()


def delete_menu_image_file(image_url: str | None) -> None:
    _delete_image_file(image_url, MENU_UPLOAD_PREFIX)


def delete_profile_image_file(image_url: str | None) -> None:
    _delete_image_file(image_url, PROFILE_UPLOAD_PREFIX)
