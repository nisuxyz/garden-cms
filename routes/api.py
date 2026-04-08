# routes/api.py
"""
HTMX API endpoints for paginated collection feeds.
"""
from litestar import Response, Router, get
from litestar.exceptions import NotFoundException

from cms.engine import render_collection_feed


@get("/collection/{slug:str}/feed")
async def collection_feed(slug: str, page: int = 1) -> Response:
    """Return rendered card HTML for one page of a collection."""
    html = await render_collection_feed(slug, page=page)
    if html is None:
        raise NotFoundException(detail="Collection not found")
    return Response(content=html, media_type="text/html")


api_router = Router(path="/api", route_handlers=[collection_feed])
