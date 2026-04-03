# app.py
import os
from pathlib import Path

from dotenv import load_dotenv
from litestar import Litestar, Response
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.plugins.htmx import HTMXPlugin
from litestar.static_files.config import StaticFilesConfig
from litestar.template.config import TemplateConfig

from db.connection import db_lifespan
from routes.admin import admin_router
from routes.blog import blog_router
from routes.pages import pages_router
from routes.projects import projects_router

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


# ── Application ────────────────────────────────────────────

app = Litestar(
    route_handlers=[pages_router, blog_router, projects_router, admin_router],
    lifespan=[db_lifespan],
    template_config=TemplateConfig(
        directory=Path("templates"),
        engine=JinjaTemplateEngine,
    ),
    static_files_config=[
        StaticFilesConfig(directories=[Path("static")], path="/static"),
    ],
    middleware=[session_config.middleware],
    plugins=[HTMXPlugin()],
    after_request=add_security_headers,
    debug=os.getenv("DEBUG", "false").lower() == "true",
)
