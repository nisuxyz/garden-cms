# tests/test_routes.py
"""Tests for the CMS engine functions (used by public routes)."""
import pytest

from cms.engine import (
    get_active_theme,
    get_nav_items,
    render_collection_feed,
    render_page,
    resolve_collection_item,
    resolve_homepage,
    resolve_page,
    resolve_slug_redirect,
)
from db.tables import Collection, CollectionItem, CollectionItemSlugHistory


# ── Resolve helpers ────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_homepage(engine):
    page = await resolve_homepage()
    assert page is not None
    assert page["is_homepage"] is True
    assert page["slug"] == "home"


@pytest.mark.asyncio
async def test_resolve_page_by_slug(engine):
    page = await resolve_page("blog")
    assert page is not None
    assert page["title"] == "Blog"


@pytest.mark.asyncio
async def test_resolve_page_not_found(engine):
    page = await resolve_page("nonexistent-slug-xyz")
    assert page is None


@pytest.mark.asyncio
async def test_get_nav_items(engine):
    items = await get_nav_items()
    assert len(items) > 0
    slugs = [i["slug"] for i in items]
    assert "blog" in slugs
    # Homepage should have url "/"
    home = [i for i in items if i["slug"] == "home"]
    assert home[0]["url"] == "/"


@pytest.mark.asyncio
async def test_get_active_theme(engine):
    theme = await get_active_theme()
    assert theme is not None
    assert theme["slug"] == "mycelium"
    assert "<!doctype html>" in theme["base_template"].lower()


# ── Render pipeline ───────────────────────────────────────


@pytest.mark.asyncio
async def test_render_page_returns_html(engine):
    page = await resolve_homepage()
    html = await render_page(page)
    assert "<!doctype html>" in html.lower()
    assert "</html>" in html


@pytest.mark.asyncio
async def test_render_page_resolves_expressions(engine):
    page = await resolve_page("resume")
    html = await render_page(page)
    # Should not contain any raw ${} expressions
    assert "${site." not in html


# ── Collection item routing ────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_collection_item(engine):
    col = await Collection.select().where(Collection.slug == "blog").first()
    item = CollectionItem(
        collection=col["id"], title="Test Post", slug="test-post",
        data={"summary": "A test", "body": "Content here"}, published=True,
    )
    await item.save()

    found_col, found_item = await resolve_collection_item("blog", "test-post")
    assert found_col is not None
    assert found_item is not None
    assert found_item["title"] == "Test Post"


@pytest.mark.asyncio
async def test_resolve_collection_item_not_found(engine):
    col, item = await resolve_collection_item("blog", "nonexistent-item")
    # Collection exists but item doesn't
    assert col is not None
    assert item is None


@pytest.mark.asyncio
async def test_resolve_collection_item_bad_collection(engine):
    col, item = await resolve_collection_item("no-such-collection", "anything")
    assert col is None
    assert item is None


# ── Slug redirect ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_slug_redirect(engine):
    col = await Collection.select().where(Collection.slug == "blog").first()
    item = CollectionItem(
        collection=col["id"], title="Renamed", slug="new-slug",
        data={"summary": "s", "body": "b"}, published=True,
    )
    await item.save()

    await CollectionItemSlugHistory(
        item=item.id, collection_slug="blog", old_slug="old-slug",
    ).save()

    url = await resolve_slug_redirect("blog", "old-slug")
    assert url == "/blog/new-slug"


@pytest.mark.asyncio
async def test_slug_redirect_not_found(engine):
    url = await resolve_slug_redirect("blog", "never-existed")
    assert url is None


# ── Collection feed ────────────────────────────────────────


@pytest.mark.asyncio
async def test_collection_feed_empty(engine):
    html = await render_collection_feed("blog", page=1)
    assert html is not None  # collection exists, just no items


@pytest.mark.asyncio
async def test_collection_feed_not_found(engine):
    result = await render_collection_feed("nonexistent-collection")
    assert result is None


@pytest.mark.asyncio
async def test_collection_feed_with_items(engine):
    col = await Collection.select().where(Collection.slug == "blog").first()
    for i in range(3):
        await CollectionItem(
            collection=col["id"], title=f"Post {i}", slug=f"post-{i}",
            data={"summary": f"Summary {i}", "body": f"Body {i}"},
            published=True,
        ).save()

    html = await render_collection_feed("blog", page=1)
    assert "Post 0" in html or "Post 1" in html or "Post 2" in html
