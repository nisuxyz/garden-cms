# routes/blog.py
from litestar import Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template

from db.schema import parse_tags, render_md
from db.tables import Post, PostSlugHistory

_PER_PAGE = 10


def _enrich(row: dict) -> dict:
    result = {**row, "tags": parse_tags(row.get("tags", []))}
    ca = result.get("created_at")
    if ca is not None and hasattr(ca, "strftime"):
        result["created_at"] = ca.strftime("%Y-%m-%d")
    return result


@get("/")
async def blog_index(page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await (
        Post.select(Post.title, Post.slug, Post.summary, Post.tags, Post.created_at)
        .where(Post.published.eq(True))
        .order_by(Post.created_at, ascending=False)
        .limit(_PER_PAGE + 1)
        .offset(offset)
    )
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="pages/blog.html",
        context={
            "posts": [_enrich(p) for p in raw[:_PER_PAGE]],
            "has_more": has_more,
            "next_page": page + 1,
        },
    )


@get("/feed")
async def blog_feed(page: int = 1) -> Template:
    offset = (page - 1) * _PER_PAGE
    raw = await (
        Post.select(Post.title, Post.slug, Post.summary, Post.tags, Post.created_at)
        .where(Post.published.eq(True))
        .order_by(Post.created_at, ascending=False)
        .limit(_PER_PAGE + 1)
        .offset(offset)
    )
    has_more = len(raw) > _PER_PAGE
    return Template(
        template_name="htmx/blog/list.html",
        context={
            "posts": [_enrich(p) for p in raw[:_PER_PAGE]],
            "has_more": has_more,
            "next_page": page + 1,
        },
    )


@get("/{slug:str}")
async def blog_post(slug: str) -> Template | Redirect:
    row = await (
        Post.select()
        .where(Post.slug == slug)
        .where(Post.published.eq(True))
        .first()
    )
    if row:
        post = {**_enrich(row), "body_html": render_md(row["body"])}
        return Template(
            template_name="pages/post.html",
            context={"post": post, "content_type": "post"},
        )

    # Check slug history for 301 redirect
    history = await (
        PostSlugHistory.select(PostSlugHistory.post)
        .where(PostSlugHistory.slug == slug)
        .first()
    )
    if history:
        current = await (
            Post.select(Post.slug)
            .where(Post.id == history["post"])
            .where(Post.published.eq(True))
            .first()
        )
        if current:
            return Redirect(path=f"/blog/{current['slug']}", status_code=301)

    raise NotFoundException()


blog_router = Router(path="/blog", route_handlers=[blog_index, blog_feed, blog_post])
