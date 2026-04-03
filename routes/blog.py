# routes/blog.py
from litestar import Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template
from stoolap import AsyncDatabase

from db.schema import parse_tags, render_md

_PER_PAGE = 10


def _enrich(row: dict) -> dict:
    result = {**row, "tags": parse_tags(row.get("tags", "[]"))}
    ca = result.get("created_at")
    if ca is not None and hasattr(ca, "strftime"):
        result["created_at"] = ca.strftime("%Y-%m-%d")
    return result


@get("/")
async def blog_index(db: AsyncDatabase, page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="pages/blog.html",
        context={"posts": [_enrich(p) for p in raw[:_PER_PAGE]], "has_more": has_more, "next_page": page + 1},
    )


@get("/feed")
async def blog_feed(db: AsyncDatabase, page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        [True, _PER_PAGE + 1, offset],
    ) or []
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="htmx/blog/list.html",
        context={"posts": [_enrich(p) for p in raw[:_PER_PAGE]], "has_more": has_more, "next_page": page + 1},
    )


@get("/{slug:str}")
async def blog_post(slug: str, db: AsyncDatabase) -> Template | Redirect:
    row = await db.query_one(
        "SELECT * FROM posts WHERE slug = $1 AND published = $2", [slug, True]
    )
    if row:
        post = {**_enrich(row), "body_html": render_md(row["body"])}
        return Template(template_name="pages/post.html", context={"post": post, "content_type": "post"})

    history = await db.query_one(
        "SELECT p.slug FROM posts p "
        "JOIN post_slug_history h ON h.post_id = p.id "
        "WHERE h.slug = $1 AND p.published = $2",
        [slug, True],
    )
    if history:
        return Redirect(path=f"/blog/{history['slug']}", status_code=301)
    raise NotFoundException()


blog_router = Router(path="/blog", route_handlers=[blog_index, blog_feed, blog_post])
