# routes/projects.py
from bustapi import Blueprint, request
from bustapi import redirect

from db.connection import get_db
from db.schema import parse_tags, render_md
from routes import render

projects_bp = Blueprint("projects", __name__)
_PER_PAGE = 12


def _enrich(row: dict) -> dict:
    return {**row, "tags": parse_tags(row.get("tags", "[]"))}


@projects_bp.route("/projects")
def projects_index():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("pages/projects.html",
                  projects=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@projects_bp.route("/projects/feed")
def projects_feed():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, url, repo_url, featured FROM projects "
        "WHERE published = $1 ORDER BY featured DESC, created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("htmx/projects/grid.html",
                  projects=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@projects_bp.route("/projects/<slug>")
def project_detail(slug: str):
    db = get_db()
    row = db.query_one(
        "SELECT * FROM projects WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        project = {**_enrich(row), "body_html": render_md(row["body"])}
        return render("pages/post.html", post=project, content_type="project")

    history = db.query_one(
        "SELECT p.slug FROM projects p "
        "JOIN project_slug_history h ON h.project_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return redirect(f"/projects/{history['slug']}", 301)
    from bustapi.http.response import Response
    return Response("Not Found", status=404)
