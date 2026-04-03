# tests/conftest.py
import pytest
from stoolap import Database

from db.schema import init_db


@pytest.fixture
def db():
    """In-memory Stoolap database with schema applied."""
    database = Database.open(":memory:")
    init_db(database)
    return database


class MockHeaders:
    def __init__(self, headers: dict):
        self._h = {k.lower(): v for k, v in headers.items()}

    def get(self, key: str, default=None):
        return self._h.get(key.lower(), default)


class MockRequest:
    def __init__(self, headers: dict | None = None, path: str = "/", session: dict | None = None):
        self.headers = MockHeaders(headers or {})
        self.path = path
        self.session = session or {}
