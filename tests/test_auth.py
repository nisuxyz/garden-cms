# tests/test_auth.py
from bustapi.http.response import Response
from middleware.auth import AdminAuthMiddleware
from tests.conftest import MockRequest


def test_non_admin_path_passes():
    mw = AdminAuthMiddleware()
    assert mw.process_request(MockRequest(path="/blog")) is None


def test_login_path_passes():
    mw = AdminAuthMiddleware()
    assert mw.process_request(MockRequest(path="/admin/login")) is None


def test_admin_without_session_redirects():
    mw = AdminAuthMiddleware()
    result = mw.process_request(MockRequest(path="/admin", session={}))
    assert result is not None
    assert result.status_code == 302
    assert result.headers.get("Location") == "/admin/login"


def test_admin_with_valid_session_passes():
    mw = AdminAuthMiddleware()
    req = MockRequest(path="/admin", session={"admin_authenticated": True})
    assert mw.process_request(req) is None


def test_admin_posts_without_session_redirects():
    mw = AdminAuthMiddleware()
    result = mw.process_request(MockRequest(path="/admin/posts", session={}))
    assert result is not None and result.status_code == 302


def test_process_response_is_passthrough():
    mw = AdminAuthMiddleware()
    resp = Response("ok")
    assert mw.process_response(MockRequest(), resp) is resp
