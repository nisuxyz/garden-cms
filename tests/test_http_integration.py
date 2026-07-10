# tests/test_http_integration.py
"""
HTTP-level integration tests against the real Litestar app.

Exercises the full request pipeline: auth flow, security headers, CSRF,
admin CRUD happy paths, favicon, public page routing, slug 301 redirects,
collection feeds, and the guard redirect on unauthenticated admin access.
"""
from __future__ import annotations

import pytest

from tests.conftest import _login


# ── Auth flow ──────────────────────────────────────────────


def test_get_login_page_renders(http_client):
    resp = http_client.get("/admin/login")
    assert resp.status_code == 200
    assert "admin" in resp.text.lower()
    # CSRF cookie is set on safe-method responses.
    assert "csrftoken" in http_client.cookies


def test_login_with_wrong_password_does_not_authenticate(http_client):
    http_client.get("/admin/login")
    token = http_client.cookies["csrftoken"]
    resp = http_client.post(
        "/admin/login",
        data={"username": "", "password": "wrong", "_csrf_token": token},
        follow_redirects=False,
    )
    # Wrong password → stays on login page (200 with error), not a redirect.
    assert resp.status_code == 200
    # Dashboard should still be guarded.
    dash = http_client.get("/admin/")
    assert dash.status_code in (302, 401, 403)


def test_login_with_correct_password_redirects_to_dashboard(http_client):
    http_client.get("/admin/login")
    token = http_client.cookies["csrftoken"]
    resp = http_client.post(
        "/admin/login",
        data={"username": "", "password": "test-admin-pw", "_csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin" in resp.headers.get("location", "")


def test_logout_clears_session(http_client):
    _login(http_client)
    assert http_client.get("/admin/").status_code == 200
    token = http_client.cookies["csrftoken"]
    http_client.post("/admin/logout", headers={"x-csrftoken": token}, follow_redirects=False)
    # After logout the dashboard is guarded again.
    guarded = http_client.get("/admin/", follow_redirects=False)
    assert guarded.status_code in (302, 401, 403)


# ── Guard redirect ─────────────────────────────────────────


def test_guarded_admin_route_redirects_to_login_when_unauthenticated(http_client):
    resp = http_client.get("/admin/", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


# ── Security headers ───────────────────────────────────────


def test_security_headers_present_on_public_page(http_client):
    resp = http_client.get("/")
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "HX-Request" in resp.headers.get("Vary", "")


# ── Public page routing ────────────────────────────────────


def test_homepage_renders(http_client):
    resp = http_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_contact_page_renders_without_form(http_client):
    """The seeded Contact page should render but no longer contain the
    dead /contact POST form (it was replaced with a placeholder)."""
    resp = http_client.get("/contact")
    assert resp.status_code == 200
    assert "not configured" in resp.text.lower() or "contact" in resp.text.lower()
    assert 'hx-post="/contact"' not in resp.text


def test_nonexistent_page_returns_404(http_client):
    resp = http_client.get("/this-page-does-not-exist-xyz")
    assert resp.status_code == 404


# ── Favicon ────────────────────────────────────────────────


def test_favicon_falls_back_to_static_svg(http_client):
    resp = http_client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")


# ── CSRF on mutating endpoints ─────────────────────────────


def test_admin_post_without_csrf_token_is_rejected(http_client):
    _login(http_client)
    # Clear the CSRF cookie to simulate a tokenless request.
    http_client.cookies.clear()
    resp = http_client.post(
        "/admin/pages",
        data={"title": "x", "slug": "x", "body": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 403


# ── Admin CRUD happy paths ─────────────────────────────────


def test_admin_dashboard_reachable_after_login(http_client):
    _login(http_client)
    resp = http_client.get("/admin/")
    assert resp.status_code == 200
    # Dashboard shows stat cards.
    assert "pages" in resp.text.lower() or "dashboard" in resp.text.lower()


def test_admin_pages_list_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/pages")
    assert resp.status_code == 200


def test_admin_create_page(http_client):
    _login(http_client)
    token = http_client.cookies["csrftoken"]
    resp = http_client.post(
        "/admin/pages",
        data={
            "title": "Test Page",
            "slug": "test-page-http",
            "body": "<p>Hello from test</p>",
            "published": "on",
        },
        headers={"x-csrftoken": token},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302)
    # The page should now be publicly reachable.
    pub = http_client.get("/test-page-http")
    assert pub.status_code == 200
    assert "Hello from test" in pub.text


def test_admin_themes_list_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/themes")
    assert resp.status_code == 200


def test_admin_content_blocks_list_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/content")
    assert resp.status_code == 200


def test_admin_collections_list_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/collections")
    assert resp.status_code == 200
    # The seeded "blog" collection should appear.
    assert "blog" in resp.text.lower()


def test_admin_media_page_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/media")
    assert resp.status_code == 200


def test_admin_settings_page_renders(http_client):
    _login(http_client)
    resp = http_client.get("/admin/settings")
    assert resp.status_code == 200
    # The S3 secret field should NOT echo a stored value.
    assert 'value="' not in resp.text.split("s3_secret_access_key")[1].split("<")[0] if "s3_secret_access_key" in resp.text else True


# ── Collection feed API ────────────────────────────────────


def test_collection_feed_api_returns_html(http_client):
    resp = http_client.get("/api/collection/blog/feed?page=1")
    # The seeded blog collection may have 0 items → empty template (200)
    # or cards (200). Either way it's not a 404.
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_collection_feed_api_nonexistent_collection_returns_404(http_client):
    resp = http_client.get("/api/collection/no-such-collection/feed?page=1")
    assert resp.status_code == 404


def test_collection_feed_api_clamps_negative_page(http_client):
    resp = http_client.get("/api/collection/blog/feed?page=-5")
    assert resp.status_code == 200  # clamped to page 1, not a 500


# ── Slug 301 redirect ──────────────────────────────────────


def test_old_slug_redirects_301(http_client, engine):
    import asyncio
    from db.tables import Collection, CollectionItem, CollectionItemSlugHistory

    async def _setup():
        col = await Collection.select().where(Collection.slug == "blog").first()
        if not col:
            return
        # Create an item with a slug, then add a history entry for an old slug.
        existing = await CollectionItem.select().where(
            CollectionItem.collection == col["id"]
        ).first()
        if not existing:
            item = CollectionItem(
                collection=col["id"], title="Redirect Test", slug="redirect-test",
                data={}, published=True,
            )
            await item.save()
            existing = await CollectionItem.select().where(
                CollectionItem.slug == "redirect-test"
            ).first()
        await CollectionItemSlugHistory(
            item=existing["id"], collection_slug="blog", old_slug="old-redirect-test",
        ).save()

    asyncio.get_event_loop().run_until_complete(_setup())
    resp = http_client.get("/blog/old-redirect-test", follow_redirects=False)
    assert resp.status_code == 301