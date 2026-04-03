# db/connection.py
import os

from stoolap import Database

_db: Database | None = None


def get_db() -> Database:
    """Return the singleton Stoolap database, opening it on first call."""
    global _db
    if _db is None:
        url = os.getenv("DATABASE_URL", "./data/site.db")
        if url != ":memory:" and not url.startswith("file://"):
            parent = os.path.dirname(url)
            if parent:
                os.makedirs(parent, exist_ok=True)
        _db = Database.open(url)
    return _db
