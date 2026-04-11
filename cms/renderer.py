# cms/renderer.py
"""
Unified rendering for the CMS pipeline.

All template rendering goes through two entry points:

- ``render(source, context)``      — async, for route handlers / engine
- ``render_sync(source, context)`` — sync, for Jinja globals running inside
                                      the worker thread (e.g. ``_render_card``)
                                      and for startup code (``load_site_dict``)

Both use the JinjaX catalog's Jinja env so ``<Component />`` tags,
``{{ site.key }}``, ``{{ media_url("f") }}`` etc. all resolve.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
from typing import Any

from markupsafe import Markup

# ── Module-level env accessor ──────────────────────────────

# Set by ``init_catalog()`` in cms/catalog.py to the catalog's internal
# Jinja env (which has the JinjaX preprocessing extension).
_jinja_env = None


def _get_env():
    if _jinja_env is None:
        raise RuntimeError("init_catalog() must be called before rendering")
    return _jinja_env


# ── Core rendering ─────────────────────────────────────────


def render_sync(source: str, context: dict[str, Any] | None = None) -> str:
    """Render a Jinja/JinjaX template *source* string synchronously.

    Safe to call from:
    - inside the worker thread (Jinja globals like ``_render_card``)
    - startup code that runs before the event loop (``load_site_dict``)
    """
    env = _get_env()
    tpl = env.from_string(source)
    return tpl.render(context or {})


async def render(source: str, context: dict[str, Any] | None = None) -> str:
    """Render a Jinja/JinjaX template *source* string asynchronously.

    Offloads the synchronous Jinja render to a worker thread so the main
    event loop stays free.  Sync helpers (``fetch_collection``) can then
    call back to the main loop via ``run_coroutine_threadsafe``.
    """
    from cms.catalog import _main_loop  # deferred to avoid circular import

    loop = asyncio.get_running_loop()
    _main_loop.set(loop)

    ctx = contextvars.copy_context()
    return await loop.run_in_executor(
        None, ctx.run, render_sync, source, context,
    )


# ── Convenience wrappers ──────────────────────────────────


def unpack_item_data(item: dict[str, Any]) -> dict[str, Any]:
    """Unpack JSON ``data`` field into top-level keys for template access."""
    data = item.get("data", {})
    if isinstance(data, str):
        data = json.loads(data) if data else {}
    merged = {**item}
    for k, v in data.items():
        if k not in merged:
            merged[k] = v
    return merged


async def render_themed(
    base_template: str,
    css: str,
    title: str,
    content_html: str,
    nav_items: list[dict[str, str]],
    site_head: str | None = None,
) -> str:
    """Wrap *content_html* in a theme's base template.

    The theme template typically ``{% extends "layout/base.html" %}``.
    """
    extra_head = Markup(f"<style>{css}</style>") if css else ""
    ctx: dict[str, Any] = {
        "title": title,
        "content": Markup(content_html),
        "nav_items": nav_items,
        "extra_head": extra_head,
    }
    if site_head:
        ctx["extra_admin_head"] = Markup(site_head)
    return await render(base_template, ctx)
