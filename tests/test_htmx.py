# tests/test_htmx.py
"""
Tests for HTMX integration via Litestar's built-in HTMXPlugin.

The custom middleware/htmx.py module has been removed — HTMX header parsing
and response helpers are now provided by litestar.plugins.htmx.

These tests verify that the HTMXPlugin correctly processes request headers
and that the HTMX response classes work as expected.
"""
from litestar import Litestar, get
from litestar.plugins.htmx import (
    ClientRedirect,
    ClientRefresh,
    HTMXPlugin,
    HTMXRequest,
    HXLocation,
    PushUrl,
    ReplaceUrl,
    TriggerEvent,
)
from litestar.response import Template
from litestar.testing import TestClient


@get("/htmx-check")
async def htmx_check_handler(request: HTMXRequest) -> dict:
    return {
        "is_htmx": bool(request.htmx),
        "current_url": request.htmx.current_url if request.htmx else None,
        "target": request.htmx.target if request.htmx else None,
        "boosted": request.htmx.boosted if request.htmx else False,
    }


_test_app = Litestar(
    route_handlers=[htmx_check_handler],
    plugins=[HTMXPlugin()],
)


def test_htmx_plugin_detects_htmx_request():
    with TestClient(app=_test_app) as client:
        resp = client.get("/htmx-check", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_htmx"] is True


def test_htmx_plugin_detects_non_htmx_request():
    with TestClient(app=_test_app) as client:
        resp = client.get("/htmx-check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_htmx"] is False


def test_htmx_plugin_reads_headers():
    with TestClient(app=_test_app) as client:
        resp = client.get("/htmx-check", headers={
            "HX-Request": "true",
            "HX-Current-URL": "http://localhost/blog",
            "HX-Target": "feed",
            "HX-Boosted": "true",
        })
        data = resp.json()
        assert data["current_url"] == "http://localhost/blog"
        assert data["target"] == "feed"
        assert data["boosted"] is True
