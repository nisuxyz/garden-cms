# tests/test_auth.py
import pytest
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException

from middleware.auth import admin_guard


class _FakeScope:
    """Minimal scope-like object for testing the guard."""

    def __init__(self, session: dict | None = None):
        self._session = session or {}

    @property
    def session(self) -> dict:
        return self._session


def _make_connection(session: dict | None = None) -> _FakeScope:
    return _FakeScope(session)


def test_guard_raises_without_session():
    conn = _make_connection({})
    with pytest.raises(NotAuthorizedException):
        admin_guard(conn, None)  # type: ignore[arg-type]


def test_guard_passes_with_valid_session():
    conn = _make_connection({"admin_authenticated": True})
    # Should not raise
    admin_guard(conn, None)  # type: ignore[arg-type]


def test_guard_raises_with_false_session():
    conn = _make_connection({"admin_authenticated": False})
    with pytest.raises(NotAuthorizedException):
        admin_guard(conn, None)  # type: ignore[arg-type]
