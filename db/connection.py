# db/connection.py
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar
from litestar.datastructures import State
from stoolap import AsyncDatabase

from db.schema import init_db


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    """Open the AsyncDatabase on startup, close it on shutdown."""
    url = os.getenv("DATABASE_URL", "./data/site.db")
    if url != ":memory:" and not url.startswith("file://"):
        parent = os.path.dirname(url)
        if parent:
            os.makedirs(parent, exist_ok=True)
    db = await AsyncDatabase.open(url)
    app.state.db = db
    await init_db(db)
    try:
        yield
    finally:
        await db.close()


async def provide_db(state: State) -> AsyncDatabase:
    """Litestar dependency — provides the AsyncDatabase from app state."""
    return state.db
