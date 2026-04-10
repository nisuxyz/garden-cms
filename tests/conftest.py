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

    # Load site context cache and set up Jinja globals for tests.
    from cms.site_context import load_site_dict
    await load_site_dict()

    from cms.renderer import get_env
    from cms.site_context import _site_dict
    from cms.storage import get_backend
    env = get_env()
    env.globals["site"] = _site_dict
    env.globals["media_url"] = lambda f: get_backend().url(f)

    yield test_engine

    # Cleanup
    try:
        os.unlink(tmp.name)
    except OSError:
        pass
