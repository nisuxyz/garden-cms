# cms/errors.py
"""
Admin-configurable error/status pages.

A single generic "Status page" (a Page selected in Settings) is rendered
for every error response on the public site. Its body is rendered with
``status_code`` / ``status_text`` / ``error`` (and, when ``DEBUG=true``, a
``traceback``) so it can branch on the status code itself.

Litestar invokes exception handlers *synchronously* (it does not await
them), so the handler cannot do async DB access directly. Instead it
returns a :class:`~litestar.response.Stream` whose async generator runs
on the event loop — that's where the DB reads and themed render happen.
The generator computes the whole page (with a built-in fallback) before
yielding a single chunk, so a render failure never sends a half-page.

Registered for ``NotFoundException``, ``HTTPException``, and the catch-all
``Exception`` (500). ``NotAuthorizedException`` is more specific and keeps
its login-redirect handler.
"""
from __future__ import annotations

import http
import logging
import os
import traceback as _traceback

from litestar import Request
from litestar.response import Stream

log = logging.getLogger("cms.errors")

# Requests to these prefixes get a plain built-in error, never the themed
# public status page (a themed 404 inside /admin would be confusing, and
# API/asset clients want a terse body).
_INFRA_PREFIXES = ("/admin", "/api", "/media", "/static", "/favicon")


def _status_text(status: int) -> str:
    try:
        return http.HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def _default_error_html(status: int) -> str:
    """Minimal, dependency-free fallback page."""
    text = _status_text(status)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{status} {text}</title>"
        "<style>body{font-family:system-ui,sans-serif;display:grid;"
        "place-items:center;min-height:100vh;margin:0;color:#334155;"
        "background:#f8fafc}main{text-align:center;padding:2rem}"
        "h1{font-size:3rem;margin:0}p{color:#64748b}</style></head><body>"
        f"<main><h1>{status}</h1><p>{text}</p></main></body></html>"
    )


def _is_debug() -> bool:
    return os.getenv("DEBUG", "false").lower() == "true"


async def _render_status_html(status: int, path: str, exc: Exception) -> str:
    """Render the configured status Page through the active theme.

    Falls back to the built-in HTML on any failure (including a missing
    or broken status page) so the error path can never itself error.
    """
    try:
        from db.tables import SiteSettings
        row = await (
            SiteSettings.select(SiteSettings.value)
            .where(SiteSettings.key == "status_page")
            .first()
        )
        slug = (row.get("value", "") or "").strip() if row else ""
        if slug:
            from cms.engine import resolve_page, render_page
            page = await resolve_page(slug)
            if page:
                ctx = {
                    "status_code": status,
                    "status_text": _status_text(status),
                    "error": str(getattr(exc, "detail", "") or exc)
                    or _status_text(status),
                    "path": path,
                    "traceback": (
                        "".join(
                            _traceback.format_exception(
                                type(exc), exc, exc.__traceback__
                            )
                        )
                        if _is_debug()
                        else ""
                    ),
                }
                return await render_page(page, extra_context=ctx)
    except Exception:  # noqa: BLE001 — the error path must never raise
        log.exception("Status page render failed for %s", path)
    return _default_error_html(status)


def render_status_page(request: Request, exc: Exception) -> Stream:
    """Sync exception handler → streams the themed status page.

    The async render is deferred into the Stream's generator so it runs
    on the event loop (where the DB pool and renderer live).
    """
    status = int(getattr(exc, "status_code", 500) or 500)

    # Always surface server errors in the logs — never silently swallow.
    if status >= 500:
        log.exception("Unhandled error on %s", request.url.path, exc_info=exc)

    path = request.url.path
    infra = path.startswith(_INFRA_PREFIXES)

    async def _body():
        if infra:
            html = _default_error_html(status)
        else:
            html = await _render_status_html(status, path, exc)
        yield html.encode("utf-8")

    return Stream(
        _body(),
        status_code=status,
        media_type="text/html",
    )
