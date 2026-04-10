# cms/media.py
"""
Media file upload handling.

Validates file types, generates safe UUID-prefixed filenames, and
delegates storage to the configured backend (local disk or S3).
"""
from __future__ import annotations

import os
import uuid

from cms.storage import get_backend
from db.tables import MediaFile

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

    # Delegate to the active storage backend.
    backend = get_backend()
    file_path = await backend.save(filename, file_data, content_type)

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

    # Remove file via storage backend.
    backend = get_backend()
    await backend.delete(row["filename"])

    await MediaFile.delete().where(MediaFile.id == media_id)
