# routes/projects.py
from litestar import Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template
from stoolap import AsyncDatabase

from db.schema import parse_tags, render_md

_PER_PAGE = 12


def _enrich(row: dict) -> dict:
    result = {**row, "tags": parse_tags(row.get("tags", "[]"))}
    ca = result.get("created_at")
    if ca is not None and hasattr(ca, "strftime"):
        result["created_at"] = ca.strftime("%Y-%m-%d")
    return result


@get("/")
async def projects_index(db: AsyncDatabase, page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="pages/projects.html",
        context={"projects": [_enrich(p) for p in raw[:_PER_PAGE]], "has_more": has_more, "next_page": page + 1},
    )


@get("/feed")
async def projects_feed(db: AsyncDatabase, page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="htmx/projects/grid.html",
        context={"projects": [_enrich(p) for p in raw[:_PER_PAGE]], "has_more": has_more, "next_page": page + 1},
    )


@get("/{slug:str}")
async def project_detail(slug: str, db: AsyncDatabase) -> Template | Redirect:
    row = await db.query_one(
        "SELECT * FROM projects WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        project = {**_enrich(row), "body_html": render_md(row["body"])}
        return Template(template_name="pages/post.html", context={"post": project, "content_type": "project"})

    history = await db.query_one(
        "SELECT p.slug FROM projects p "
        "JOIN project_slug_history h ON h.project_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return Redirect(path=f"/projects/{history['slug']}", status_code=301)
    raise NotFoundException()


projects_router = Router(path="/projects", route_handlers=[projects_index, projects_feed, project_detail])
