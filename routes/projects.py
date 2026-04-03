# routes/projects.py
from litestar import Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template

from db.schema import parse_tags, render_md
from db.tables import Project, ProjectSlugHistory

_PER_PAGE = 12


def _enrich(row: dict) -> dict:
    result = {**row, "tags": parse_tags(row.get("tags", []))}
    ca = result.get("created_at")
    if ca is not None and hasattr(ca, "strftime"):
        result["created_at"] = ca.strftime("%Y-%m-%d")
    return result


@get("/")
async def projects_index(page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await (
        Project.select(
            Project.title, Project.slug, Project.summary,
            Project.tags, Project.url, Project.repo_url, Project.featured,
        )
        .where(Project.published.eq(True))
        .order_by(Project.featured, ascending=False)
        .order_by(Project.created_at, ascending=False)
        .limit(_PER_PAGE + 1)
        .offset(offset)
    )
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="pages/projects.html",
        context={
            "projects": [_enrich(p) for p in raw[:_PER_PAGE]],
            "has_more": has_more,
            "next_page": page + 1,
        },
    )


@get("/feed")
async def projects_feed(page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await (
        Project.select(
            Project.title, Project.slug, Project.summary,
            Project.tags, Project.url, Project.repo_url, Project.featured,
        )
        .where(Project.published.eq(True))
        .order_by(Project.featured, ascending=False)
        .order_by(Project.created_at, ascending=False)
        .limit(_PER_PAGE + 1)
        .offset(offset)
    )
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="htmx/projects/grid.html",
        context={
            "projects": [_enrich(p) for p in raw[:_PER_PAGE]],
            "has_more": has_more,
            "next_page": page + 1,
        },
    )


@get("/{slug:str}")
async def project_detail(slug: str) -> Template | Redirect:
    row = await (
        Project.select()
        .where(Project.slug == slug)
        .where(Project.published.eq(True))
        .first()
    )
    if row:
        project = {**_enrich(row), "body_html": render_md(row["body"])}
        return Template(
            template_name="pages/post.html",
            context={"post": project, "content_type": "project"},
        )

    # Check slug history for 301 redirect
    history = await (
        ProjectSlugHistory.select(ProjectSlugHistory.project)
        .where(ProjectSlugHistory.slug == slug)
        .first()
    )
    if history:
        current = await (
            Project.select(Project.slug)
            .where(Project.id == history["project"])
            .where(Project.published.eq(True))
            .first()
        )
        if current:
            return Redirect(path=f"/projects/{current['slug']}", status_code=301)

    raise NotFoundException()


projects_router = Router(
    path="/projects",
    route_handlers=[projects_index, projects_feed, project_detail],
)
