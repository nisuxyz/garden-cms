# routes/pages.py
from typing import Annotated

from litestar import Router, get, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Redirect, Template
from stoolap import AsyncDatabase

from db.schema import get_content, parse_tags


@get("/")
async def index(request: HTMXRequest, db: AsyncDatabase) -> Template:
    content = {
        "hero_headline": await get_content(db, "home.hero_headline"),
        "hero_subtext":  await get_content(db, "home.hero_subtext"),
        "about":         await get_content(db, "home.about"),
    }
    raw_posts = await db.query(
        "SELECT title, slug, summary, tags, created_at FROM posts "
        "WHERE published = $1 ORDER BY created_at DESC LIMIT $2",
        [True, 3],
    ) or []

    def _fmt(p: dict) -> dict:
        r = {**p, "tags": parse_tags(p.get("tags", "[]"))}
        ca = r.get("created_at")
        if ca is not None and hasattr(ca, "strftime"):
            r["created_at"] = ca.strftime("%Y-%m-%d")
        return r

    posts = [_fmt(p) for p in raw_posts]

    raw_projects = await db.query(
        "SELECT title, slug, summary, tags, url, repo_url FROM projects "
        "WHERE published = $1 AND featured = $2 ORDER BY created_at DESC LIMIT $3",
        [True, True, 4],
    ) or []
    projects = [{**p, "tags": parse_tags(p.get("tags", "[]"))} for p in raw_projects]

    return Template(template_name="pages/index.html", context={"content": content, "posts": posts, "projects": projects})


@get("/resume")
async def resume(db: AsyncDatabase) -> Template:
    content = {
        "intro":      await get_content(db, "resume.intro"),
        "experience": await get_content(db, "resume.experience"),
        "education":  await get_content(db, "resume.education"),
        "skills":     await get_content(db, "resume.skills"),
    }
    return Template(template_name="pages/resume.html", context={"content": content})


@get("/contact")
async def contact_page(db: AsyncDatabase, success: str | None = None, error: str | None = None) -> Template:
    return Template(
        template_name="pages/contact.html",
        context={
            "intro": await get_content(db, "contact.intro"),
            "success": success == "1",
            "error_msg": error == "1",
        },
    )


@post("/contact")
async def contact_post(
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Template | Redirect:
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not (name and email and message):
        if request.htmx:
            return Template(template_name="htmx/contact/error.html", context={"error": "All fields are required."}, status_code=422)
        return Redirect(path="/contact?error=1")

    # TODO: integrate email/notification delivery
    if request.htmx:
        return Template(template_name="htmx/contact/success.html", context={})
    return Redirect(path="/contact?success=1")


pages_router = Router(path="/", route_handlers=[index, resume, contact_page, contact_post])
