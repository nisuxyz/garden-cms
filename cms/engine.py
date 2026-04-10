# cms/engine.py
"""
High-level CMS page processing pipeline.

    resolve_page  → fetch a Page row by slug (or homepage flag)
    render_page   → full pipeline: expressions → markdown → theme
    render_item   → render a CollectionItem detail page
    get_nav_items → navigation items for the active theme
"""
from __future__ import annotations

from typing import Any

from cms.expressions import ExpressionContext, resolve_expressions
from cms.renderer import expand_collections, render_card_list, render_theme
from db.schema import render_md
from db.tables import (
    Collection,
    CollectionItem,
    CollectionItemSlugHistory,
    Page,
    SiteSettings,
    Theme,
)


async def get_active_theme() -> dict[str, Any] | None:
    """Return the currently active Theme row (dict), or ``None``."""
    return (
        await Theme.select()
        .where(Theme.active.eq(True))
        .first()
        
    )


async def get_nav_items() -> list[dict[str, str]]:
    """Return pages marked ``show_in_nav`` ordered by ``nav_order``."""
    rows = (
        await Page.select(Page.title, Page.slug, Page.is_homepage)
        .where(Page.published.eq(True))
        .where(Page.show_in_nav.eq(True))
        .order_by(Page.nav_order)
        
    )
    items = []
    for r in rows:
        url = "/" if r["is_homepage"] else f"/{r['slug']}"
        items.append({"title": r["title"], "slug": r["slug"], "url": url})
    return items


async def resolve_page(slug: str) -> dict[str, Any] | None:
    """Fetch a published Page by *slug*."""
    return (
        await Page.select()
        .where(Page.slug == slug)
        .where(Page.published.eq(True))
        .first()
        
    )


async def resolve_homepage() -> dict[str, Any] | None:
    """Fetch the published homepage."""
    return (
        await Page.select()
        .where(Page.is_homepage.eq(True))
        .where(Page.published.eq(True))
        .first()
        
    )


async def _get_site_head() -> str | None:
    """Load the site_head setting (extra HTML for <head>)."""
    row = await (
        SiteSettings.select(SiteSettings.value)
        .where(SiteSettings.key == "site_head")
        .first()
    )
    val = (row.get("value", "") or "") if row else ""
    return val or None


async def render_page(page: dict[str, Any]) -> str:
    """Full pipeline: expressions → markdown → expand collections → theme.

    Returns a complete HTML document string.
    """
    ctx = ExpressionContext()

    # 1. Resolve ${} expressions in the page markdown body.
    processed_md = await resolve_expressions(page["body_md"], ctx)

    # 2. Convert markdown to HTML.
    content_html = render_md(processed_md)

    # 3. Expand collection placeholders into rendered card HTML.
    content_html = expand_collections(content_html, ctx)

    # 4. Wrap in theme.
    theme = None
    if page.get("theme"):
        theme = (
            await Theme.select()
            .where(Theme.id == page["theme"])
            .first()
            
        )
    if theme is None:
        theme = await get_active_theme()
    if theme is None:
        # Fallback: return raw content without a theme wrapper.
        return content_html

    nav = await get_nav_items()
    site_head = await _get_site_head()

    return render_theme(
        base_template=theme["base_template"],
        css=theme.get("css", ""),
        title=page["title"],
        content_html=content_html,
        nav_items=nav,
        site_head=site_head,
    )


# ── Collection item detail ─────────────────────────────────


async def resolve_collection_item(
    collection_slug: str, item_slug: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return ``(collection, item)`` or ``(None, None)``."""
    col = (
        await Collection.select()
        .where(Collection.slug == collection_slug)
        .first()
        
    )
    if col is None:
        return None, None

    item = (
        await CollectionItem.select()
        .where(CollectionItem.collection == col["id"])
        .where(CollectionItem.slug == item_slug)
        .where(CollectionItem.published.eq(True))
        .first()
        
    )
    return col, item


async def resolve_slug_redirect(
    collection_slug: str, item_slug: str
) -> str | None:
    """Check slug history; return new URL path if a redirect is found."""
    row = (
        await CollectionItemSlugHistory.select(
            CollectionItemSlugHistory.item,
            CollectionItemSlugHistory.collection_slug,
        )
        .where(CollectionItemSlugHistory.collection_slug == collection_slug)
        .where(CollectionItemSlugHistory.old_slug == item_slug)
        .first()
        
    )
    if row is None:
        return None

    # Look up the current slug of the item.
    item = (
        await CollectionItem.select(CollectionItem.slug)
        .where(CollectionItem.id == row["item"])
        .first()
        
    )
    if item is None:
        return None
    return f"/{collection_slug}/{item['slug']}"


async def render_item(
    collection: dict[str, Any], item: dict[str, Any]
) -> str:
    """Render a CollectionItem detail page through its collection's template.

    Pipeline: resolve ``${item.*}`` → markdown → theme.
    """
    ctx = ExpressionContext(item=item)

    detail_md = collection.get("detail_template", "")
    if not detail_md:
        # Fallback: render item title + data dump.
        detail_md = f"# ${{item.title}}\n\n${{item.body}}"

    # Resolve item-level expressions.
    processed_md = await resolve_expressions(detail_md, ctx)

    # Also support ${site.*} and ${media.*} in detail templates.
    content_html = render_md(processed_md)
    content_html = expand_collections(content_html, ctx)

    theme = await get_active_theme()
    if theme is None:
        return content_html

    nav = await get_nav_items()
    site_head = await _get_site_head()
    return render_theme(
        base_template=theme["base_template"],
        css=theme.get("css", ""),
        title=item.get("title", ""),
        content_html=content_html,
        nav_items=nav,
        site_head=site_head,
    )


# ── Collection feed (HTMX pagination) ─────────────────────


async def render_collection_feed(
    collection_slug: str, page: int = 1
) -> str | None:
    """Return rendered card HTML for page *page* of a collection.

    Returns ``None`` if the collection doesn't exist.
    """
    col = (
        await Collection.select()
        .where(Collection.slug == collection_slug)
        .first()
        
    )
    if col is None:
        return None

    per_page = col.get("items_per_page", 10)
    offset = (page - 1) * per_page

    query = (
        CollectionItem.select()
        .where(CollectionItem.collection == col["id"])
        .where(CollectionItem.published.eq(True))
        .order_by(CollectionItem.created_at, ascending=False)
        .offset(offset)
        .limit(per_page + 1)
    )
    rows = await query
    has_more = len(rows) > per_page
    items = rows[:per_page]

    from cms.expressions import ResolvedCollection

    rc = ResolvedCollection(
        collection=col, items=items, has_more=has_more, next_page=page + 1
    )
    return render_card_list(rc, page=page)
