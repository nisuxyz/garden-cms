# db/schema.py
import json

from markdown_it import MarkdownIt
from stoolap import AsyncDatabase

_md = MarkdownIt()

_DDL = """
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTO_INCREMENT,
    title      TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    summary    TEXT NOT NULL,
    body       TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '[]',
    published  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS post_slug_history (
    id         INTEGER PRIMARY KEY AUTO_INCREMENT,
    post_id    INTEGER NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTO_INCREMENT,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    summary     TEXT NOT NULL,
    body        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    url         TEXT,
    repo_url    TEXT,
    featured    BOOLEAN NOT NULL DEFAULT FALSE,
    published   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS project_slug_history (
    id          INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id  INTEGER NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS site_content (
    id          INTEGER PRIMARY KEY AUTO_INCREMENT,
    content_key TEXT NOT NULL UNIQUE,
    value       TEXT NOT NULL,
    label       TEXT NOT NULL,
    is_markdown BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_CONTENT_SEEDS = [
    ("home.hero_headline", "Hello, I'm Nisu.", "Landing page headline", False),
    ("home.hero_subtext", "Developer, maker, and curious human.", "Landing page subtext", False),
    ("home.about", "I build things, explore ideas, and share what I learn.", "About blurb", True),
    ("resume.intro", "Here's a snapshot of where I've been and what I've built.", "Resume intro", True),
    ("resume.experience", "## Experience\n\n*Add your experience here.*", "Experience section", True),
    ("resume.education", "## Education\n\n*Add your education here.*", "Education section", True),
    ("resume.skills", "## Skills\n\n*Add your skills here.*", "Skills section", True),
    ("contact.intro", "Have a question or want to say hello?", "Contact page intro", True),
]


async def init_db(db: AsyncDatabase) -> None:
    """Create tables and seed default site_content rows."""
    await db.exec(_DDL)
    for key, value, label, is_markdown in _CONTENT_SEEDS:
        existing = await db.query_one(
            "SELECT content_key FROM site_content WHERE content_key = $1", [key]
        )
        if not existing:
            await db.execute(
                "INSERT INTO site_content (content_key, value, label, is_markdown) VALUES ($1, $2, $3, $4)",
                [key, value, label, is_markdown],
            )


def render_md(text: str) -> str:
    """Render a markdown string to HTML."""
    return _md.render(text)


async def get_content(db: AsyncDatabase, key: str) -> str:
    """Fetch a site_content value by key. Returns HTML (if markdown) or raw text. Returns '' if not found."""
    row = await db.query_one(
        "SELECT value, is_markdown FROM site_content WHERE content_key = $1", [key]
    )
    if not row:
        return ""
    return render_md(row["value"]) if row["is_markdown"] else row["value"]


def parse_tags(tags_json: str) -> list[str]:
    """Parse a JSON-encoded tag list from the database."""
    try:
        return json.loads(tags_json) if tags_json else []
    except (ValueError, TypeError):
        return []
