# cms/media.py
"""
Media file upload handling.

Validates file types, generates safe UUID-prefixed filenames, and saves
to ``data/media/``.  Designed with a storage-backend abstraction point
so a future S3 adapter can be dropped in.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import BinaryIO

from db.tables import MediaFile

MEDIA_ROOT = Path("data/media")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
ALLOWED_MIMETYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class MediaError(Exception):
    """Raised when a media upload fails validation."""


def _safe_filename(original: str) -> str:
    """Generate a UUID-prefixed filename preserving the original extension."""
    _, ext = os.path.splitext(original)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise MediaError(f"File type {ext} is not allowed")
    return f"{uuid.uuid4().hex}{ext}"


async def save_upload(
    file_data: bytes,
    original_name: str,
    content_type: str,
    alt_text: str | None = None,
) -> dict:
    """Validate and save an uploaded file.

    Returns the created MediaFile row as a dict.
    """
    # Validate mime type.
    if content_type not in ALLOWED_MIMETYPES:
        raise MediaError(f"Content type {content_type} is not allowed")

    # Validate size.
    if len(file_data) > MAX_FILE_SIZE:
        raise MediaError(f"File exceeds maximum size of {MAX_FILE_SIZE // 1024 // 1024} MB")

    filename = _safe_filename(original_name)
    file_path = str(MEDIA_ROOT / filename)

    # Ensure media directory exists.
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    # Write file to disk.
    with open(file_path, "wb") as f:
        f.write(file_data)

    # Create DB record.
    media = MediaFile(
        filename=filename,
        original_name=original_name,
        file_path=file_path,
        mime_type=content_type,
        alt_text=alt_text,
        file_size=len(file_data),
    )
    await media.save()

    return await (
        MediaFile.select()
        .where(MediaFile.filename == filename)
        .first()
        
    )


async def delete_media(media_id: int) -> None:
    """Delete a media file from disk and DB."""
    row = await (
        MediaFile.select()
        .where(MediaFile.id == media_id)
        .first()
        
    )
    if row is None:
        return

    # Remove file from disk.
    try:
        os.remove(row["file_path"])
    except FileNotFoundError:
        pass

    await MediaFile.delete().where(MediaFile.id == media_id)
