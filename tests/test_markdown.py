# tests/test_markdown.py
"""
Unit tests for cms.markdown — directory discovery, route listing,
resolve_md_file (including the traversal guard), and the md_mounts
SiteSettings persistence round-trip.
"""
from __future__ import annotations

import pytest

import cms.markdown as m
from cms.markdown import (
    discover_md_dirs,
    list_md_routes,
    load_md_mounts,
    resolve_md_file,
    save_md_mounts,
)


# ── Discovery + routing ────────────────────────────────────


def test_discover_md_dirs(monkeypatch, tmp_path):
    root = tmp_path / "md"
    (root / "docs").mkdir(parents=True)
    (root / "blog").mkdir(parents=True)
    (root / ".hidden").mkdir()
    monkeypatch.setattr(m, "_MD_ROOT", root)
    dirs = discover_md_dirs()
    assert dirs == ["blog", "docs"]  # sorted, dotdirs excluded


def test_discover_md_dirs_empty_when_root_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_MD_ROOT", tmp_path / "nonexistent")
    assert discover_md_dirs() == []


def test_list_md_routes(monkeypatch, tmp_path):
    root = tmp_path / "md"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Index")
    (docs / "styling").mkdir()
    (docs / "styling" / "css.md").write_text("# CSS")
    monkeypatch.setattr(m, "_MD_ROOT", root)
    routes = list_md_routes("docs")
    assert "index" in routes
    assert "styling/css" in routes


def test_list_md_routes_nonexistent_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "_MD_ROOT", tmp_path / "md")
    assert list_md_routes("no-such") == []


# ── resolve_md_file ────────────────────────────────────────


def test_resolve_md_file_returns_title_and_html(monkeypatch, tmp_path):
    root = tmp_path / "md"
    docs = root / "docs"
    docs.mkdir(parents=True)
    (docs / "page.md").write_text("# My Page Title\n\nSome content.")
    monkeypatch.setattr(m, "_MD_ROOT", root)
    result = resolve_md_file("docs", "page")
    assert result is not None
    title, html, _layout = result
    assert title == "My Page Title"
    assert "<h1>" in html or "My Page Title" in html


def test_resolve_md_file_finds_nearest_layout(monkeypatch, tmp_path):
    root = tmp_path / "md"
    docs = root / "docs"
    sub = docs / "sub"
    sub.mkdir(parents=True)
    (docs / "_layout.jinja").write_text("LAYOUT-ROOT")
    (sub / "page.md").write_text("# Page")
    monkeypatch.setattr(m, "_MD_ROOT", root)
    result = resolve_md_file("docs", "sub/page")
    assert result is not None
    _, _, layout = result
    assert layout == "LAYOUT-ROOT"


def test_resolve_md_file_missing_file(monkeypatch, tmp_path):
    root = tmp_path / "md"
    (root / "docs").mkdir(parents=True)
    monkeypatch.setattr(m, "_MD_ROOT", root)
    assert resolve_md_file("docs", "no-such") is None


def test_resolve_md_file_rejects_dotdot(monkeypatch, tmp_path):
    root = tmp_path / "md"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "real.md").write_text("# Real")
    monkeypatch.setattr(m, "_MD_ROOT", root)
    assert resolve_md_file("docs", "../secret") is None


def test_resolve_md_file_rejects_absolute(monkeypatch, tmp_path):
    root = tmp_path / "md"
    (root / "docs").mkdir(parents=True)
    monkeypatch.setattr(m, "_MD_ROOT", root)
    assert resolve_md_file("docs", "/etc/passwd") is None


# ── md_mounts persistence ──────────────────────────────────


@pytest.mark.asyncio
async def test_save_and_load_md_mounts(engine):
    await save_md_mounts({"docs": "docs", "blog": "blog"})
    loaded = await load_md_mounts()
    assert loaded == {"docs": "docs", "blog": "blog"}


@pytest.mark.asyncio
async def test_load_md_mounts_empty_when_unset(engine):
    # Clear any seeded value first.
    from db.tables import SiteSettings
    await SiteSettings.delete().where(SiteSettings.key == "md_mounts")
    assert await load_md_mounts() == {}