# tests/test_head_and_status.py
"""
Tests for the head-composition split (CSS framework setting + per-theme
Site Head), the Sprig-renders-200 regression, and the configurable
generic status page.
"""
from __future__ import annotations

import pytest

from db.tables import SiteSettings, Theme
from tests.conftest import _login


# ── CSS framework resolver (per-theme key → <head> HTML) ──────


def test_css_framework_defaults_to_pico():
    from cms.engine import _css_framework_html
    for key in ("", None, "pico"):
        html = _css_framework_html(key)
        assert "picocss" in html and "pico.classless" in html


def test_css_framework_none_yields_empty():
    from cms.engine import _css_framework_html
    assert _css_framework_html("none") == ""


def test_css_framework_unknown_key_yields_empty():
    from cms.engine import _css_framework_html
    assert _css_framework_html("does-not-exist") == ""


def test_css_framework_specific_key():
    from cms.engine import _css_framework_html
    assert "water.css" in _css_framework_html("water")


# ── render_themed head composition ────────────────────────────


@pytest.mark.asyncio
async def test_render_themed_composes_both_heads(engine):
    """Framework + site Site Head land in the theme-independent slot;
    theme Site Head + theme CSS land in the theme-specific slot."""
    from cms.renderer import render_themed
    base = (
        '{% extends "layout/base.html" %}'
        "{% block head %}{{ extra_head }}{% endblock %}"
        "{% block body %}{{ content }}{% endblock %}"
    )
    html = await render_themed(
        base_template=base,
        css="body{color:red}",
        title="T",
        content_html="<p>hi</p>",
        nav_items=[],
        site_head='<meta name="analytics" content="x">',
        theme_site_head='<script src="engine.js"></script>',
        css_framework_html='<link rel="stylesheet" href="fw.css">',
    )
    # theme-independent slot (admin_head): framework then site head
    assert '<link rel="stylesheet" href="fw.css">' in html
    assert '<meta name="analytics" content="x">' in html
    # theme-specific slot (head block): theme site head then <style>
    assert '<script src="engine.js"></script>' in html
    assert "<style>body{color:red}</style>" in html
    assert "<p>hi</p>" in html


@pytest.mark.asyncio
async def test_render_themed_framework_none_no_pico_fallback(engine):
    """When framework html is empty and there's no site head, the base
    template must NOT fall back to its built-in Pico default (the
    'is defined' guard sees an empty-but-present extra_admin_head)."""
    from cms.renderer import render_themed
    base = (
        '{% extends "layout/base.html" %}'
        "{% block body %}{{ content }}{% endblock %}"
    )
    html = await render_themed(
        base_template=base,
        css="",
        title="T",
        content_html="x",
        nav_items=[],
        site_head=None,
        theme_site_head="",
        css_framework_html="",
    )
    assert "pico.classless" not in html


# ── Sprig renders 200 (the reported 500 regression) ───────────


def test_sprig_active_homepage_renders_200(http_client):
    """Activating Sprig and rendering a public page must return 200,
    not the 500 the theme-engine mechanism used to cause. The Pico
    framework link and the UnoCSS engine (from Sprig's Site Head)
    must both be present."""
    import asyncio

    async def _activate_sprig():
        await Theme.update({Theme.active: False}, force=True)
        await Theme.update({Theme.active: True}).where(Theme.slug == "sprig")

    asyncio.get_event_loop().run_until_complete(_activate_sprig())

    resp = http_client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "pico.classless" in body           # site CSS framework
    assert "@unocss/runtime/uno.global.js" in body  # Sprig theme Site Head
    assert "max-w-5xl" in body                # Sprig utility chrome


# ── Configurable status page ──────────────────────────────────


def test_active_theme_css_framework_drives_head(http_client):
    """The active theme's css_framework key controls the framework link
    in the rendered public <head> — set it to 'none' → no framework."""
    import asyncio

    async def _sprig_none():
        await Theme.update({Theme.active: False}, force=True)
        await Theme.update(
            {Theme.active: True, Theme.css_framework: "none"}
        ).where(Theme.slug == "sprig")

    asyncio.get_event_loop().run_until_complete(_sprig_none())
    resp = http_client.get("/")
    assert resp.status_code == 200
    assert "pico.classless" not in resp.text
    # UnoCSS (Sprig's own Site Head) is unaffected by the framework choice.
    assert "@unocss/runtime/uno.global.js" in resp.text


def test_missing_public_page_renders_themed_status(http_client):
    """An unknown public URL renders the configured status page (the
    seeded 'error' Page) with a 404 status and the status_code in the
    body."""
    resp = http_client.get("/no-such-page-xyz", follow_redirects=False)
    assert resp.status_code == 404
    assert "text/html" in resp.headers.get("content-type", "")
    assert "404" in resp.text


def test_status_page_falls_back_when_unset(http_client):
    """With status_page unset, the built-in fallback renders (still 404)."""
    import asyncio

    async def _clear():
        await SiteSettings.update({SiteSettings.value: ""}).where(
            SiteSettings.key == "status_page"
        )

    asyncio.get_event_loop().run_until_complete(_clear())
    resp = http_client.get("/still-missing", follow_redirects=False)
    assert resp.status_code == 404
    assert "404" in resp.text


def test_admin_missing_path_is_plain_not_themed(http_client):
    """Errors under /admin never render the public themed status page."""
    _login(http_client)
    resp = http_client.get("/admin/definitely-not-a-route", follow_redirects=False)
    assert resp.status_code == 404
    # The themed status page would carry the site chrome; the plain
    # fallback does not reference the CSS framework link.
    assert "pico.classless" not in resp.text
