# routes/pages.py
"""
Dynamic CMS page and collection-item routing.

All public URLs are resolved at runtime from the database:
  GET /              → Page where is_homepage=True
  GET /{slug}        → Page by slug
  GET /{col}/{item}  → CollectionItem detail (with 301 redirect from old slugs)
"""
import logging
from pathlib import Path

from litestar import Response, Router, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect

from cms.engine import (
    render_item,
    render_md_page,
    render_page,
    resolve_collection_item,
    resolve_homepage,
    resolve_page,
    resolve_slug_redirect,
)
from cms.markdown import load_md_mounts, resolve_md_file
from cms.storage import get_backend
from db.tables import Collection, SiteSettings

log = logging.getLogger(__name__)


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
    #     embedded in Pages via <CollectionFeed /> components.)

    # 5. Try matching a markdown mount.
    mounts = await load_md_mounts()
    # Build reverse lookup: slug_prefix → dir_name
    slug_to_dir = {v: k for k, v in mounts.items()}
    # Check if any mount prefix matches.
    for prefix, dir_name in slug_to_dir.items():
        if slug == prefix or slug.startswith(prefix + "/"):
            sub_path = slug[len(prefix):].strip("/")
            if not sub_path:
                # Bare mount URL (e.g. /docs) — try index.md
                sub_path = "index"
            result = resolve_md_file(dir_name, sub_path)
            if result is not None:
                title, content_html, layout_source = result
                html = await render_md_page(content_html, title, layout_source)
                return Response(content=html, media_type="text/html")

    raise NotFoundException(detail="Page not found")


_FALLBACK_FAVICON = Path("static/favicon.svg")


@get("/favicon.ico")
async def favicon() -> Response:
    """Serve the user-configured favicon, or fall back to the static default."""
    rows = await (
        SiteSettings.select(SiteSettings.value)
        .where(SiteSettings.key == "favicon")
        .limit(1)
    )
    chosen = rows[0]["value"] if rows and rows[0].get("value") else None

    if chosen:
        backend = get_backend()
        try:
            body, content_type = await backend.get_object(chosen)
            return Response(
                content=body,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
        except Exception:
            log.warning("Configured favicon %r not found, using fallback", chosen)

    # Fallback to static file on disk.
    if _FALLBACK_FAVICON.exists():
        body = _FALLBACK_FAVICON.read_bytes()
        return Response(
            content=body,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    raise NotFoundException(detail="No favicon available")


pages_router = Router(path="/", route_handlers=[homepage, dynamic_page])
