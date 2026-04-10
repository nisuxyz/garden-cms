# app.py
import os
from pathlib import Path

from dotenv import load_dotenv
from litestar import Litestar, Request, Response
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.exceptions import NotAuthorizedException
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.plugins.htmx import HTMXPlugin
from litestar.response import Redirect
from litestar.static_files.config import StaticFilesConfig
from litestar.template.config import TemplateConfig

from db.connection import db_lifespan
from cms.catalog import init_catalog
from routes.admin import admin_router
from routes.api import api_router
from routes.media import media_router
from routes.pages import favicon, pages_router

load_dotenv()


# ── Session middleware ─────────────────────────────────────

_secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
# CookieBackendConfig needs a bytes key (≥16 bytes)
_secret_bytes = _secret.encode().ljust(16, b"\0")[:16]
session_config = CookieBackendConfig(secret=_secret_bytes)  # type: ignore[arg-type]


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
    template_config=TemplateConfig(
        directory=Path("templates"),
        engine=JinjaTemplateEngine,
    ),
    static_files_config=_static_configs,
    middleware=[session_config.middleware],
    plugins=[HTMXPlugin()],
    exception_handlers={NotAuthorizedException: _handle_not_authorized},
    after_request=add_security_headers,
    debug=os.getenv("DEBUG", "false").lower() == "true",
)

# Register JinjaX extension and component globals on the shared Jinja env.
init_catalog(app.template_engine.engine)
