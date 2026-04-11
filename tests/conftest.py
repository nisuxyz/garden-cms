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
