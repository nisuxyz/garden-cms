# tests/test_cms.py
"""Tests for the CMS expression parser and renderer."""
import pytest

from cms.expressions import (
    ExpressionContext,
    _resolve_item,
    _split_preserving_code,
    resolve_expressions,
)
from db.tables import Collection, CollectionItem, ContentBlock, MediaFile


# ── Tokeniser ──────────────────────────────────────────────


def test_split_preserving_code_no_fences():
    parts = _split_preserving_code("hello ${site.key} world")
    assert len(parts) == 1
    assert parts[0] == (False, "hello ${site.key} world")


def test_split_preserving_code_with_fence():
    text = "before\n```\n${site.key}\n```\nafter"
    parts = _split_preserving_code(text)
    assert any(is_code for is_code, _ in parts)
    code_parts = [frag for is_code, frag in parts if is_code]
    assert "${site.key}" in code_parts[0]


# ── Item resolver (sync, no DB) ───────────────────────────


def test_resolve_item_from_data():
    ctx = ExpressionContext(
        item={"title": "Hello", "data": {"summary": "A summary"}}
    )
    assert _resolve_item("title", ctx) == "Hello"
    assert _resolve_item("summary", ctx) == "A summary"


def test_resolve_item_missing_field():
    ctx = ExpressionContext(item={"title": "Hello", "data": {}})
    assert _resolve_item("nonexistent", ctx) == ""


def test_resolve_item_no_context():
    ctx = ExpressionContext(item=None)
    assert _resolve_item("title", ctx) == ""


# ── Expression resolution (requires DB) ───────────────────


@pytest.mark.asyncio
async def test_resolve_site_text(engine):
    result = await resolve_expressions("Hello ${site.hero_headline}!")
    # Should contain the seeded headline value
    assert "Hello" in result
    assert "${site.hero_headline}" not in result


@pytest.mark.asyncio
async def test_resolve_site_markdown(engine):
    await ContentBlock(
        key="test.mdblock", label="Test", block_type="markdown", value="**bold**",
    ).save()
    result = await resolve_expressions("${site.test.mdblock}")
    assert "<strong>bold</strong>" in result


@pytest.mark.asyncio
async def test_resolve_site_missing_key(engine):
    result = await resolve_expressions("${site.nonexistent_key_xyz}")
    assert result == ""


@pytest.mark.asyncio
async def test_resolve_collection_placeholder(engine):
    ctx = ExpressionContext()
    result = await resolve_expressions("${collection.blog:3}", ctx)
    assert "<!--collection:blog:" in result
    assert len(ctx.collection_blocks) == 1
    _, rc = ctx.collection_blocks[0]
    assert rc.collection.get("slug") == "blog"


@pytest.mark.asyncio
async def test_resolve_media(engine):
    await MediaFile(
        filename="abc123.jpg",
        original_name="photo.jpg",
        file_path="data/media/abc123.jpg",
        mime_type="image/jpeg",
        alt_text="A photo",
    ).save()
    result = await resolve_expressions("${media.abc123.jpg}")
    assert '<img src="/media/abc123.jpg"' in result
    assert 'alt="A photo"' in result


@pytest.mark.asyncio
async def test_resolve_media_missing(engine):
    result = await resolve_expressions("${media.does_not_exist.png}")
    assert result == ""


@pytest.mark.asyncio
async def test_code_fence_preserved(engine):
    text = "```\n${site.hero_headline}\n```"
    result = await resolve_expressions(text)
    assert "${site.hero_headline}" in result


@pytest.mark.asyncio
async def test_unknown_expression_returns_empty(engine):
    result = await resolve_expressions("${unknown.thing}")
    assert result == ""


@pytest.mark.asyncio
async def test_item_expression_in_context(engine):
    ctx = ExpressionContext(
        item={"title": "My Post", "slug": "my-post", "data": {"summary": "Sum"}}
    )
    result = await resolve_expressions("# ${item.title}\n${item.summary}", ctx)
    assert "My Post" in result
    assert "Sum" in result


@pytest.mark.asyncio
async def test_multiple_expressions(engine):
    result = await resolve_expressions(
        "${site.hero_headline} - ${site.hero_subtext}"
    )
    assert "${site." not in result
