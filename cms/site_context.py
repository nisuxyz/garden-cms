"""
In-memory cache for ContentBlock key/value pairs.

All ContentBlocks are loaded at startup and kept in a module-level dict.
CRUD operations call ``invalidate_site_dict()`` to refresh the cache.
The cache is intentionally simple — ContentBlocks are small KV pairs.
"""
from __future__ import annotations

from cms.storage import get_backend
from db.tables import ContentBlock

_site_dict: dict[str, str] = {}


async def load_site_dict() -> None:
    """Query all ContentBlocks and populate ``_site_dict``."""
    rows = await ContentBlock.select()
    new: dict[str, str] = {}
    backend = get_backend()
    for row in rows:
        key = row["key"]
        block_type = row.get("block_type", "text")
        value = row.get("value", "")
        if block_type == "image" and value:
            new[key] = backend.url(value)
        else:
            # text and markdown blocks stored as-is (no markdown rendering)
            new[key] = value
    # Mutate in-place so Jinja globals keep a live reference.
    _site_dict.clear()
    _site_dict.update(new)


async def invalidate_site_dict() -> None:
    """Reload the site dict from the database."""
    await load_site_dict()


def get_site_dict() -> dict[str, str]:
    """Return the cached site dict (sync, safe for Jinja context)."""
    return _site_dict
