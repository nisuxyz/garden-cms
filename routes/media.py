# routes/media.py
"""
Serve media files through the active storage backend.

Works for both local-disk and S3 backends — replaces the previous
``StaticFilesConfig`` for ``/media/``.
"""
import logging

from litestar import Response, Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect

from cms.storage import S3StorageBackend, get_backend

log = logging.getLogger(__name__)


@get("/{filename:path}")
async def serve_media(filename: str) -> Response | Redirect:
    """Return the requested media file from the active storage backend."""
    backend = get_backend()
    filename = filename.strip("/")
    log.debug("serve_media: backend=%s, filename=%s", type(backend).__name__, filename)

    # If the S3 backend has a public URL, redirect there directly.
    if isinstance(backend, S3StorageBackend) and backend.public_url:
        return Redirect(path=backend.url(filename), status_code=302)

    try:
        body, content_type = await backend.get_object(filename)
    except FileNotFoundError:
        raise NotFoundException(detail="Media file not found")
    except Exception as exc:  # noqa: BLE001 — surface a 404 to clients for any backend miss
        log.error("serve_media failed for %s: %s", filename, exc)
        raise NotFoundException(detail="Media file not found")

    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


media_router = Router(path="/media", route_handlers=[serve_media])
