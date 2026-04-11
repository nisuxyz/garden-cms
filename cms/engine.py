# cms/engine.py
"""
High-level CMS page processing pipeline.

    resolve_page  → fetch a Page row by slug (or homepage flag)
    render_page   → full pipeline: Jinja render body → theme wrap
    render_item   → render a CollectionItem detail page
    get_nav_items → navigation items for the active theme
"""
from __future__ import annotations

from typing import Any

from cms.catalog import fetch_collection_async
from cms.renderer import render, render_sync, render_themed, unpack_item_data
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
    """Full pipeline: render body as Jinja template → wrap in theme.

    Returns a complete HTML document string.
    """
    content_html = await render(page["body"])

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
        return content_html

    nav = await get_nav_items()
    site_head = await _get_site_head()

    return await render_themed(
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

    Pipeline: render detail_template as Jinja with ``item`` context → theme.
    """
    detail_tpl = collection.get("detail_template", "")
    if not detail_tpl:
        detail_tpl = "<h1>{{ item.title }}</h1>\n{{ item.body }}"

    merged = unpack_item_data(item)
    content_html = await render(detail_tpl, {"item": merged})

    theme = await get_active_theme()
    if theme is None:
        return content_html

    nav = await get_nav_items()
    site_head = await _get_site_head()
    return await render_themed(
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
    Uses the shared ``fetch_collection_async`` for data access.
    """
    result = await fetch_collection_async(collection_slug, page=page)
    col = result["collection"]
    if col is None:
        return None

    items = result["items"]
    if not items:
        return col.get("empty_template", "")

    card_tpl = col.get("card_template", "")
    slug = col.get("slug", "")
    parts: list[str] = [
        render_sync(card_tpl, {"item": item})
        for item in items
    ]
    html = "\n".join(parts)

    if result["has_more"]:
        next_page = result["next_page"]
        html += (
            f'\n<button hx-get="/api/collection/{slug}/feed?page={next_page}" '
            f'hx-swap="outerHTML" hx-target="this">Load more</button>'
        )

    return html
