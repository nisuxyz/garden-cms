"""
In-memory cache for ContentBlock key/value pairs.

All ContentBlocks are loaded at startup and kept in a module-level dict.
CRUD operations call ``invalidate_site_dict()`` to refresh the cache.
The cache is intentionally simple — ContentBlocks are small KV pairs.

HTML blocks are rendered through Jinja so ``{{ media_url("file") }}``
and other globals resolve at cache-load time.
"""
from __future__ import annotations

from cms.storage import get_backend
from db.tables import ContentBlock
from markupsafe import Markup

_site_dict: dict[str, str] = {}


async def load_site_dict() -> None:
    """Query all ContentBlocks and populate ``_site_dict``."""
    from cms.renderer import render_sync

    rows = await ContentBlock.select()
    new: dict[str, str] = {}
    backend = get_backend()
    for row in rows:
        key = row["key"]
        block_type = row.get("block_type", "text")
        value = row.get("value", "")
        if block_type == "image" and value:
            new[key] = backend.url(value)
        elif block_type == "html" and value:
            # Render through Jinja so media_url() etc. resolve.
            # Wrap in Markup so {{ site.key }} won't be auto-escaped.
            try:
                new[key] = Markup(render_sync(value))
            except Exception:
                new[key] = Markup(value)
        else:
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
