# routes/admin.py
import hmac
import json
import os
from typing import Annotated

from litestar import Router, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Redirect, Response, Template
from stoolap import AsyncDatabase

from db.schema import get_content, parse_tags, render_md
from middleware.auth import admin_guard


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
    admin_pw = os.getenv("ADMIN_PASSWORD", "")
    if password and admin_pw and hmac.compare_digest(password, admin_pw):
        request.set_session({"admin_authenticated": True})
        return Redirect(path="/admin")
    return Template(template_name="pages/admin/login.html", context={"error": "Invalid password."})


@post("/logout")
async def logout(request: HTMXRequest) -> Redirect:
    request.clear_session()
    return Redirect(path="/admin/login")


# ── Dashboard ──────────────────────────────────────────────

@get("/")
async def dashboard(db: AsyncDatabase) -> Template:
    post_count = (await db.query_one("SELECT COUNT(*) as n FROM posts") or {}).get("n", 0)
    project_count = (await db.query_one("SELECT COUNT(*) as n FROM projects") or {}).get("n", 0)
    return Template(
        template_name="pages/admin/dashboard.html",
        context={"post_count": post_count, "project_count": project_count, "view": "overview"},
    )


# ── Posts ──────────────────────────────────────────────────

@get("/posts")
async def posts_list(db: AsyncDatabase) -> Template:
    rows = await db.query(
        "SELECT id, title, slug, published, created_at FROM posts ORDER BY created_at DESC"
    ) or []
    return Template(
        template_name="pages/admin/dashboard.html",
        context={"posts": rows, "view": "posts", "post_count": len(rows), "project_count": 0},
    )


@get("/posts/new")
async def posts_new() -> Template:
    return Template(template_name="pages/admin/post_edit.html", context={"post": None})


@post("/posts")
async def posts_create(
    db: AsyncDatabase,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    summary = (data.get("summary") or "").strip()
    body = (data.get("body") or "").strip()
    tags_raw = (data.get("tags") or "").strip()
    published = data.get("published") == "on"
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    await db.execute(
        "INSERT INTO posts (title, slug, summary, body, tags, published) "
        "VALUES ($1,$2,$3,$4,$5,$6)",
        [title, slug, summary, body, json.dumps(tags), published],
    )
    return Redirect(path="/admin/posts")


@get("/posts/{post_id:int}/edit")
async def posts_edit(post_id: int, db: AsyncDatabase) -> Template:
    post = await db.query_one("SELECT * FROM posts WHERE id = $1", [post_id])
    if not post:
        raise NotFoundException()
    post = {**post, "tags": parse_tags(post.get("tags", "[]"))}
    return Template(template_name="pages/admin/post_edit.html", context={"post": post})


@post("/posts/{post_id:int}/edit")
async def posts_update(
    post_id: int,
    db: AsyncDatabase,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await db.query_one("SELECT slug FROM posts WHERE id = $1", [post_id])
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
        await db.execute(
            "INSERT INTO post_slug_history (post_id, slug) VALUES ($1, $2)",
            [post_id, old_slug],
        )
    await db.execute(
        "UPDATE posts SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "published=$6, updated_at=CURRENT_TIMESTAMP WHERE id=$7",
        [title, new_slug, summary, body, json.dumps(tags), published, post_id],
    )
    return Redirect(path="/admin/posts")


@post("/posts/{post_id:int}/delete")
async def posts_delete(post_id: int, request: HTMXRequest, db: AsyncDatabase) -> Response | Redirect:
    await db.execute("DELETE FROM post_slug_history WHERE post_id = $1", [post_id])
    await db.execute("DELETE FROM posts WHERE id = $1", [post_id])
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/posts")


# ── Projects ───────────────────────────────────────────────

@get("/projects")
async def projects_list(db: AsyncDatabase) -> Template:
    rows = await db.query(
        "SELECT id, title, slug, published, featured FROM projects ORDER BY created_at DESC"
    ) or []
    return Template(template_name="pages/admin/project_list.html", context={"projects": rows})


@get("/projects/new")
async def projects_new() -> Template:
    return Template(template_name="pages/admin/project_edit.html", context={"project": None})


@post("/projects")
async def projects_create(
    db: AsyncDatabase,
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
    await db.execute(
        "INSERT INTO projects (title, slug, summary, body, tags, url, repo_url, featured, published) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [title, slug, summary, body, json.dumps(tags), url, repo_url, featured, published],
    )
    return Redirect(path="/admin/projects")


@get("/projects/{project_id:int}/edit")
async def projects_edit(project_id: int, db: AsyncDatabase) -> Template:
    project = await db.query_one("SELECT * FROM projects WHERE id = $1", [project_id])
    if not project:
        raise NotFoundException()
    project = {**project, "tags": parse_tags(project.get("tags", "[]"))}
    return Template(template_name="pages/admin/project_edit.html", context={"project": project})


@post("/projects/{project_id:int}/edit")
async def projects_update(
    project_id: int,
    db: AsyncDatabase,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await db.query_one("SELECT slug FROM projects WHERE id = $1", [project_id])
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
        await db.execute(
            "INSERT INTO project_slug_history (project_id, slug) VALUES ($1, $2)",
            [project_id, old_slug],
        )
    await db.execute(
        "UPDATE projects SET title=$1, slug=$2, summary=$3, body=$4, tags=$5, "
        "url=$6, repo_url=$7, featured=$8, published=$9, updated_at=CURRENT_TIMESTAMP "
        "WHERE id=$10",
        [title, new_slug, summary, body, json.dumps(tags), url, repo_url, featured, published, project_id],
    )
    return Redirect(path="/admin/projects")


@post("/projects/{project_id:int}/delete")
async def projects_delete(project_id: int, request: HTMXRequest, db: AsyncDatabase) -> Response | Redirect:
    await db.execute("DELETE FROM project_slug_history WHERE project_id = $1", [project_id])
    await db.execute("DELETE FROM projects WHERE id = $1", [project_id])
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/projects")


# ── Site Content ───────────────────────────────────────────

@get("/content")
async def content_list(db: AsyncDatabase) -> Template:
    rows = await db.query(
        "SELECT content_key as key, value, label, is_markdown, updated_at FROM site_content ORDER BY content_key"
    ) or []
    return Template(template_name="pages/admin/content.html", context={"blocks": rows})


@post("/content/{key:str}")
async def content_update(
    key: str,
    request: HTMXRequest,
    db: AsyncDatabase,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response | Redirect:
    if not await db.query_one("SELECT content_key FROM site_content WHERE content_key = $1", [key]):
        raise NotFoundException()
    value = (data.get("value") or "").strip()
    await db.execute(
        "UPDATE site_content SET value=$1, updated_at=CURRENT_TIMESTAMP WHERE content_key=$2",
        [value, key],
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

_guarded_router = Router(path="/", route_handlers=_guarded_handlers, guards=[admin_guard])
admin_router = Router(path="/admin", route_handlers=[*_public_handlers, _guarded_router])
