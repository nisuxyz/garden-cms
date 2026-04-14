"""
In-memory cache for ContentBlock key/value pairs.

All ContentBlocks are loaded at startup and kept in a module-level dict.
CRUD operations call ``invalidate_site_dict()`` to refresh the cache.

HTML blocks are rendered through Jinja so ``{{ media_url("file") }}``
and other globals resolve at cache-load time.

Stateless mode
──────────────
Set the ``STATELESS`` environment variable to ``true`` (or ``1`` / ``yes``)
to reload content blocks from the database before every page render.
This avoids stale in-memory state in serverless or multi-instance
deployments where each request may hit a different process.
"""
from __future__ import annotations

import os

from cms.storage import get_backend
from db.tables import ContentBlock
from markupsafe import Markup

_site_dict: dict[str, str] = {}

STATELESS: bool = os.getenv("STATELESS", "").lower() in ("1", "true", "yes")


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
            try:
                new[key] = Markup(render_sync(value))
            except Exception:
                new[key] = Markup(value)
        else:
            new[key] = value
    # Mutate in-place so Jinja globals keep a live reference.
    _site_dict.clear()
    _site_dict.update(new)


async def ensure_fresh_site_dict() -> None:
    """Reload ``_site_dict`` from the database when running stateless.

    Call this before rendering a public page.  In stateful mode (the
    default) this is a no-op — the dict stays current via startup load
    and CRUD invalidation.
    """
    if STATELESS:
        await load_site_dict()


async def invalidate_site_dict() -> None:
    """Reload the site dict from the database."""
    await load_site_dict()


def get_site_dict() -> dict[str, str]:
    """Return the cached site dict (sync, safe for Jinja context)."""
    return _site_dict
