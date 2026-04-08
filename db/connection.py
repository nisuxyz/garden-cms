# db/connection.py
"""
Database lifecycle management for Piccolo + Litestar.

Provides an async lifespan context-manager that opens/closes the
Piccolo connection pool and ensures seed data exists.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar
from piccolo.engine.postgres import PostgresEngine


async def init_db() -> None:
    """Seed default CMS data (themes, pages, content blocks, collections).

    Implemented in commit 7 — currently a no-op placeholder.
    """


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    """Start the Piccolo connection pool on startup, close on shutdown."""
    from piccolo_conf import DB  # noqa: WPS433 — deferred to allow env loading

    engine: PostgresEngine = DB

    await engine.start_connection_pool(max_inactive_connection_lifetime=1)
    try:
        await init_db()
        yield
    finally:
        await engine.close_connection_pool()
