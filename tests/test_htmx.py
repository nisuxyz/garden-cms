# tests/test_htmx.py
import json
import pytest
from bustapi import Middleware
from bustapi.http.response import Response
from middleware.htmx import (
    HTMXDetails, HTMXMiddleware,
    hx_location, hx_push_url, hx_redirect,
    hx_refresh, hx_replace_url, hx_trigger,
)
from tests.conftest import MockRequest


def test_htmx_details_detects_htmx_request():
    req = MockRequest(headers={"HX-Request": "true"})
    assert HTMXDetails(req).is_htmx is True


def test_htmx_details_non_htmx():
    assert HTMXDetails(MockRequest()).is_htmx is False


def test_htmx_details_all_headers():
    req = MockRequest(headers={
        "HX-Request": "true",
        "HX-Request-Type": "partial",
        "HX-Current-URL": "http://localhost/blog",
        "HX-Source": "btn",
        "HX-Target": "feed",
        "HX-Boosted": "true",
        "HX-History-Restore-Request": "true",
        "Last-Event-ID": "42",
    })
    d = HTMXDetails(req)
    assert d.request_type == "partial"
    assert d.current_url == "http://localhost/blog"
    assert d.source == "btn"
    assert d.target == "feed"
    assert d.boosted is True
    assert d.history_restore is True
    assert d.last_event_id == "42"


def test_htmx_details_defaults():
    d = HTMXDetails(MockRequest())
    assert d.request_type is None
    assert d.boosted is False
    assert d.history_restore is False
    assert d.last_event_id is None


def test_middleware_attaches_htmx_attr():
    mw = HTMXMiddleware()
    req = MockRequest(headers={"HX-Request": "true"})
    assert mw.process_request(req) is None
    assert hasattr(req, "htmx")
    assert req.htmx.is_htmx is True


def test_middleware_adds_vary_header():
    mw = HTMXMiddleware()
    req = MockRequest()
    mw.process_request(req)
    resp = mw.process_response(req, Response("ok"))
    assert resp.headers.get("Vary") == "HX-Request"


def test_hx_redirect():
    assert hx_redirect(Response("ok"), "/new").headers.get("HX-Redirect") == "/new"


def test_hx_location_simple():
    assert hx_location(Response("ok"), "/new").headers.get("HX-Location") == "/new"


def test_hx_location_with_opts():
    resp = hx_location(Response("ok"), "/new", target="#content")
    payload = json.loads(resp.headers.get("HX-Location"))
    assert payload["path"] == "/new"
    assert payload["target"] == "#content"


def test_hx_refresh():
    assert hx_refresh(Response("ok")).headers.get("HX-Refresh") == "true"


def test_hx_push_url():
    assert hx_push_url(Response("ok"), "/blog/post").headers.get("HX-Push-Url") == "/blog/post"


def test_hx_replace_url():
    assert hx_replace_url(Response("ok"), "/blog/new").headers.get("HX-Replace-Url") == "/blog/new"


def test_hx_trigger_simple():
    assert hx_trigger(Response("ok"), "saved").headers.get("HX-Trigger") == "saved"


def test_hx_trigger_with_detail():
    payload = json.loads(hx_trigger(Response("ok"), "saved", id=1).headers.get("HX-Trigger"))
    assert payload == {"saved": {"id": 1}}
