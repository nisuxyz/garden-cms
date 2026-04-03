# tests/test_db.py
import pytest

from db.schema import get_content, parse_tags, render_md
from db.tables import Post, PostSlugHistory, SiteContent


@pytest.mark.asyncio
async def test_init_db_seeds_content(engine):
    row = (
        await SiteContent.select(SiteContent.value)
        .where(SiteContent.content_key == "home.hero_headline")
        .first()
    )
    assert row is not None
    assert row["value"] != ""


@pytest.mark.asyncio
async def test_get_content_returns_html_for_markdown(engine):
    await SiteContent(
        content_key="test.md",
        value="**bold**",
        label="Test",
        is_markdown=True,
    ).save()
    result = await get_content("test.md")
    assert "<strong>bold</strong>" in result


@pytest.mark.asyncio
async def test_get_content_returns_plain_text(engine):
    await SiteContent(
        content_key="test.plain",
        value="Hello world",
        label="Test",
        is_markdown=False,
    ).save()
    result = await get_content("test.plain")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_get_content_missing_key_returns_empty(engine):
    assert await get_content("nonexistent.key") == ""


def test_parse_tags():
    assert parse_tags('["python", "web"]') == ["python", "web"]
    assert parse_tags("[]") == []
    assert parse_tags("") == []
    assert parse_tags("bad json") == []
    # Piccolo JSON columns return native lists
    assert parse_tags(["python", "web"]) == ["python", "web"]


@pytest.mark.asyncio
async def test_slug_history_preserved(engine):
    post = Post(title="Hello", slug="hello", summary="Summary", body="Body")
    await post.save()
    post_id = post.id

    await PostSlugHistory(post=post_id, slug="old-hello").save()

    row = (
        await PostSlugHistory.select(PostSlugHistory.post)
        .where(PostSlugHistory.slug == "old-hello")
        .first()
    )
    assert row is not None
    assert row["post"] == post_id
