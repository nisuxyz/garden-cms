# cms/renderer.py
"""
Rendering utilities for the CMS pipeline.

- Jinja template-string rendering (DB-stored page bodies, card templates)
- Theme wrapper (inject content into base template)
"""
from __future__ import annotations

import asyncio
import contextvars
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Jinja2 env with filesystem loader — DB string templates can use
# {% extends "layout/base.html" %} because from_string() inherits
# the loader from the environment.
_file_env: Environment | None = None


def get_env() -> Environment:
    """Return the shared Jinja2 env (created lazily, then cached)."""
    global _file_env
    if _file_env is None:
        _file_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True,
        )
    return _file_env


def set_env(env: Environment) -> None:
    """Replace the module-level env (called from app init)."""
    global _file_env
    _file_env = env


# ── Template-string rendering ──────────────────────────────


def render_template_string(source: str, context: dict[str, Any] | None = None) -> str:
    """Render a Jinja template *source* string with *context*.

    The env has JinjaX registered (if ``init_catalog`` was called),
    so ``<CollectionFeed slug="blog" />`` etc. work inside source.
    ``__prefix`` is required by JinjaX's preprocessor output.
    """
    env = get_env()
    tpl = env.from_string(source)
    ctx = context or {}
    ctx.setdefault("__prefix", "")
    return tpl.render(ctx)


async def render_template_string_async(
    source: str, context: dict[str, Any] | None = None,
) -> str:
    """Async version — offloads sync Jinja rendering to a worker thread.

    This keeps the main event loop free so that sync helpers like
    ``fetch_collection`` can schedule DB coroutines back on it via
    ``run_coroutine_threadsafe``.
    """
    from cms.catalog import _main_loop  # avoid circular import at module level

    loop = asyncio.get_running_loop()
    _main_loop.set(loop)

    # Copy the current context so the ContextVar is visible in the thread.
    ctx = contextvars.copy_context()
    return await loop.run_in_executor(
        None, ctx.run, render_template_string, source, context,
    )


def render_card(card_template: str, item: dict[str, Any]) -> str:
    """Render a card template with ``item`` in context.

    JSON ``data`` fields are unpacked to top-level for convenience.
    """
    data = item.get("data", {})
    if isinstance(data, str):
        data = json.loads(data) if data else {}
    merged = {**item}
    for k, v in data.items():
        if k not in merged:
            merged[k] = v
    return render_template_string(card_template, {"item": merged})


# ── Theme rendering ────────────────────────────────────────


def render_theme(
    base_template: str,
    css: str,
    title: str,
    content_html: str,
    nav_items: list[dict[str, str]],
    site_head: str | None = None,
) -> str:
    """Render a themed page.

    The theme's *base_template* (a Jinja2 string stored in the DB) should
    ``{% extends "layout/base.html" %}`` and override ``{% block body %}``
    and optionally ``{% block head %}``.
    """
    extra_head = Markup(f"<style>{css}</style>") if css else ""
    env = get_env()
    tpl = env.from_string(base_template)
    ctx: dict[str, Any] = {
        "__prefix": "",
        "title": title,
        "content": Markup(content_html),
        "nav_items": nav_items,
        "extra_head": extra_head,
    }
    if site_head:
        ctx["extra_admin_head"] = Markup(site_head)
    return tpl.render(ctx)
