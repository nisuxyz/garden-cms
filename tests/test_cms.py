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
