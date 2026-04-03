# routes/blog.py
from bustapi import Blueprint, request
from bustapi import redirect

from db.connection import get_db
from db.schema import parse_tags, render_md
from routes import render

blog_bp = Blueprint("blog", __name__)
_PER_PAGE = 10


def _enrich(row: dict) -> dict:
    return {**row, "tags": parse_tags(row.get("tags", "[]"))}


@blog_bp.route("/blog")
def blog_index():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("pages/blog.html",
                  posts=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@blog_bp.route("/blog/feed")
def blog_feed():
    db = get_db()
    page   = int(request.args.get("page", 1))
    offset = (page - 1) * _PER_PAGE
    raw = db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return render("htmx/blog/list.html",
                  posts=[_enrich(p) for p in raw[:_PER_PAGE]],
                  has_more=has_more, next_page=page + 1)


@blog_bp.route("/blog/<slug>")
def blog_post(slug: str):
    db = get_db()
    row = db.query_one(
        "SELECT * FROM posts WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        post = {**_enrich(row), "body_html": render_md(row["body"])}
        return render("pages/post.html", post=post, content_type="post")

    history = db.query_one(
        "SELECT p.slug FROM posts p "
        "JOIN post_slug_history h ON h.post_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return redirect(f"/blog/{history['slug']}", 301)
    from bustapi.http.response import Response
    return Response("Not Found", status=404)
