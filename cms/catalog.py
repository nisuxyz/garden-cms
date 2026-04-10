"""
JinjaX catalog setup and Jinja global helpers.

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

from cms.renderer import set_env
from cms.site_context import _site_dict
from cms.storage import get_backend
from db.tables import Collection, CollectionItem

_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "templates"

catalog: jinjax.Catalog | None = None

# The main event loop reference, set before offloading sync rendering
# to a worker thread so that sync helpers can schedule coroutines on it.
_main_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar(
    "_main_loop", default=None,
)


def provide_catalog() -> jinjax.Catalog:
    """Litestar DI provider — returns the initialised JinjaX catalog."""
    assert catalog is not None, "init_catalog() must be called before providing catalog"
    return catalog


# ── Jinja globals ──────────────────────────────────────────


def _media_url(filename: str) -> str:
    """Resolve a media filename to its public URL."""
    return get_backend().url(filename)


async def _fetch_collection_async(
    slug: str, page: int = 1, limit: int | None = None,
) -> dict[str, Any]:
    """Fetch a collection's items from the DB.

    Returns a dict with keys: collection, items, has_more, next_page.
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
    items = rows[:per_page]

    # Unpack JSON data field into top-level keys for template access.
    for item in items:
        data = item.get("data", {})
        if isinstance(data, str):
            data = json.loads(data) if data else {}
        for k, v in data.items():
            if k not in item:
                item[k] = v

    return {
        "collection": col,
        "items": items,
        "has_more": has_more,
        "next_page": page + 1,
    }


# Sync wrapper so Jinja templates can call it during rendering.
# Template rendering runs in a worker thread (via run_in_executor).
# We schedule the async DB query back on the main event loop with
# run_coroutine_threadsafe, which is safe because the main loop is
# free (it's awaiting the executor future, not blocked).
def fetch_collection(
    slug: str, page: int = 1, limit: int | None = None,
) -> dict[str, Any]:
    loop = _main_loop.get()
    coro = _fetch_collection_async(slug, page, limit)
    if loop is not None and loop.is_running():
        # Called from a worker thread — schedule on the main loop.
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    # No main loop stored (e.g. tests) — run directly.
    return asyncio.run(coro)


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
    # Use that env for all DB-stored template rendering so <Component /> tags work.
    cat_env = catalog.jinja_env

    # The catalog env needs the filesystem loader so {% extends "layout/..." %} works.
    if jinja_env.loader and not cat_env.loader:
        cat_env.loader = jinja_env.loader

    # Share the catalog's env with the renderer module.
    set_env(cat_env)

    def _render_card(template_str: str, item: dict[str, Any]) -> str:
        """Render a card template string with item context."""
        tpl = cat_env.from_string(template_str)
        return tpl.render(item=item, site=_site_dict, media_url=_media_url, __prefix="")

    # Register globals on the catalog's env (used by from_string rendering)
    # and on the original Litestar env (used by file-based template rendering).
    for env in (cat_env, jinja_env):
        env.globals["site"] = _site_dict
        env.globals["media_url"] = _media_url
        env.globals["fetch_collection"] = fetch_collection
        env.globals["_render_card"] = _render_card

    return catalog
