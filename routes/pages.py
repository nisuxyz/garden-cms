# routes/pages.py
"""
Dynamic CMS page and collection-item routing.

All public URLs are resolved at runtime from the database:
  GET /              → Page where is_homepage=True
  GET /{slug}        → Page by slug
  GET /{col}/{item}  → CollectionItem detail (with 301 redirect from old slugs)
"""
from litestar import Response, Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect

from cms.engine import (
    render_item,
    render_page,
    resolve_collection_item,
    resolve_homepage,
    resolve_page,
    resolve_slug_redirect,
)
from db.tables import Collection


@get("/")
async def homepage() -> Response:
    page = await resolve_homepage()
    if page is None:
        raise NotFoundException(detail="No homepage configured")
    html = await render_page(page)
    return Response(content=html, media_type="text/html")


@get("/{slug:path}")
async def dynamic_page(slug: str) -> Response | Redirect:
    slug = slug.strip("/")

    # 1. Try matching a Page.
    page = await resolve_page(slug)
    if page is not None:
        html = await render_page(page)
        return Response(content=html, media_type="text/html")

    # 2. Try matching {collection_slug}/{item_slug}.
    parts = slug.split("/", 1)
    if len(parts) == 2:
        col_slug, item_slug = parts

        col, item = await resolve_collection_item(col_slug, item_slug)
        if col is not None and item is not None:
            html = await render_item(col, item)
            return Response(content=html, media_type="text/html")

        # 3. Check slug history for 301 redirect.
        redirect_url = await resolve_slug_redirect(col_slug, item_slug)
        if redirect_url is not None:
            return Redirect(path=redirect_url, status_code=301)

    # 4. Maybe the first segment is a collection slug (bare collection page).
    #    Check if there's a Page whose slug matches the collection slug.
    #    (Collections themselves don't have standalone pages — they're
    #     embedded in Pages via ${collection.*} expressions.)

    raise NotFoundException(detail="Page not found")


pages_router = Router(path="/", route_handlers=[homepage, dynamic_page])
