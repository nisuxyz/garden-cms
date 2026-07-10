# tests/conftest.py
"""
Test fixtures.

Uses Piccolo's SQLiteEngine so tests run without Postgres.
The engine is patched onto every Table class that our app defines
so queries hit the temporary test DB.
"""
import os
import tempfile

import pytest_asyncio
from piccolo.engine.sqlite import SQLiteEngine

from db.connection import init_db
from db.tables import (
    Collection,
    CollectionItem,
    CollectionItemSlugHistory,
    ContentBlock,
    MediaFile,
    Page,
    SiteSettings,
    Theme,
)

# Order matters: parents before children (FK deps).
_ALL_TABLES = [
    Theme,
    Page,
    ContentBlock,
    Collection,
    CollectionItem,
    CollectionItemSlugHistory,
    MediaFile,
    SiteSettings,
]


@pytest_asyncio.fixture
async def engine():
    """Create a file-backed SQLite engine for testing.

    We use a temp file rather than :memory: because Piccolo's
    SQLiteEngine opens a new connection per query, and each
    :memory: connection is a *separate* database.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    test_engine = SQLiteEngine(path=tmp.name)

    # Point every content table at this engine
    for tbl in _ALL_TABLES:
        tbl._meta._db = test_engine  # type: ignore[attr-defined]

    # Create tables
    for tbl in _ALL_TABLES:
        await tbl.create_table(if_not_exists=True)

    # Seed default CMS content
    await init_db()

    # Set up JinjaX catalog (must happen before load_site_dict which uses render_sync).
    from jinja2 import Environment, FileSystemLoader
    from cms.catalog import init_catalog
    test_jinja_env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=False,
    )
    init_catalog(test_jinja_env)

    # Load site context cache (uses render_sync internally).
    from cms.site_context import load_site_dict
    await load_site_dict()

    yield test_engine

    # Cleanup
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


# ── Shared HTTP app fixture ─────────────────────────────────


def _build_http_app() -> "Litestar":
    """Build a Litestar app wired up like the production app but without
    the Postgres lifespan (tables are pointed at the in-process SQLite
    engine by the ``engine`` fixture). Includes session + CSRF middleware
    and the real admin/pages/api/media routers so HTTP-level integration
    tests exercise the actual request pipeline."""
    import hashlib
    import os as _os
    from pathlib import Path

    from litestar import Litestar
    from litestar.config.csrf import CSRFConfig
    from litestar.contrib.jinja import JinjaTemplateEngine
    from litestar.middleware.session.client_side import CookieBackendConfig
    from litestar.plugins.htmx import HTMXPlugin
    from litestar.static_files.config import StaticFilesConfig
    from litestar.template.config import TemplateConfig

    from routes.admin import admin_router
    from routes.api import api_router
    from routes.media import media_router
    from routes.pages import favicon, pages_router

    secret = _os.getenv("SECRET_KEY") or "dev-secret-change-me"
    secret_bytes = hashlib.sha256(secret.encode()).digest()

    async def _add_security_headers(response):
        response.headers["Vary"] = "HX-Request"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return Litestar(
        route_handlers=[media_router, favicon, pages_router, api_router, admin_router],
        template_config=TemplateConfig(
            directory=Path("templates"),
            engine=JinjaTemplateEngine,
        ),
        static_files_config=[StaticFilesConfig(directories=[Path("static")], path="/static")],
        middleware=[CookieBackendConfig(secret=secret_bytes).middleware],
        csrf_config=CSRFConfig(
            secret=secret,
            cookie_name="csrftoken",
            header_name="x-csrftoken",
            cookie_samesite="lax",
            cookie_httponly=False,
        ),
        plugins=[HTMXPlugin()],
        after_request=_add_security_headers,
        debug=True,
    )


@pytest_asyncio.fixture
async def http_client(engine, monkeypatch):
    """A Litestar TestClient backed by the real app + SQLite engine.

    Sets ADMIN_PASSWORD so the password login flow can be exercised.
    """
    import os as _os
    from litestar.testing import TestClient

    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pw")
    app = _build_http_app()
    with TestClient(app=app) as client:
        # Prime the CSRF cookie with a GET before returning.
        yield client


def _login(client) -> str:
    """Log in via the password flow and return the CSRF token.

    Assumes ``ADMIN_PASSWORD`` is set to ``"test-admin-pw"``.
    """
    client.get("/admin/login")
    token = client.cookies["csrftoken"]
    client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw", "_csrf_token": token},
        follow_redirects=False,
    )
    # After login the cookie may have rotated; refresh.
    client.get("/admin/")
    return client.cookies.get("csrftoken", token)
