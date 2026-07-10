# cms/media.py
"""
Media file upload handling.

Validates file types, generates safe UUID-prefixed filenames, and
delegates storage to the configured backend (local disk or S3).
"""
from __future__ import annotations

import os
import re
import uuid
from xml.etree import ElementTree

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


# ── SVG sanitisation ───────────────────────────────────────
# SVG is an XML format that can carry <script> elements, inline event
# handlers (onclick/onload/etc.) and javascript:/data: URLs in href
# attributes — all of which execute as scripts when the file is served
# inline (image/svg+xml). Strip those before persisting so an uploaded
# SVG can't become a stored XSS vector.

_SVG_DANGEROUS_TAGS = {"script", "foreignobject"}
_SCRIPT_URL_RE = re.compile(r"^\s*(javascript|vbscript|data):", re.IGNORECASE)


def _strip_dangerous_svg(root: ElementTree.Element) -> None:
    """Recursively drop dangerous elements and attributes from *root* in place."""
    # Filter children first so we don't recurse into removed nodes.
    kept = []
    for child in list(root):
        local = child.tag.split("}", 1)[-1].lower()
        if local in _SVG_DANGEROUS_TAGS:
            continue
        kept.append(child)
    root[:] = kept
    # Clean attributes on this element.
    for attr in list(root.attrib):
        lname = attr.split("}", 1)[-1].lower()
        if lname.startswith("on"):
            del root.attrib[attr]
            continue
        if lname in ("href", "xlink:href"):
            if _SCRIPT_URL_RE.match(root.attrib.get(attr, "")):
                del root.attrib[attr]
    # Recurse into surviving children.
    for child in root:
        _strip_dangerous_svg(child)


def sanitize_svg(data: bytes) -> bytes:
    """Parse SVG XML, strip script/event-handler/javascript-URL nodes, and
    re-serialise. Raises :class:`MediaError` if the file isn't well-formed
    XML or has no SVG root element.
    """
    try:
        parsed = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise MediaError(f"SVG upload is not well-formed XML: {exc}") from exc
    root_local = parsed.tag.split("}", 1)[-1].lower()
    if root_local != "svg":
        raise MediaError("SVG upload root element is not <svg>")
    _strip_dangerous_svg(parsed)
    return ElementTree.tostring(parsed, encoding="utf-8")


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

    # SVG can carry <script>/event handlers — sanitise before storing.
    if filename.endswith(".svg"):
        file_data = sanitize_svg(file_data)

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
