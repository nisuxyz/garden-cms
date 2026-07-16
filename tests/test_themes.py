# tests/test_themes.py
"""
Tests for seeded theme templates — verify both the classless Mycelium
and the non-classless Sprig ship and render without errors.
"""
from __future__ import annotations

import jinja2
import pytest
from jinja2 import Environment, FileSystemLoader

from db.tables import ContentBlock, Page, SiteSettings, Theme


# ── Seeding ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mycelium_is_seeded_active(engine):
    row = await Theme.select().where(Theme.slug == "mycelium").first()
    assert row is not None
    assert row["name"] == "Mycelium"
    assert row["active"] is True
    # Stored template should be the polished Mycelium v2, not the old
    # single-line nav + footer version.
    assert "myco-header" in row["base_template"]
    assert "myco-footer__inner" in row["base_template"]


@pytest.mark.asyncio
async def test_sprig_is_seeded_inactive(engine):
    row = await Theme.select().where(Theme.slug == "sprig").first()
    assert row is not None
    assert row["name"] == "Sprig"
    assert row["active"] is False
    # Stored template uses UnoCSS runtime utility classes.
    assert "unocss" in row["base_template"].lower()
    assert "class=\"sticky top-0" in row["base_template"]


@pytest.mark.asyncio
async def test_exactly_one_theme_is_active(engine):
    rows = await Theme.select().where(Theme.active.eq(True))
    assert len(rows) == 1
    assert rows[0]["slug"] == "mycelium"


@pytest.mark.asyncio
async def test_nightshade_is_seeded_inactive(engine):
    row = await Theme.select().where(Theme.slug == "nightshade").first()
    assert row is not None
    assert row["name"] == "Nightshade"
    assert row["active"] is False
    # Hand-rolled theme: no base framework.
    assert row["css_framework"] == "none"
    # Dark-first shell markers + web fonts in its Site Head.
    assert "ns-header" in row["base_template"]
    assert "data-theme-toggle" in row["base_template"]
    assert "Space+Grotesk" in (row["site_head"] or "")


# ── Template validity ────────────────────────────────────────


def _make_env() -> Environment:
    """Standalone Jinja env that mimics the CMS context surface."""
    env = Environment(loader=FileSystemLoader("templates"), autoescape=False)
    return env


def test_mycelium_template_renders_into_valid_html():
    """Rendering Mycelium should not raise, and should expose the
    header / nav / footer that the CSS styles rely on."""
    from db.connection import _MYCELIUM_TEMPLATE
    tmpl = _make_env().from_string(_MYCELIUM_TEMPLATE)
    html = tmpl.render(
        site={"site_name": "Test", "tagline": "Hi"},
        nav_items=[{"title": "Home", "url": "/"}],
        content="<p>Body</p>",
        extra_head="",
        logo=None,
    )
    assert "myco-header" in html
    assert "myco-nav" in html
    assert "myco-footer" in html
    assert "myco-theme-toggle" in html
    assert "Hi" in html  # tagline rendered
    assert "<p>Body</p>" in html


def test_sprig_template_renders_into_valid_html():
    """Rendering Sprig should not raise, and its utility-class chrome
    should flow through to the rendered markup. The CSS engine is no
    longer hardcoded in the template — it lives in the theme's Site
    Head (extra_head) — so the template itself carries no unocss URL."""
    from db.connection import _SPRIG_TEMPLATE
    tmpl = _make_env().from_string(_SPRIG_TEMPLATE)
    html = tmpl.render(
        site={"site_name": "Test"},
        nav_items=[{"title": "Home", "url": "/"}],
        content="<p>Body</p>",
        extra_head="",
    )
    assert "sticky top-0" in html
    assert "max-w-5xl mx-auto" in html
    assert "<p>Body</p>" in html
    # The template must not hardcode the engine anymore.
    assert "unocss" not in html.lower()


def test_nightshade_template_renders_with_shell():
    """Nightshade renders a top-header shell with a theme toggle and a
    footer, and places {{ content }} in the main column."""
    from db.connection import _NIGHTSHADE_TEMPLATE
    tmpl = _make_env().from_string(_NIGHTSHADE_TEMPLATE)
    html = tmpl.render(
        site={"site_name": "Test"},
        nav_items=[{"title": "Home", "url": "/"}],
        content="<p>Body</p>",
        extra_head="",
        logo=None,
    )
    assert "ns-header" in html
    assert "ns-toggle" in html and "data-theme-toggle" in html
    assert "ns-footer" in html
    assert "<p>Body</p>" in html


def test_nightshade_css_dark_first_tokens_and_doc_sidebar():
    """Nightshade defines both dark and light token blocks (dark is the
    default :root) and styles the docs .doc-shell as a left sidebar."""
    from db.connection import _NIGHTSHADE_CSS
    assert ':root[data-theme="dark"]' in _NIGHTSHADE_CSS
    assert ':root[data-theme="light"]' in _NIGHTSHADE_CSS
    # Berry red-purple accent, not violet.
    assert "--ns-accent" in _NIGHTSHADE_CSS
    # Docs sidebar grid.
    assert ".doc-shell" in _NIGHTSHADE_CSS
    assert "grid-template-columns: 15rem" in _NIGHTSHADE_CSS


def test_mycelium_css_defines_data_theme_tokens():
    """Mycelium must override Pico tokens for both light AND dark
    themes — otherwise the [data-theme=dark] selector will not flip."""
    from db.connection import _MYCELIUM_CSS
    assert ":root[data-theme=\"light\"]" in _MYCELIUM_CSS
    assert ":root[data-theme=\"dark\"]" in _MYCELIUM_CSS
    assert "--myco-accent" in _MYCELIUM_CSS


# ── Docs layout is theme-driven ──────────────────────────────


def test_docs_layout_is_semantic_and_themeless():
    """The docs layout emits semantic .doc-shell markup and loads NO
    static stylesheet — styling now lives in each active theme's CSS."""
    from pathlib import Path
    src = Path("data/md/docs/_layout.jinja").read_text()
    assert "doc-shell" in src and "doc-nav" in src and "doc-content" in src
    assert "docs.css" not in src  # no static stylesheet link
    assert "<link" not in src     # carries no styling of its own


def test_all_themes_style_the_docs_nav():
    """Every shipped theme must style .doc-nav so the docs render
    correctly whichever theme is active (top-nav for the classless
    themes, sidebar for Nightshade)."""
    from db.connection import _MYCELIUM_CSS, _SPRIG_CSS, _NIGHTSHADE_CSS
    for css in (_MYCELIUM_CSS, _SPRIG_CSS, _NIGHTSHADE_CSS):
        assert ".doc-nav" in css and ".doc-content" in css


# ── Themes never control content ─────────────────────────────


@pytest.mark.asyncio
async def test_theme_has_no_home_template_field(engine):
    """Themes provide chrome + CSS only — there is no per-theme content
    override. The removed Theme.home_template column must be gone."""
    row = await Theme.select().where(Theme.slug == "sprig").first()
    assert "home_template" not in row


@pytest.mark.asyncio
async def test_homepage_renders_page_body_regardless_of_theme(engine):
    """render_page always renders the Page's own body — the active theme
    never injects or replaces content, even for the homepage."""
    from cms.engine import render_page
    # Homepage on the active theme (Mycelium): the page body wins.
    html = await render_page(
        {"body": "<h1 data-marker>PAGE BODY</h1>", "title": "Home", "is_homepage": True}
    )
    assert "PAGE BODY" in html
    # Wrapped in the active theme's chrome, but the theme adds no content.
    assert "myco-header" in html


@pytest.mark.asyncio
async def test_page_theme_override_pins_theme(engine):
    """A page can pin its own theme via Page.theme; render_page then wraps
    it in that theme instead of the site's active theme (Mycelium)."""
    from cms.engine import render_page
    night = await Theme.select(Theme.id).where(Theme.slug == "nightshade").first()
    # Pinned to Nightshade → Nightshade shell, not the active Mycelium one.
    pinned = await render_page(
        {"body": "<p>Body</p>", "title": "Pinned", "is_homepage": False,
         "theme": night["id"]}
    )
    assert "ns-header" in pinned and "myco-header" not in pinned
    # No override → active theme (Mycelium) wraps it.
    default = await render_page(
        {"body": "<p>Body</p>", "title": "Default", "is_homepage": False,
         "theme": None}
    )
    assert "myco-header" in default and "ns-header" not in default


def test_sprig_css_overrides_pico_tokens():
    """Sprig intentionally overrides Pico's design tokens so the
    classless body content emitted by seed pages picks up the
    Sprig palette (slate + emerald) instead of Pico's defaults.

    Verifies:
    * Light-mode ``:root`` block overrides key Pico tokens.
    * Dark-mode ``:root[data-theme="dark"]`` block does the same.
    * ``color-scheme`` is declared so the browser paints form
      controls correctly without a separate framework.
    """
    from db.connection import _SPRIG_CSS
    # Light-mode root must override Pico's color tokens.
    for var in ("--pico-primary", "--pico-background-color", "--pico-color",
                "--pico-muted-color", "--pico-card-background-color"):
        assert var in _SPRIG_CSS, f"Sprig CSS missing Pico override {var}"
    # Dark-mode root must override the same tokens.
    dark_block = _SPRIG_CSS.split(":root[data-theme=\"dark\"]", 1)[1]
    for var in ("--pico-primary", "--pico-background-color", "--pico-color"):
        assert var in dark_block, f"Sprig dark-mode CSS missing Pico override {var}"
    # Color scheme is declared on the root.
    assert "color-scheme" in _SPRIG_CSS


def test_sprig_loads_unocss_via_theme_site_head():
    """Sprig's CSS engine (UnoCSS) is carried by its Site Head field,
    not the template. The template no longer has the old theme-engine
    meta tag, and _SPRIG_SITE_HEAD loads the UnoCSS runtime."""
    from db.connection import _SPRIG_TEMPLATE, _SPRIG_SITE_HEAD
    assert "theme-engine" not in _SPRIG_TEMPLATE
    assert "@unocss/runtime/uno.global.js" not in _SPRIG_TEMPLATE
    assert "@unocss/runtime/uno.global.js" in _SPRIG_SITE_HEAD


@pytest.mark.asyncio
async def test_sprig_seeded_with_site_head(engine):
    """After seeding, the Sprig theme row carries the UnoCSS Site Head."""
    row = await Theme.select().where(Theme.slug == "sprig").first()
    assert row is not None
    assert "@unocss/runtime/uno.global.js" in (row.get("site_head") or "")


# ── ContentBlocks wiring ─────────────────────────────────────


@pytest.mark.asyncio
async def test_seeded_content_blocks_include_site_name_and_tagline(engine):
    """Mycelium's footer template relies on `site.site_name` and
    `site.tagline` — both must exist after seeding."""
    for key in ("site_name", "tagline", "hero_headline", "hero_subtext"):
        row = await ContentBlock.select().where(ContentBlock.key == key).first()
        assert row is not None, f"missing content block: {key}"
        assert (row.get("value") or "").strip() != "", f"empty content block: {key}"
