# app.py
import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
from litestar import Litestar, Request, Response
from litestar.config.csrf import CSRFConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.di import Provide
from litestar.exceptions import HTTPException, NotAuthorizedException, NotFoundException
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.plugins.htmx import HTMXPlugin
from litestar.response import Redirect
from litestar.static_files.config import StaticFilesConfig
from litestar.template.config import TemplateConfig

from db.connection import db_lifespan
from cms.catalog import init_catalog, provide_catalog
from cms.errors import render_status_page
from routes.admin import admin_router
from routes.api import api_router
from routes.media import media_router
from routes.pages import favicon, pages_router

load_dotenv()


# ── Session middleware ─────────────────────────────────────

_DEFAULT_SECRET = "dev-secret-change-me"
_secret = os.getenv("SECRET_KEY", _DEFAULT_SECRET) or ""

# CookieBackendConfig requires a bytes key of exactly 16, 24, or 32 bytes.
# The old code did `.encode().ljust(16, b"\0")[:16]`, which silently truncated
# long secrets to 16 bytes — a 64-char SECRET_KEY was effectively only as
# strong as its first 16 bytes. Instead, derive a 32-byte key via SHA-256 so
# every byte of the configured secret contributes and any length is accepted.
_secret_bytes = hashlib.sha256(_secret.encode()).digest()  # 32 bytes

# Fail fast if the insecure dev default (or an empty secret) is used in what
# looks like a production deploy.
_is_dev = (
    os.getenv("DEBUG", "false").lower() == "true"
    or "localhost" in os.getenv("DATABASE_URL", "localhost")
)
if _secret in ("", _DEFAULT_SECRET) and not _is_dev:
    raise RuntimeError(
        "SECRET_KEY is unset or empty (using the insecure dev default). Set "
        "SECRET_KEY to a random string for production deployments."
    )

session_config = CookieBackendConfig(secret=_secret_bytes)  # type: ignore[arg-type]


# ── CSRF middleware ────────────────────────────────────────

# Reuse the configured SECRET_KEY to sign CSRF tokens. The cookie is readable
# by JS (httponly=False) so HTMX can grab it and send it back as the
# ``x-csrftoken`` header on every mutating request; HTML forms additionally
# carry the token in a hidden ``_csrf_token`` field (Litestar's CSRFMiddleware
# checks both header and url-encoded body field).
csrf_config = CSRFConfig(
    secret=_secret,
    cookie_name="csrftoken",
    header_name="x-csrftoken",
    cookie_samesite="lax",
    cookie_httponly=False,
)


# ── Security headers hook ─────────────────────────────────

async def add_security_headers(response: Response) -> Response:
    """after_request hook: security headers + Vary for HTMX."""
    response.headers["Vary"] = "HX-Request"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _handle_not_authorized(request: "Request", exc: NotAuthorizedException) -> Redirect:
    """Redirect to login page instead of returning JSON 401."""
    redirect_to = "/admin/login"
    if isinstance(exc.extra, dict):
        redirect_to = exc.extra.get("redirect_to", redirect_to)
    return Redirect(path=redirect_to)


# ── Static files ───────────────────────────────────────────

_static_configs = [
    StaticFilesConfig(directories=[Path("static")], path="/static"),
]


# ── Application ────────────────────────────────────────────

app = Litestar(
    route_handlers=[media_router, favicon, pages_router, api_router, admin_router],
    lifespan=[db_lifespan],
    dependencies={"catalog": Provide(provide_catalog, sync_to_thread=False)},
    template_config=TemplateConfig(
        directory=Path("templates"),
        engine=JinjaTemplateEngine,
    ),
    static_files_config=_static_configs,
    middleware=[session_config.middleware],
    csrf_config=csrf_config,
    plugins=[HTMXPlugin()],
    exception_handlers={
        # Most-specific class wins, so the login redirect stays for 401s.
        NotAuthorizedException: _handle_not_authorized,
        NotFoundException: render_status_page,   # 404
        HTTPException: render_status_page,        # other 4xx/5xx
        Exception: render_status_page,            # uncaught → 500
    },
    after_request=add_security_headers,
    debug=os.getenv("DEBUG", "false").lower() == "true",
)

# Register JinjaX extension and component globals on the shared Jinja env.
init_catalog(app.template_engine.engine)
