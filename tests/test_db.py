# tests/test_db.py
import pytest
from db.schema import get_content, parse_tags, render_md


@pytest.mark.asyncio
async def test_init_db_seeds_content(db):
    row = await db.query_one("SELECT value FROM site_content WHERE content_key = $1", ["home.hero_headline"])
    assert row is not None
    assert row["value"] != ""


@pytest.mark.asyncio
async def test_get_content_returns_html_for_markdown(db):
    await db.execute(
        "INSERT INTO site_content (content_key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
        ["test.md", "**bold**", "Test", True],
    )
    result = await get_content(db, "test.md")
    assert "<strong>bold</strong>" in result


@pytest.mark.asyncio
async def test_get_content_returns_plain_text(db):
    await db.execute(
        "INSERT INTO site_content (content_key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
        ["test.plain", "Hello world", "Test", False],
    )
    result = await get_content(db, "test.plain")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_get_content_missing_key_returns_empty(db):
    assert await get_content(db, "nonexistent.key") == ""


def test_parse_tags():
    assert parse_tags('["python", "web"]') == ["python", "web"]
    assert parse_tags("[]") == []
    assert parse_tags("") == []
    assert parse_tags("bad json") == []


@pytest.mark.asyncio
async def test_slug_history_preserved(db):
    await db.execute(
        "INSERT INTO posts (title, slug, summary, body) VALUES ($1, $2, $3, $4)",
        ["Hello", "hello", "Summary", "Body"],
    )
    post = await db.query_one("SELECT id FROM posts WHERE slug = $1", ["hello"])
    await db.execute(
        "INSERT INTO post_slug_history (post_id, slug) VALUES ($1, $2)",
        [post["id"], "old-hello"],
    )
    row = await db.query_one(
        "SELECT post_id FROM post_slug_history WHERE slug = $1", ["old-hello"]
    )
    assert row is not None
    assert row["post_id"] == post["id"]
