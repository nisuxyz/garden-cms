# tests/conftest.py
import pytest
import pytest_asyncio
from stoolap import AsyncDatabase

from db.schema import init_db


@pytest_asyncio.fixture
async def db():
    """In-memory async Stoolap database with schema applied."""
    database = await AsyncDatabase.open(":memory:")
    await init_db(database)
    yield database
    await database.close()
