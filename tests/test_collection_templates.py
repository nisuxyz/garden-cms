"""Tests for the seeded collection card/detail templates.

These templates are rendered with the *production* Jinja env, which has
``autoescape=True`` (Litestar's ``JinjaTemplateEngine`` sets it, and JinjaX
copies the flag onto the catalog env). ``CollectionItem.data`` values are
plain strings — unlike ``ContentBlock`` html values, which are wrapped in
``Markup`` — so any DB-stored HTML rendered from an item must be piped
through ``| safe`` or it reaches the browser as visible escaped markup.

The shared ``engine`` fixture in conftest builds its env with
``autoescape=False``, which masks exactly this class of bug, so these tests
deliberately build their own autoescaping env.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment

from cms.catalog import register_filters
from db.connection import (
    _BLOG_CARD_TEMPLATE,
    _BLOG_DETAIL_TEMPLATE,
    _PROJECT_CARD_TEMPLATE,
    _PROJECT_DETAIL_TEMPLATE,
)

_BODY_HTML = "<h2>A heading</h2>\n<p>Some <em>body</em> copy.</p>"

_ITEM = {
    "title": "Test Item",
    "slug": "test-item",
    "summary": "A short summary.",
    "body": _BODY_HTML,
    "tags": "alpha, beta , ,gamma",
    "url": "https://example.com",
    "repo_url": "https://github.com/example/repo",
    "created_at": datetime(2026, 7, 24, 12, 34, 56, tzinfo=timezone.utc),
}

_CARD_TEMPLATES = [_BLOG_CARD_TEMPLATE, _PROJECT_CARD_TEMPLATE]
_DETAIL_TEMPLATES = [_BLOG_DETAIL_TEMPLATE, _PROJECT_DETAIL_TEMPLATE]
_ALL_TEMPLATES = _CARD_TEMPLATES + _DETAIL_TEMPLATES


@pytest.fixture
def env() -> Environment:
    """A Jinja env matching production: autoescaping, with CMS filters."""
    e = Environment(autoescape=True)
    register_filters(e)
    return e


def _render(env: Environment, template: str, **overrides) -> str:
    item = {**_ITEM, **overrides}
    return env.from_string(template).render(item=item)


# ── The invariant that makes | safe necessary ──────────────


def test_production_jinja_env_autoescapes() -> None:
    """If this ever flips to False, the ``| safe`` pipes below stop being
    load-bearing — but until then, DB-stored item HTML must be marked safe."""
    from litestar.contrib.jinja import JinjaTemplateEngine

    engine = JinjaTemplateEngine(directory=Path("templates"))
    assert engine.engine.autoescape is True


# ── Body HTML must not be escaped ──────────────────────────


@pytest.mark.parametrize("template", _DETAIL_TEMPLATES)
def test_detail_template_renders_body_html_unescaped(
    env: Environment, template: str
) -> None:
    out = _render(env, template)
    assert "<h2>A heading</h2>" in out
    assert "<em>body</em>" in out
    assert "&lt;h2&gt;" not in out
    assert "&lt;/p&gt;" not in out


# ── Tags render as individual pills, not a raw string ──────


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_tags_render_as_individual_pills(env: Environment, template: str) -> None:
    out = _render(env, template)
    for tag in ("alpha", "beta", "gamma"):
        assert f'<span class="tag">{tag}</span>' in out
    # The raw comma-joined string must not leak through.
    assert "alpha, beta" not in out


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_blank_tags_produce_no_pills(env: Environment, template: str) -> None:
    for value in ("", None, "  ,  ,"):
        out = _render(env, template, tags=value)
        assert 'class="tag"' not in out


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_missing_tags_key_does_not_break_render(
    env: Environment, template: str
) -> None:
    """``tags`` is optional in both seeded fields_schema definitions."""
    item = {k: v for k, v in _ITEM.items() if k != "tags"}
    out = env.from_string(template).render(item=item)
    assert 'class="tag"' not in out


# ── Dates are formatted, not dumped as full datetimes ─────


@pytest.mark.parametrize("template", [_BLOG_CARD_TEMPLATE, _BLOG_DETAIL_TEMPLATE])
def test_dates_are_formatted_as_iso_day(env: Environment, template: str) -> None:
    out = _render(env, template)
    assert "2026-07-24" in out
    # No time-of-day / tz noise.
    assert "12:34:56" not in out
    assert "+00:00" not in out


@pytest.mark.parametrize("template", [_BLOG_CARD_TEMPLATE, _BLOG_DETAIL_TEMPLATE])
def test_string_dates_are_also_formatted(env: Environment, template: str) -> None:
    """SQLite returns timestamps as strings; Postgres returns datetimes."""
    out = _render(env, template, created_at="2026-07-24 12:34:56+00:00")
    assert "2026-07-24" in out
    assert "12:34:56" not in out


# ── Project links survive the port ────────────────────────


def test_project_detail_links_to_url_and_repo(env: Environment) -> None:
    out = _render(env, _PROJECT_DETAIL_TEMPLATE)
    assert 'href="https://example.com"' in out
    assert 'href="https://github.com/example/repo"' in out


def test_project_detail_omits_absent_links(env: Environment) -> None:
    out = _render(env, _PROJECT_DETAIL_TEMPLATE, url=None, repo_url=None)
    assert "href=\"None\"" not in out
    assert "example.com" not in out


# ── Text fields stay escaped (no over-correction) ─────────


@pytest.mark.parametrize("template", _ALL_TEMPLATES)
def test_title_and_summary_remain_escaped(env: Environment, template: str) -> None:
    """Only ``body`` is trusted HTML. Titles/summaries are plain text and
    must still be escaped, or a stray ``<`` becomes an injection vector."""
    out = _render(
        env,
        template,
        title="<script>alert(1)</script>",
        summary="<img src=x onerror=alert(1)>",
    )
    assert "<script>" not in out
    assert "onerror=alert(1)>" not in out
    assert "&lt;script&gt;" in out
