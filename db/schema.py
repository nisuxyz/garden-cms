# db/schema.py
"""
Utility helpers (markdown rendering, tag parsing, content lookup)
and database seed logic.

Table *definitions* live in ``db.tables``.
"""
import json

from markdown_it import MarkdownIt

from db.tables import SiteContent

_md = MarkdownIt()

# ── Seed data ──────────────────────────────────────────────

_CONTENT_SEEDS: list[tuple[str, str, str, bool]] = [
    ("home.hero_headline", "Hello, I'm Nisu.", "Landing page headline", False),
    ("home.hero_subtext", "Developer, maker, and curious human.", "Landing page subtext", False),
    ("home.about", "I build things, explore ideas, and share what I learn.", "About blurb", True),
    ("resume.intro", "Here's a snapshot of where I've been and what I've built.", "Resume intro", True),
    ("resume.experience", "## Experience\n\n*Add your experience here.*", "Experience section", True),
    ("resume.education", "## Education\n\n*Add your education here.*", "Education section", True),
    ("resume.skills", "## Skills\n\n*Add your skills here.*", "Skills section", True),
    ("contact.intro", "Have a question or want to say hello?", "Contact page intro", True),
]


async def init_db() -> None:
    """Seed default site_content rows (idempotent)."""
    for key, value, label, is_markdown in _CONTENT_SEEDS:
        exists = await SiteContent.exists().where(
            SiteContent.content_key == key,
        )
        if not exists:
            await SiteContent(
                content_key=key,
                value=value,
                label=label,
                is_markdown=is_markdown,
            ).save()


# ── Template helpers ───────────────────────────────────────

def render_md(text: str) -> str:
    """Render a Markdown string to HTML."""
    return _md.render(text)


async def get_content(key: str) -> str:
    """Fetch a ``site_content`` value by key.

    Returns rendered HTML (if the row is Markdown) or raw text.
    Returns ``""`` when the key doesn't exist.
    """
    row = (
        await SiteContent.select(SiteContent.value, SiteContent.is_markdown)
        .where(SiteContent.content_key == key)
        .first()
    )
    if not row:
        return ""
    return render_md(row["value"]) if row["is_markdown"] else row["value"]


def parse_tags(tags: str | list) -> list[str]:
    """Normalise a tag value coming from the database.

    Piccolo stores JSON columns as Python objects, but we also accept
    a raw JSON string for backwards-compat and template convenience.
    """
    if isinstance(tags, list):
        return tags
    try:
        return json.loads(tags) if tags else []
    except (ValueError, TypeError):
        return []
