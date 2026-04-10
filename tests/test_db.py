# tests/test_db.py
"""Tests for the CMS database schema and seed data."""
import pytest

from db.tables import (
    Collection,
    CollectionItem,
    CollectionItemSlugHistory,
    ContentBlock,
    Page,
    Theme,
)


# ── Seed data ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_creates_theme(engine):
    row = await Theme.select().where(Theme.slug == "mycelium").first()
    assert row is not None
    assert row["active"] is True


@pytest.mark.asyncio
async def test_seed_creates_homepage(engine):
    row = await Page.select().where(Page.is_homepage.eq(True)).first()
    assert row is not None
    assert row["slug"] == "home"
    assert row["published"] is True


@pytest.mark.asyncio
async def test_seed_creates_content_blocks(engine):
    row = (
        await ContentBlock.select()
        .where(ContentBlock.key == "hero_headline")
        .first()
    )
    assert row is not None
    assert row["value"] != ""


@pytest.mark.asyncio
async def test_seed_creates_collections(engine):
    blog = await Collection.select().where(Collection.slug == "blog").first()
    projects = await Collection.select().where(Collection.slug == "projects").first()
    assert blog is not None
    assert projects is not None
    assert len(blog["fields_schema"]) > 0


@pytest.mark.asyncio
async def test_seed_idempotent(engine):
    """Calling init_db() again should not duplicate rows."""
    from db.connection import init_db

    count_before = await Theme.count()
    await init_db()
    assert await Theme.count() == count_before


# ── Content blocks ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_content_block_types(engine):
    await ContentBlock(
        key="test.md", label="Test", block_type="markdown", value="**bold**",
    ).save()
    row = await ContentBlock.select().where(ContentBlock.key == "test.md").first()
    assert row["block_type"] == "markdown"

    await ContentBlock(
        key="test.img", label="Img", block_type="image", value="photo.jpg",
    ).save()
    row = await ContentBlock.select().where(ContentBlock.key == "test.img").first()
    assert row["block_type"] == "image"


# ── Slug history ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_slug_history_preserved(engine):
    col = await Collection.select().where(Collection.slug == "blog").first()
    item = CollectionItem(
        collection=col["id"], title="Hello", slug="hello",
        data={"summary": "s", "body": "b"}, published=True,
    )
    await item.save()
    item_id = item.id

    await CollectionItemSlugHistory(
        item=item_id, collection_slug="blog", old_slug="old-hello",
    ).save()

    row = (
        await CollectionItemSlugHistory.select()
        .where(CollectionItemSlugHistory.old_slug == "old-hello")
        .first()
    )
    assert row is not None
    assert row["item"] == item_id

