# cms/renderer.py
"""
Rendering utilities for the CMS pipeline.

- Markdown → HTML conversion
- Collection card-list rendering (expanding ``${item.*}`` in card templates)
- Theme wrapper (inject content into base template)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from cms.expressions import ExpressionContext, ResolvedCollection
from db.schema import render_md

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Jinja2 env with filesystem loader — DB string templates can use
# {% extends "layout/base.html" %} because from_string() inherits
# the loader from the environment.
_file_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True
)

_ITEM_EXPR = re.compile(r"\$\{item\.([^}]+)\}")


# ── Card rendering ─────────────────────────────────────────


def render_card(
    card_template: str, item: dict[str, Any], collection_slug: str
) -> str:
    """Render a single card by replacing ``${item.*}`` in *card_template*."""

    def _replace(m: re.Match) -> str:
        field = m.group(1).strip()
        # Check top-level columns first, then the JSON ``data`` blob.
        val = item.get(field)
        if val is None:
            data = item.get("data", {})
            if isinstance(data, str):
                data = json.loads(data) if data else {}
            val = data.get(field, "")
        if val is None:
            val = ""
        # Special handling: render markdown fields in cards.
        if isinstance(val, str) and "\n" in val and len(val) > 200:
            val = render_md(val)
        return str(val)

    return _ITEM_EXPR.sub(_replace, card_template)


def render_card_list(
    rc: ResolvedCollection,
    page: int = 1,
) -> str:
    """Render a collection's items through its card template.

    Returns an HTML fragment including a *Load more* button when
    ``rc.has_more`` is True.
    """
    col = rc.collection
    if not col:
        return ""

    if not rc.items:
        return col.get("empty_template", "")

    card_tpl = col.get("card_template", "")
    slug = col.get("slug", "")
    parts: list[str] = []

    for item in rc.items:
        parts.append(render_card(card_tpl, item, slug))

    html = "\n".join(parts)

    if rc.has_more:
        next_page = page + 1
        html += (
            f'\n<button hx-get="/api/collection/{slug}/feed?page={next_page}" '
            f'hx-swap="outerHTML" hx-target="this">Load more</button>'
        )

    return html


# ── Theme rendering ────────────────────────────────────────


def render_theme(
    base_template: str,
    css: str,
    title: str,
    content_html: str,
    nav_items: list[dict[str, str]],
) -> str:
    """Render a themed page.

    The theme's *base_template* (a Jinja2 string stored in the DB) should
    ``{% extends "layout/base.html" %}`` and override ``{% block body %}``
    and optionally ``{% block head %}``.  Using ``_file_env.from_string``
    gives the DB string access to filesystem templates for ``{% extends %}``.
    """
    extra_head = Markup(f"<style>{css}</style>") if css else ""
    tpl = _file_env.from_string(base_template)
    return tpl.render(
        title=title,
        content=Markup(content_html),
        nav_items=nav_items,
        extra_head=extra_head,
    )


# ── Expand collection placeholders ─────────────────────────


def expand_collections(html: str, ctx: ExpressionContext) -> str:
    """Replace ``<!--collection:…-->`` placeholders with rendered card HTML."""
    for placeholder, rc in ctx.collection_blocks:
        card_html = render_card_list(rc)
        html = html.replace(placeholder, card_html)
    return html
