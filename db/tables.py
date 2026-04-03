# db/tables.py
"""Piccolo ORM table definitions for site content."""
from piccolo.columns import (
    JSON,
    Boolean,
    ForeignKey,
    Text,
    Timestamptz,
    Varchar,
)
from piccolo.table import Table


class Post(Table, tablename="posts"):
    """Blog post."""

    title = Text(required=True)
    slug = Varchar(length=255, unique=True, required=True)
    summary = Text(required=True)
    body = Text(required=True)
    tags = JSON(default=[])
    published = Boolean(default=False)
    created_at = Timestamptz(auto_update=False)
    updated_at = Timestamptz(auto_update=True)


class PostSlugHistory(Table, tablename="post_slug_history"):
    """Tracks old slugs so we can 301-redirect after a rename."""

    post = ForeignKey(references=Post, required=True)
    slug = Varchar(length=255, unique=True, required=True)
    created_at = Timestamptz(auto_update=False)


class Project(Table, tablename="projects"):
    """Portfolio / showcase project."""

    title = Text(required=True)
    slug = Varchar(length=255, unique=True, required=True)
    summary = Text(required=True)
    body = Text(required=True)
    tags = JSON(default=[])
    url = Varchar(length=500, null=True, default=None)
    repo_url = Varchar(length=500, null=True, default=None)
    featured = Boolean(default=False)
    published = Boolean(default=False)
    created_at = Timestamptz(auto_update=False)
    updated_at = Timestamptz(auto_update=True)


class ProjectSlugHistory(Table, tablename="project_slug_history"):
    """Tracks old slugs so we can 301-redirect after a rename."""

    project = ForeignKey(references=Project, required=True)
    slug = Varchar(length=255, unique=True, required=True)
    created_at = Timestamptz(auto_update=False)


class SiteContent(Table, tablename="site_content"):
    """Key-value store for editable site copy (hero text, resume sections, …)."""

    content_key = Varchar(length=255, unique=True, required=True)
    value = Text(required=True)
    label = Varchar(length=255, required=True)
    is_markdown = Boolean(default=True)
    updated_at = Timestamptz(auto_update=True)
