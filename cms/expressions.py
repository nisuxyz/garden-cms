# cms/expressions.py
"""
Parse and resolve ``${...}`` expressions in CMS markdown bodies.

Supported forms
───────────────
  ${site.key}               → ContentBlock value (text/markdown/image)
  ${collection.slug}        → full paginated collection (cards)
  ${collection.slug:N}      → N most-recent items
  ${collection.slug:featured:N} → N featured items
  ${item.field}             → field from the current CollectionItem context
  ${media.filename}         → <img> tag for an uploaded MediaFile

Expressions inside fenced code blocks (``` … ```) are left untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from db.schema import render_md
from db.tables import Collection, CollectionItem, ContentBlock, MediaFile

# ── Tokeniser ──────────────────────────────────────────────

# Matches ``` fenced blocks (greedy) followed by ${...} outside them.
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_EXPR = re.compile(r"\$\{([^}]+)\}")


@dataclass
class ResolvedCollection:
    """Carries everything the renderer needs to emit a card list."""

    collection: dict[str, Any]
    items: list[dict[str, Any]]
    has_more: bool = False
    next_page: int = 2


@dataclass
class ExpressionContext:
    """Runtime context available while resolving expressions."""

    # When rendering a detail page, ``item`` is the current CollectionItem row.
    item: dict[str, Any] | None = None
    # Accumulates resolved collection blocks so the renderer can emit HTML.
    collection_blocks: list[tuple[str, ResolvedCollection]] = field(
        default_factory=list
    )


# ── Helpers ────────────────────────────────────────────────


def _split_preserving_code(text: str) -> list[tuple[bool, str]]:
    """Split *text* into ``(is_code, fragment)`` pairs.

    Code-fenced regions are marked ``is_code=True`` so the resolver
    can skip them.
    """
    parts: list[tuple[bool, str]] = []
    last_end = 0
    for m in _CODE_FENCE.finditer(text):
        if m.start() > last_end:
            parts.append((False, text[last_end : m.start()]))
        parts.append((True, m.group()))
        last_end = m.end()
    if last_end < len(text):
        parts.append((False, text[last_end:]))
    return parts


# ── Resolvers ──────────────────────────────────────────────


async def _resolve_site(key: str) -> str:
    """Resolve ``${site.<key>}`` → ContentBlock value."""
    row = (
        await ContentBlock.select()
        .where(ContentBlock.key == key)
        .first()
        
    )
    if row is None:
        return ""
    if row["block_type"] == "markdown":
        return render_md(row["value"])
    if row["block_type"] == "image":
        alt = key.replace("_", " ").replace(".", " ")
        return f'<img src="/media/{row["value"]}" alt="{alt}">'
    return row["value"]


async def _resolve_collection(
    parts: list[str],
) -> ResolvedCollection:
    """Resolve ``${collection.<slug>[:<filter>][:<limit>]}``."""
    slug = parts[0]
    col = (
        await Collection.select()
        .where(Collection.slug == slug)
        .first()
        
    )
    if col is None:
        return ResolvedCollection(collection={}, items=[])

    query = (
        CollectionItem.select()
        .where(CollectionItem.collection == col["id"])
        .where(CollectionItem.published.eq(True))
    )

    limit: int | None = None
    featured_only = False

    for p in parts[1:]:
        if p == "featured":
            featured_only = True
        elif p.isdigit():
            limit = int(p)

    if featured_only:
        query = query.where(CollectionItem.featured.eq(True))

    query = query.order_by(CollectionItem.created_at, ascending=False)

    # Fetch one extra to know if there are more pages.
    fetch_limit = (limit or col["items_per_page"]) + 1
    rows = await query.limit(fetch_limit)

    has_more = len(rows) > (limit or col["items_per_page"])
    items = rows[: limit or col["items_per_page"]]

    return ResolvedCollection(
        collection=col, items=items, has_more=has_more, next_page=2
    )


async def _resolve_media(filename: str) -> str:
    """Resolve ``${media.<filename>}`` → ``<img>`` tag."""
    row = (
        await MediaFile.select()
        .where(MediaFile.filename == filename)
        .first()
        
    )
    if row is None:
        return ""
    alt = row.get("alt_text") or row["original_name"]
    return f'<img src="/media/{row["filename"]}" alt="{alt}">'


def _resolve_item(field_name: str, ctx: ExpressionContext) -> str:
    """Resolve ``${item.<field>}`` from the current item context."""
    if ctx.item is None:
        return ""
    # ``data`` is the JSON blob; also check top-level columns.
    value = ctx.item.get(field_name) or ctx.item.get("data", {}).get(field_name, "")
    if value is None:
        return ""
    return str(value)


# ── Main entry point ──────────────────────────────────────


async def resolve_expressions(
    text: str,
    ctx: ExpressionContext | None = None,
) -> str:
    """Replace every ``${…}`` in *text* with its resolved value.

    Code-fenced regions are preserved verbatim.  Collection placeholders
    are stored in *ctx.collection_blocks* for the renderer to expand
    later (they need HTML card rendering which depends on the collection's
    card_template).
    """
    if ctx is None:
        ctx = ExpressionContext()

    fragments = _split_preserving_code(text)
    out_parts: list[str] = []

    for is_code, fragment in fragments:
        if is_code:
            out_parts.append(fragment)
            continue

        last = 0
        resolved = []
        for m in _EXPR.finditer(fragment):
            resolved.append(fragment[last : m.start()])
            expr = m.group(1).strip()
            resolved.append(await _resolve_single(expr, ctx))
            last = m.end()
        resolved.append(fragment[last:])
        out_parts.append("".join(resolved))

    return "".join(out_parts)


async def _resolve_single(expr: str, ctx: ExpressionContext) -> str:
    """Dispatch a single expression string to the right resolver."""
    if expr.startswith("site."):
        key = expr[len("site.") :]
        return await _resolve_site(key)

    if expr.startswith("collection."):
        parts = expr[len("collection.") :].split(":")
        rc = await _resolve_collection(parts)
        # Use a unique placeholder the renderer will swap for card HTML.
        placeholder = f"<!--collection:{parts[0]}:{len(ctx.collection_blocks)}-->"
        ctx.collection_blocks.append((placeholder, rc))
        return placeholder

    if expr.startswith("media."):
        filename = expr[len("media.") :]
        return await _resolve_media(filename)

    if expr.startswith("item."):
        field_name = expr[len("item.") :]
        return _resolve_item(field_name, ctx)

    # Unknown expression — return empty.
    return ""
