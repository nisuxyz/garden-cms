# cms/renderer.py
"""
Rendering utilities for the CMS pipeline.

- Markdown → HTML conversion
- Collection card-list rendering (expanding ``${item.*}`` in card templates)
- Theme wrapper (inject content into base template)
"""
from __future__ import annotations

import re
from typing import Any

from jinja2 import BaseLoader, Environment
from markupsafe import Markup

from cms.expressions import ExpressionContext, ResolvedCollection
from db.schema import render_md

# Minimal Jinja2 env for rendering theme base templates from DB strings.
_jinja_env = Environment(loader=BaseLoader(), autoescape=True)

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
            val = item.get("data", {}).get(field, "")
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
    """Inject *content_html* into *base_template* (Jinja2 string).

    The base template may use:
      {{ title }}      — page title
      {{ content }}    — rendered page HTML (marked safe)
      {{ nav_items }}  — list of {title, slug, url} dicts
      {{ theme_css }}  — theme CSS string
    """
    tpl = _jinja_env.from_string(base_template)
    return tpl.render(
        title=title,
        content=Markup(content_html),
        nav_items=nav_items,
        theme_css=Markup(css),
    )


# ── Expand collection placeholders ─────────────────────────


def expand_collections(html: str, ctx: ExpressionContext) -> str:
    """Replace ``<!--collection:…-->`` placeholders with rendered card HTML."""
    for placeholder, rc in ctx.collection_blocks:
        card_html = render_card_list(rc)
        html = html.replace(placeholder, card_html)
    return html
