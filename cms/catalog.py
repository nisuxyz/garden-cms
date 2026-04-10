"""
JinjaX catalog setup and Jinja global helpers.

Call ``init_catalog(jinja_env)`` once after the Litestar app is created
to register the JinjaX extension, component folder, and template globals.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment
from syncwrap import syncwrap

import jinjax

from cms.renderer import set_env
from cms.site_context import _site_dict
from cms.storage import get_backend
from db.tables import Collection, CollectionItem

_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "components"

catalog: jinjax.Catalog | None = None


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
fetch_collection = syncwrap(_fetch_collection_async)


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

    # Share this env with the renderer module so DB-stored templates
    # rendered via from_string() also have JinjaX + globals.
    set_env(jinja_env)

    def _render_card(template_str: str, item: dict[str, Any]) -> str:
        """Render a card template string with item context."""
        tpl = jinja_env.from_string(template_str)
        return tpl.render(item=item, site=_site_dict, media_url=_media_url)

    # Register globals available in all templates (file-based and DB strings).
    jinja_env.globals["site"] = _site_dict
    jinja_env.globals["media_url"] = _media_url
    jinja_env.globals["fetch_collection"] = fetch_collection
    jinja_env.globals["_render_card"] = _render_card

    return catalog
