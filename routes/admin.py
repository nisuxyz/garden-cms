# routes/admin.py
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Annotated

from litestar import Router, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Redirect, Response, Template

from db.schema import get_content, parse_tags, render_md
from db.tables import (
    Post,
    PostSlugHistory,
    Project,
    ProjectSlugHistory,
    SiteContent,
)
from middleware.auth import admin_guard

# Optional: attempt to import Piccolo's BaseUser for the enhanced auth path.
# Falls back gracefully to env-var auth when piccolo user tables aren't available.
try:
    from piccolo.apps.user.tables import BaseUser

    _HAS_BASEUSER = True
except Exception:  # pragma: no cover
    _HAS_BASEUSER = False


# ── Auth ───────────────────────────────────────────────────

@get("/login")
async def login_page() -> Template:
    return Template(template_name="pages/admin/login.html", context={"error": None})


@post("/login")
async def login_submit(
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Template | Redirect:
    password = (data.get("password") or "").strip()
    username = (data.get("username") or "").strip()

    authenticated = False

    # Path 1: Piccolo BaseUser (preferred when available)
    if _HAS_BASEUSER and username:
        user_id = await BaseUser.login(username=username, password=password)
        if user_id is not None:
            authenticated = True

    # Path 2: Legacy env-var password (fallback)
    if not authenticated:
        admin_pw = os.getenv("ADMIN_PASSWORD", "")
        if password and admin_pw and hmac.compare_digest(password, admin_pw):
            authenticated = True

    if authenticated:
        request.set_session({"admin_authenticated": True})
        return Redirect(path="/admin")

    return Template(
        template_name="pages/admin/login.html",
        context={"error": "Invalid credentials."},
    )


@post("/logout")
async def logout(request: HTMXRequest) -> Redirect:
    request.clear_session()
    return Redirect(path="/admin/login")


# ── Dashboard ──────────────────────────────────────────────

@get("/")
async def dashboard() -> Template:
    post_rows = await Post.select(Post.id).output(as_list=True)
    project_rows = await Project.select(Project.id).output(as_list=True)
    return Template(
        template_name="pages/admin/dashboard.html",
        context={
            "post_count": len(post_rows),
            "project_count": len(project_rows),
            "view": "overview",
        },
    )


# ── Posts ──────────────────────────────────────────────────

@get("/posts")
async def posts_list() -> Template:
    rows = await (
        Post.select(Post.id, Post.title, Post.slug, Post.published, Post.created_at)
        .order_by(Post.created_at, ascending=False)
    )
    return Template(
        template_name="pages/admin/dashboard.html",
        context={
            "posts": rows,
            "view": "posts",
            "post_count": len(rows),
            "project_count": 0,
        },
    )


@get("/posts/new")
async def posts_new() -> Template:
    return Template(template_name="pages/admin/post_edit.html", context={"post": None})


@post("/posts")
async def posts_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    summary = (data.get("summary") or "").strip()
    body = (data.get("body") or "").strip()
    tags_raw = (data.get("tags") or "").strip()
    published = data.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    await Post(
        title=title,
        slug=slug,
        summary=summary,
        body=body,
        tags=tags,
        published=published,
    ).save()
    return Redirect(path="/admin/posts")


@get("/posts/{post_id:int}/edit")
async def posts_edit(post_id: int) -> Template:
    row = await Post.select().where(Post.id == post_id).first()
    if not row:
        raise NotFoundException()
    row["tags"] = parse_tags(row.get("tags", []))
    return Template(template_name="pages/admin/post_edit.html", context={"post": row})


@post("/posts/{post_id:int}/edit")
async def posts_update(
    post_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await Post.select(Post.slug).where(Post.id == post_id).first()
    if not existing:
        raise NotFoundException()
    title = (data.get("title") or "").strip()
    new_slug = (data.get("slug") or "").strip()
    summary = (data.get("summary") or "").strip()
    body = (data.get("body") or "").strip()
    tags_raw = (data.get("tags") or "").strip()
    published = data.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug = existing["slug"]
    if new_slug != old_slug:
        await PostSlugHistory(post=post_id, slug=old_slug).save()
    await Post.update(
        {
            Post.title: title,
            Post.slug: new_slug,
            Post.summary: summary,
            Post.body: body,
            Post.tags: tags,
            Post.published: published,
            Post.updated_at: datetime.now(timezone.utc),
        }
    ).where(Post.id == post_id)
    return Redirect(path="/admin/posts")


@post("/posts/{post_id:int}/delete")
async def posts_delete(post_id: int, request: HTMXRequest) -> Response | Redirect:
    await PostSlugHistory.delete().where(PostSlugHistory.post == post_id)
    await Post.delete().where(Post.id == post_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/posts")


# ── Projects ───────────────────────────────────────────────

@get("/projects")
async def projects_list() -> Template:
    rows = await (
        Project.select(
            Project.id, Project.title, Project.slug,
            Project.published, Project.featured,
        )
        .order_by(Project.created_at, ascending=False)
    )
    return Template(
        template_name="pages/admin/project_list.html",
        context={"projects": rows},
    )


@get("/projects/new")
async def projects_new() -> Template:
    return Template(
        template_name="pages/admin/project_edit.html",
        context={"project": None},
    )


@post("/projects")
async def projects_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    summary = (data.get("summary") or "").strip()
    body = (data.get("body") or "").strip()
    tags_raw = (data.get("tags") or "").strip()
    url = (data.get("url") or "").strip() or None
    repo_url = (data.get("repo_url") or "").strip() or None
    featured = data.get("featured") == "on"
    published = data.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    await Project(
        title=title,
        slug=slug,
        summary=summary,
        body=body,
        tags=tags,
        url=url,
        repo_url=repo_url,
        featured=featured,
        published=published,
    ).save()
    return Redirect(path="/admin/projects")


@get("/projects/{project_id:int}/edit")
async def projects_edit(project_id: int) -> Template:
    row = await Project.select().where(Project.id == project_id).first()
    if not row:
        raise NotFoundException()
    row["tags"] = parse_tags(row.get("tags", []))
    return Template(
        template_name="pages/admin/project_edit.html",
        context={"project": row},
    )


@post("/projects/{project_id:int}/edit")
async def projects_update(
    project_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await (
        Project.select(Project.slug).where(Project.id == project_id).first()
    )
    if not existing:
        raise NotFoundException()
    title = (data.get("title") or "").strip()
    new_slug = (data.get("slug") or "").strip()
    summary = (data.get("summary") or "").strip()
    body = (data.get("body") or "").strip()
    tags_raw = (data.get("tags") or "").strip()
    url = (data.get("url") or "").strip() or None
    repo_url = (data.get("repo_url") or "").strip() or None
    featured = data.get("featured") == "on"
    published = data.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    old_slug = existing["slug"]
    if new_slug != old_slug:
        await ProjectSlugHistory(project=project_id, slug=old_slug).save()
    await Project.update(
        {
            Project.title: title,
            Project.slug: new_slug,
            Project.summary: summary,
            Project.body: body,
            Project.tags: tags,
            Project.url: url,
            Project.repo_url: repo_url,
            Project.featured: featured,
            Project.published: published,
            Project.updated_at: datetime.now(timezone.utc),
        }
    ).where(Project.id == project_id)
    return Redirect(path="/admin/projects")


@post("/projects/{project_id:int}/delete")
async def projects_delete(
    project_id: int, request: HTMXRequest,
) -> Response | Redirect:
    await ProjectSlugHistory.delete().where(
        ProjectSlugHistory.project == project_id,
    )
    await Project.delete().where(Project.id == project_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/projects")


# ── Site Content ───────────────────────────────────────────

@get("/content")
async def content_list() -> Template:
    rows = await (
        SiteContent.select(
            SiteContent.content_key,
            SiteContent.value,
            SiteContent.label,
            SiteContent.is_markdown,
            SiteContent.updated_at,
        )
        .order_by(SiteContent.content_key)
    )
    # Template expects "key" not "content_key"
    blocks = [{**r, "key": r["content_key"]} for r in rows]
    return Template(
        template_name="pages/admin/content.html",
        context={"blocks": blocks},
    )


@post("/content/{key:str}")
async def content_update(
    key: str,
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response | Redirect:
    exists = await SiteContent.exists().where(SiteContent.content_key == key)
    if not exists:
        raise NotFoundException()
    value = (data.get("value") or "").strip()
    await (
        SiteContent.update({
            SiteContent.value: value,
        })
        .where(SiteContent.content_key == key)
    )
    if request.htmx:
        safe_id = key.replace(".", "-")
        return Response(
            content=f'<span id="saved-{safe_id}" class="meta"><ins>Saved ✓</ins></span>',
            status_code=200,
            media_type="text/html",
        )
    return Redirect(path="/admin/content")


# ── Guarded and unguarded handlers ─────────────────────────
# Login/logout don't require auth; everything else does.

_public_handlers = [login_page, login_submit, logout]
_guarded_handlers = [
    dashboard, posts_list, posts_new, posts_create, posts_edit, posts_update,
    posts_delete, projects_list, projects_new, projects_create, projects_edit,
    projects_update, projects_delete, content_list, content_update,
]

_guarded_router = Router(
    path="/", route_handlers=_guarded_handlers, guards=[admin_guard],
)
admin_router = Router(
    path="/admin", route_handlers=[*_public_handlers, _guarded_router],
)
