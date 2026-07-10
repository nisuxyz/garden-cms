# tests/test_cms.py
"""Tests for the CMS rendering pipeline (site context + Jinja templates)."""
import pytest

from cms.renderer import render_sync, unpack_item_data
from cms.site_context import _site_dict, get_site_dict, load_site_dict
from db.tables import ContentBlock


# ── Site context cache ─────────────────────────────────────


@pytest.mark.asyncio
async def test_load_site_dict(engine):
    await load_site_dict()
    d = get_site_dict()
    assert "hero_headline" in d
    assert d["hero_headline"] != ""


@pytest.mark.asyncio
async def test_site_dict_invalidation(engine):
    await load_site_dict()
    old_val = get_site_dict().get("hero_headline")
    await ContentBlock.update(
        {ContentBlock.value: "Updated Headline"}
    ).where(ContentBlock.key == "hero_headline")
    await load_site_dict()
    assert get_site_dict()["hero_headline"] == "Updated Headline"
    assert get_site_dict()["hero_headline"] != old_val


@pytest.mark.asyncio
async def test_site_dict_image_block(engine):
    await ContentBlock(
        key="test.img", label="Test Img", block_type="image", value="photo.jpg",
    ).save()
    await load_site_dict()
    # Image blocks should have a URL, not raw filename
    assert get_site_dict()["test.img"].endswith("photo.jpg")


# ── Template string rendering ──────────────────────────────


def test_render_sync_basic():
    result = render_sync("<p>{{ name }}</p>", {"name": "World"})
    assert "<p>World</p>" in result


def test_render_sync_empty():
    result = render_sync("")
    assert result == ""


def test_render_sync_no_context():
    result = render_sync("<p>Hello</p>")
    assert "<p>Hello</p>" in result


# ── Card rendering ─────────────────────────────────────────


def test_render_card_basic():
    tpl = '<article><h3>{{ item.title }}</h3></article>'
    item = {"title": "My Post", "slug": "my-post", "data": {}}
    merged = unpack_item_data(item)
    result = render_sync(tpl, {"item": merged})
    assert "<h3>My Post</h3>" in result


def test_render_card_with_data_fields():
    tpl = '<p>{{ item.summary }}</p>'
    item = {"title": "Post", "data": {"summary": "A summary"}}
    merged = unpack_item_data(item)
    result = render_sync(tpl, {"item": merged})
    assert "A summary" in result


def test_render_card_json_string_data():
    import json
    tpl = '<p>{{ item.tags }}</p>'
    item = {"title": "Post", "data": json.dumps({"tags": "a, b, c"})}
    merged = unpack_item_data(item)
    result = render_sync(tpl, {"item": merged})
    assert "a, b, c" in result


def test_unpack_item_data_handles_malformed_json():
    """A corrupted ``data`` JSON string shouldn't blow up rendering."""
    import json
    item = {"title": "Post", "data": "{not json"}
    merged = unpack_item_data(item)
    assert merged["title"] == "Post"
    # Malformed JSON → empty dict, the item's scalar fields still present.
    assert "summary" not in merged


def test_unpack_item_data_handles_non_dict_json():
    """A JSON value that's a list/str shouldn't silently merge into the item."""
    item = {"title": "Post", "data": "['a', 'b']"}
    merged = unpack_item_data(item)
    assert merged["title"] == "Post"
    # List data is not mergeable; should degrade to empty.
    assert "summary" not in merged


def test_unpack_item_data_handles_none():
    item = {"title": "Post"}
    merged = unpack_item_data(item)
    assert merged["title"] == "Post"


# ── Collection feed page clamping ─────────────────────────


@pytest.mark.asyncio
async def test_fetch_collection_async_clamps_negative_page(engine):
    from cms.catalog import fetch_collection_async

    # The seeded "blog" collection exists; a negative page must not produce a
    # negative OFFSET — it should clamp to page 1.
    r = await fetch_collection_async("blog", page=-7)
    assert r["collection"] is not None
    assert r["next_page"] == 2  # clamped page 1 → next page 2


@pytest.mark.asyncio
async def test_fetch_collection_async_clamps_huge_page(engine):
    from cms.catalog import fetch_collection_async

    r = await fetch_collection_async("blog", page=10**9)
    assert r["collection"] is not None
    # No items on a huge page; has_more False, items [].
    assert r["items"] == []
    assert r["has_more"] is False
