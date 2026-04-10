# db/connection.py
"""
Database lifecycle management for Piccolo + Litestar.

Provides an async lifespan context-manager that opens/closes the
Piccolo connection pool and ensures seed data exists.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar
from piccolo.engine.postgres import PostgresEngine

from db.tables import Collection, ContentBlock, Page, SiteSettings, Theme


# ── Seed data ──────────────────────────────────────────────

_DEFAULT_THEME_TEMPLATE = """\
{% extends "layout/base.html" %}
{% block head %}{{ extra_head }}{% endblock %}
{% block body %}
<header>
  <nav>
    <ul>
      <li><strong><a href="/" style="text-decoration:none">&larr; home</a></strong></li>
    </ul>
    <ul>
      {% for item in nav_items %}
      <li><a href="{{ item.url }}">{{ item.title | lower }}</a></li>
      {% endfor %}
      <li>
        <button data-theme-toggle
          onclick="var d=document.documentElement,t=d.getAttribute('data-theme')==='dark'?'light':'dark';d.setAttribute('data-theme',t);localStorage.setItem('theme',t);"
          title="Toggle theme" aria-label="Toggle theme"></button>
      </li>
    </ul>
  </nav>
</header>
<main>{{ content }}</main>
<footer>
  <small>
    powered by <a href="https://litestar.dev" target="_blank">litestar</a> &middot;
    <a href="https://htmx.org" target="_blank">htmx</a> &middot;
    <a href="https://picocss.com" target="_blank">pico css</a>
  </small>
</footer>
{% endblock %}
"""

_DEFAULT_THEME_CSS = """\
:root {
  --pico-border-radius: 0.5rem;
  --pico-font-family-sans-serif: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --pico-font-family-monospace: "SFMono-Regular", "Consolas", "Liberation Mono", Menlo, monospace;
  --pico-transition: 150ms ease;
}
:root[data-theme="light"] {
  --pico-primary: var(--pico-color-jade-550);
  --pico-primary-background: var(--pico-color-jade-550);
  --pico-primary-hover: var(--pico-color-jade-600);
  --pico-primary-inverse: #ffffff;
  --pico-secondary: var(--pico-color-azure-600);
  --pico-secondary-background: var(--pico-color-azure-600);
  --pico-secondary-hover: var(--pico-color-azure-700);
  --pico-secondary-inverse: #ffffff;
  --pico-background-color: var(--pico-color-slate-50);
  --pico-card-background-color: #ffffff;
  --pico-card-border-color: var(--pico-color-slate-200);
  --pico-color: var(--pico-color-slate-900);
  --pico-muted-color: var(--pico-color-slate-500);
  --pico-muted-border-color: var(--pico-color-slate-200);
}
:root[data-theme="dark"] {
  --pico-primary: var(--pico-color-jade-350);
  --pico-primary-background: var(--pico-color-jade-500);
  --pico-primary-hover: var(--pico-color-jade-450);
  --pico-primary-inverse: var(--pico-color-slate-950);
  --pico-secondary: var(--pico-color-azure-350);
  --pico-secondary-background: var(--pico-color-azure-500);
  --pico-secondary-hover: var(--pico-color-azure-450);
  --pico-secondary-inverse: var(--pico-color-slate-950);
  --pico-background-color: var(--pico-color-slate-950);
  --pico-card-background-color: var(--pico-color-slate-900);
  --pico-card-border-color: var(--pico-color-slate-800);
  --pico-color: var(--pico-color-slate-100);
  --pico-muted-color: var(--pico-color-slate-400);
  --pico-muted-border-color: var(--pico-color-slate-800);
}
article {
  box-shadow: 0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
  transition: box-shadow var(--pico-transition);
}
article:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.06);
}
:root[data-theme="dark"] article {
  box-shadow: 0 1px 3px rgba(0,0,0,.25), 0 1px 2px rgba(0,0,0,.20);
}
:root[data-theme="dark"] article:hover {
  box-shadow: 0 4px 14px rgba(0,0,0,.35), 0 2px 6px rgba(0,0,0,.25);
}
.tag {
  display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px;
  background-color: var(--pico-secondary-background);
  color: var(--pico-secondary-inverse);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.72rem; font-weight: 500; text-decoration: none;
}
.meta {
  color: var(--pico-muted-color);
  font-family: var(--pico-font-family-monospace);
  font-size: 0.8rem;
}
.hero { padding: 4rem 0 3rem; }
.hero h1 { font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 700; line-height: 1.15; margin-bottom: 0.75rem; }
.hero p { font-size: 1.2rem; color: var(--pico-muted-color); max-width: 48ch; }
body { display: flex; flex-direction: column; min-height: 100vh; }
body>footer { margin-top: auto; text-align: center; }
[data-theme-toggle] {
  background: none; border: none; cursor: pointer;
  padding: 0.25rem 0.5rem; font-size: 1.1rem;
  color: var(--pico-muted-color); transition: color var(--pico-transition);
}
[data-theme-toggle]:hover { color: var(--pico-color); }
:root[data-theme="light"] [data-theme-toggle]::before { content: "☽"; }
:root[data-theme="dark"] [data-theme-toggle]::before { content: "☀"; }
"""

_DEFAULT_CONTENT_BLOCKS = [
    ("hero_headline", "Hero Headline", "text", "Hello, I'm here."),
    ("hero_subtext", "Hero Subtext", "text", "Developer, maker, and curious human."),
    ("about", "About (Home)", "markdown", "I build things, explore ideas, and occasionally write about what I learn along the way."),
    ("resume.intro", "Resume Intro", "markdown", "Here's a snapshot of my professional journey so far."),
    ("resume.experience", "Resume Experience", "markdown", "## Experience\n\n*Add your experience here.*"),
    ("resume.education", "Resume Education", "markdown", "## Education\n\n*Add your education here.*"),
    ("resume.skills", "Resume Skills", "markdown", "## Skills\n\n*Add your skills here.*"),
    ("contact.intro", "Contact Intro", "markdown", "Have a question or want to say hello? Fill out the form below."),
]

_BLOG_CARD_TEMPLATE = """\
<article>
  <header>
    <h3><a href="/blog/${item.slug}">${item.title}</a></h3>
    <small class="meta">${item.created_at}</small>
  </header>
  <p>${item.summary}</p>
  <footer>${item.tags}</footer>
</article>
"""

_BLOG_DETAIL_TEMPLATE = """\
# ${item.title}

<small class="meta">${item.created_at}</small>

${item.summary}

---

${item.body}

${item.tags}
"""

_PROJECT_CARD_TEMPLATE = """\
<article>
  <header>
    <h3><a href="/projects/${item.slug}">${item.title}</a></h3>
  </header>
  <p>${item.summary}</p>
  <footer>${item.tags}</footer>
</article>
"""

_PROJECT_DETAIL_TEMPLATE = """\
# ${item.title}

${item.summary}

---

${item.body}

${item.tags}
"""

_HOME_PAGE_MD = """\
<div class="hero">

# ${site.hero_headline}

${site.hero_subtext}

</div>

${site.about}

## Recent Posts

${collection.blog:3}

## Featured Projects

${collection.projects:featured:4}
"""

_BLOG_PAGE_MD = """\
# Blog

${collection.blog}
"""

_PROJECTS_PAGE_MD = """\
# Projects

${collection.projects}
"""

_RESUME_PAGE_MD = """\
# Resume / CV

${site.resume.intro}

${site.resume.experience}

${site.resume.skills}
"""

_CONTACT_PAGE_MD = """\
# Contact

${site.contact.intro}

<form method="post" action="/contact" hx-post="/contact" hx-target="#contact-area" hx-swap="innerHTML">
  <div id="contact-area">
    <label>
      Name
      <input type="text" name="name" required />
    </label>
    <label>
      Email
      <input type="email" name="email" required />
    </label>
    <label>
      Message
      <textarea name="message" rows="5" required></textarea>
    </label>
    <button type="submit">Send</button>
  </div>
</form>
"""


async def init_db() -> None:
    """Seed default CMS data if tables are empty.

    Each section checks independently so a partial previous seed
    (e.g. theme created but pages failed) is completed on next run.
    """

    # ── Theme ──────────────────────────────────────────────
    if await Theme.count() == 0:
        await Theme(
            name="Mycelium",
            slug="mycelium",
            base_template=_DEFAULT_THEME_TEMPLATE,
            css=_DEFAULT_THEME_CSS,
            active=True,
        ).save()

    # ── Content Blocks ─────────────────────────────────────
    if await ContentBlock.count() == 0:
        for key, label, block_type, value in _DEFAULT_CONTENT_BLOCKS:
            await ContentBlock(
                key=key, label=label, block_type=block_type, value=value,
            ).save()

    # ── Pages ──────────────────────────────────────────────
    if await Page.count() == 0:
        pages = [
            ("Home", "home", _HOME_PAGE_MD, True, True, 0),
            ("Blog", "blog", _BLOG_PAGE_MD, False, True, 1),
            ("Projects", "projects", _PROJECTS_PAGE_MD, False, True, 2),
            ("Resume", "resume", _RESUME_PAGE_MD, False, True, 3),
            ("Contact", "contact", _CONTACT_PAGE_MD, False, True, 4),
        ]
        for title, slug, body_md, is_homepage, show_in_nav, nav_order in pages:
            await Page(
                title=title,
                slug=slug,
                body_md=body_md,
                is_homepage=is_homepage,
                show_in_nav=show_in_nav,
                nav_order=nav_order,
                published=True,
            ).save()

    # ── Collections ────────────────────────────────────────
    if await Collection.count() == 0:
        await Collection(
            name="Blog Posts",
            slug="blog",
            description="Blog posts and articles",
            fields_schema=[
                {"name": "summary", "type": "text", "required": True},
                {"name": "body", "type": "markdown", "required": True},
                {"name": "tags", "type": "list", "required": False},
            ],
            card_template=_BLOG_CARD_TEMPLATE,
            detail_template=_BLOG_DETAIL_TEMPLATE,
            items_per_page=10,
        ).save()

        await Collection(
            name="Projects",
            slug="projects",
            description="Portfolio projects",
            fields_schema=[
                {"name": "summary", "type": "text", "required": True},
                {"name": "body", "type": "markdown", "required": True},
                {"name": "tags", "type": "list", "required": False},
                {"name": "url", "type": "url", "required": False},
                {"name": "repo_url", "type": "url", "required": False},
            ],
            card_template=_PROJECT_CARD_TEMPLATE,
            detail_template=_PROJECT_DETAIL_TEMPLATE,
            items_per_page=12,
        ).save()

    # ── Settings ───────────────────────────────────────────
    if await SiteSettings.count() == 0:
        defaults = [
            ("storage_backend", "local"),
            ("s3_bucket", ""),
            ("s3_region", "us-east-1"),
            ("s3_endpoint_url", ""),
            ("s3_access_key_id", ""),
            ("s3_secret_access_key", ""),
            ("s3_prefix", ""),
            ("s3_public_url", ""),
        ]
        for key, value in defaults:
            await SiteSettings(key=key, value=value).save()


@asynccontextmanager
async def db_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    """Start the Piccolo connection pool on startup, close on shutdown."""
    from piccolo_conf import DB  # noqa: WPS433 — deferred to allow env loading

    engine: PostgresEngine = DB

    await engine.start_connection_pool(max_inactive_connection_lifetime=1)
    try:
        await init_db()
        # Initialise the storage backend from DB settings.
        from cms.storage import load_backend
        await load_backend()
        yield
    finally:
        await engine.close_connection_pool()
