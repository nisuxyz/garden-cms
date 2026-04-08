# db/schema.py
"""
Utility helpers (markdown rendering) for the CMS.

Table *definitions* live in ``db.tables``.
"""
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": True})


def render_md(text: str) -> str:
    """Render a Markdown string to HTML."""
    return _md.render(text)
