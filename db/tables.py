# db/tables.py
"""Piccolo ORM table definitions for the generic CMS."""
from datetime import datetime

from piccolo.columns import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    Text,
    Timestamptz,
    Varchar,
)
from piccolo.table import Table


# ── Theming ────────────────────────────────────────────────


class Theme(Table, tablename="themes"):
    """Visual theme — stores a Jinja2 base template + CSS."""

    name = Text(required=True)
    slug = Varchar(length=255, unique=True, required=True)
    base_template = Text(required=True)
    css = Text(default="")
    active = Boolean(default=False)
    created_at = Timestamptz()
    updated_at = Timestamptz(auto_update=datetime.now)


# ── Pages ──────────────────────────────────────────────────


class Page(Table, tablename="pages"):
    """A CMS page. Body is Markdown with ${} expressions."""

    title = Text(required=True)
    slug = Varchar(length=255, unique=True, required=True)
    body_md = Text(default="")
    meta_description = Text(null=True, default=None)
    is_homepage = Boolean(default=False)
    show_in_nav = Boolean(default=True)
    nav_order = Integer(default=0)
    published = Boolean(default=False)
    theme = ForeignKey(references=Theme, null=True, default=None)
    created_at = Timestamptz()
    updated_at = Timestamptz(auto_update=datetime.now)


# ── Content blocks ─────────────────────────────────────────


class ContentBlock(Table, tablename="content_blocks"):
    """Global key/value content — text, markdown, or image reference."""

    key = Varchar(length=255, unique=True, required=True)
    label = Varchar(length=255, required=True)
    block_type = Varchar(length=50, default="text")  # text | markdown | image
    value = Text(default="")
    created_at = Timestamptz()
    updated_at = Timestamptz(auto_update=datetime.now)


# ── Collections ────────────────────────────────────────────


class Collection(Table, tablename="collections"):
    """A user-defined collection type (e.g. blog, projects)."""

    name = Text(required=True)
    slug = Varchar(length=255, unique=True, required=True)
    description = Text(null=True, default=None)
    fields_schema = JSON(default=[])  # [{name, type, required}, …]
    card_template = Text(default="")  # HTML with ${item.*}
    detail_template = Text(default="")  # Markdown with ${item.*}
    items_per_page = Integer(default=10)
    created_at = Timestamptz()
    updated_at = Timestamptz(auto_update=datetime.now)


class CollectionItem(Table, tablename="collection_items"):
    """An entry in a Collection."""

    collection = ForeignKey(references=Collection, required=True)
    title = Text(required=True)
    slug = Varchar(length=255, required=True)
    data = JSON(default={})  # field values matching fields_schema
    published = Boolean(default=False)
    featured = Boolean(default=False)
    sort_order = Integer(default=0)
    created_at = Timestamptz()
    updated_at = Timestamptz(auto_update=datetime.now)


class CollectionItemSlugHistory(Table, tablename="collection_item_slug_history"):
    """Tracks old slugs for 301 redirects after renames."""

    item = ForeignKey(references=CollectionItem, required=True)
    collection_slug = Varchar(length=255, required=True)
    old_slug = Varchar(length=255, required=True)
    created_at = Timestamptz()


# ── Media ──────────────────────────────────────────────────


class MediaFile(Table, tablename="media_files"):
    """An uploaded file (image, etc.)."""

    filename = Varchar(length=255, unique=True, required=True)
    original_name = Varchar(length=255, required=True)
    file_path = Varchar(length=500, required=True)
    mime_type = Varchar(length=100, required=True)
    alt_text = Text(null=True, default=None)
    file_size = Integer(default=0)
    created_at = Timestamptz()
