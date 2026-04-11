"""
JinjaX catalog setup, Jinja globals, and collection data access.

Call ``init_catalog(jinja_env)`` once after the Litestar app is created
to register the JinjaX extension, component folder, and template globals.
"""
from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from jinja2 import Environment

import jinjax

import cms.renderer as _renderer
from cms.site_context import _site_dict
from cms.storage import get_backend
from db.tables import Collection, CollectionItem

_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "templates"

catalog: jinjax.Catalog | None = None

# Captured by ``render()`` before it offloads to a worker thread.
# Sync helpers running inside that thread use it to schedule coroutines
# back on the main loop via ``run_coroutine_threadsafe``.
_main_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar(
    "_main_loop", default=None,
)


def provide_catalog() -> jinjax.Catalog:
    """Litestar DI provider — returns the initialised JinjaX catalog."""
    assert catalog is not None, "init_catalog() must be called before providing catalog"
    return catalog


# ── Collection data access ─────────────────────────────────


def _unpack_items(rows: list[dict]) -> list[dict[str, Any]]:
    """Unpack JSON ``data`` fields into top-level keys on each row."""
    for item in rows:
        data = item.get("data", {})
        if isinstance(data, str):
            data = json.loads(data) if data else {}
        for k, v in data.items():
            if k not in item:
                item[k] = v
    return rows


async def fetch_collection_async(
    slug: str, page: int = 1, limit: int | None = None,
) -> dict[str, Any]:
    """Fetch a collection and its published items from the DB.

    Returns ``{"collection", "items", "has_more", "next_page"}``.
    Used by both the JinjaX ``<CollectionFeed>`` component (via sync
    wrapper) and the HTMX pagination endpoint in ``cms/engine.py``.
    """
    col = (
        await Collection.select()
        .where(Collection.slug == slug)
        .first()
    )
    if col is None:
        return {"collection": None, "items": [], "has_more": False, "next_page": 2}

    per_page = limit or col.get("items_per_page", 10)
    offset = (page - 1) * per_page

    rows = await (
        CollectionItem.select()
        .where(CollectionItem.collection == col["id"])
        .where(CollectionItem.published.eq(True))
        .order_by(CollectionItem.created_at, ascending=False)
        .offset(offset)
        .limit(per_page + 1)
    )
    has_more = len(rows) > per_page
    items = _unpack_items(rows[:per_page])

    return {
        "collection": col,
        "items": items,
        "has_more": has_more,
        "next_page": page + 1,
    }


def fetch_collection(
    slug: str, page: int = 1, limit: int | None = None,
) -> dict[str, Any]:
    """Sync wrapper for use inside Jinja templates during rendering.

    When called from the worker thread (``render()`` offloads via
    ``run_in_executor``), schedules the coroutine back on the main loop.
    """
    loop = _main_loop.get()
    coro = fetch_collection_async(slug, page, limit)
    if loop is not None and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    # No running loop (tests, startup) — safe to use asyncio.run.
    return asyncio.run(coro)


# ── Jinja globals ──────────────────────────────────────────


def _media_url(filename: str) -> str:
    """Resolve a media filename to its public URL."""
    return get_backend().url(filename)


# ── Catalog init ───────────────────────────────────────────


def init_catalog(jinja_env: Environment) -> jinjax.Catalog:
    """Register JinjaX on *jinja_env* and return the configured Catalog."""
    global catalog

    catalog = jinjax.Catalog(
        jinja_env=jinja_env,
        use_cache=True,
        auto_reload=True,
    )
    catalog.add_folder(_COMPONENTS_DIR)

    # The catalog creates its own internal env with JinjaX preprocessing.
    cat_env = catalog.jinja_env

    # The catalog env needs the filesystem loader so {% extends %} works.
    if jinja_env.loader and not cat_env.loader:
        cat_env.loader = jinja_env.loader

    # Share the catalog's env with the renderer module.
    _renderer._jinja_env = cat_env

    # JinjaX forces StrictUndefined — override to lenient so CMS templates
    # gracefully handle missing fields (e.g. {{ item.tags }} when tags is absent).
    from jinja2 import Undefined
    cat_env.undefined = Undefined

    # ``__prefix`` is required by JinjaX's preprocessor output — set once
    # as a global so every from_string() render picks it up automatically.
    cat_env.globals["__prefix"] = ""

    def _render_card(template_str: str, item: dict[str, Any]) -> str:
        """Render a card template string with ``item`` in context.

        Called from inside JinjaX components (already in the worker thread),
        so uses ``render_sync`` directly.
        """
        merged = _renderer.unpack_item_data(item)
        return _renderer.render_sync(template_str, {"item": merged})

    # Register globals on both envs.
    for env in (cat_env, jinja_env):
        env.globals["site"] = _site_dict
        env.globals["media_url"] = _media_url
        env.globals["fetch_collection"] = fetch_collection
        env.globals["_render_card"] = _render_card

    return catalog
