# tests/test_csrf.py
"""
CSRF protection integration tests.

Exercises the real admin router (login flow) through Litestar's TestClient
with the same session + CSRF middleware the production app uses. The Postgres
lifespan is bypassed; the Piccolo tables are pointed at the in-process SQLite
engine by the shared ``engine`` fixture, so the login handler can read its
env-var-backed password check without a DB pool.

These lock the property added during the de-slopping pass: every mutating
request must carry a valid CSRF token (header for HTMX / non-form bodies,
``_csrf_token`` form field for url-encoded forms).
"""
from __future__ import annotations

import os

import pytest
from pathlib import Path

from litestar import Litestar
from litestar.config.csrf import CSRFConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.middleware.session.client_side import CookieBackendConfig
from litestar.plugins.htmx import HTMXPlugin
from litestar.template.config import TemplateConfig
from litestar.testing import TestClient

from routes.admin import admin_router


def _secret_bytes() -> bytes:
    import hashlib

    return hashlib.sha256((os.getenv("SECRET_KEY") or "dev-secret-change-me").encode()).digest()


def _build_app() -> Litestar:
    return Litestar(
        route_handlers=[admin_router],
        template_config=TemplateConfig(
            directory=Path("templates"),
            engine=JinjaTemplateEngine,
        ),
        middleware=[CookieBackendConfig(secret=_secret_bytes()).middleware],
        csrf_config=CSRFConfig(
            secret=os.getenv("SECRET_KEY") or "dev-secret-change-me",
            cookie_name="csrftoken",
            header_name="x-csrftoken",
            cookie_samesite="lax",
            cookie_httponly=False,
        ),
        plugins=[HTMXPlugin()],
        debug=True,
    )


@pytest.fixture
def csrf_client(engine, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pw")
    with TestClient(app=_build_app()) as client:
        yield client


def test_get_login_sets_csrf_cookie(csrf_client):
    resp = csrf_client.get("/admin/login")
    assert resp.status_code == 200
    # The CSRF middleware sets the cookie on safe-method responses.
    cookies = csrf_client.cookies
    assert "csrftoken" in cookies


def test_post_login_without_token_is_rejected(csrf_client):
    # Prime the cookie with a GET first.
    csrf_client.get("/admin/login")
    # POST without _csrf_token and without header → rejected.
    resp = csrf_client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw"},
    )
    assert resp.status_code == 403


def test_post_login_with_valid_form_token_succeeds(csrf_client):
    csrf_client.get("/admin/login")
    token = csrf_client.cookies["csrftoken"]
    resp = csrf_client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw", "_csrf_token": token},
        follow_redirects=False,
    )
    # Successful password login redirects (302) to the dashboard.
    assert resp.status_code == 302
    # Session is now authenticated — the guarded dashboard is reachable.
    dash = csrf_client.get("/admin/")
    assert dash.status_code == 200


def test_post_login_with_header_token_succeeds(csrf_client):
    """HTMX-style: token sent in the x-csrftoken header instead of the body."""
    csrf_client.get("/admin/login")
    token = csrf_client.cookies["csrftoken"]
    resp = csrf_client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw"},
        headers={"x-csrftoken": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_post_login_with_wrong_token_is_rejected(csrf_client):
    csrf_client.get("/admin/login")
    resp = csrf_client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw", "_csrf_token": "garbage"},
    )
    assert resp.status_code == 403