# routes/pages.py
from typing import Annotated

from litestar import Router, get, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Redirect, Template

from db.schema import get_content, parse_tags
from db.tables import Post, Project


@get("/")
async def index(request: HTMXRequest) -> Template:
    content = {
        "hero_headline": await get_content("home.hero_headline"),
        "hero_subtext":  await get_content("home.hero_subtext"),
        "about":         await get_content("home.about"),
    }
    raw_posts = await (
        Post.select(Post.title, Post.slug, Post.summary, Post.tags, Post.created_at)
        .where(Post.published.eq(True))
        .order_by(Post.created_at, ascending=False)
        .limit(3)
    )

    def _fmt(p: dict) -> dict:
        r = {**p, "tags": parse_tags(p.get("tags", []))}
        ca = r.get("created_at")
        if ca is not None and hasattr(ca, "strftime"):
            r["created_at"] = ca.strftime("%Y-%m-%d")
        return r

    posts = [_fmt(p) for p in raw_posts]

    raw_projects = await (
        Project.select(
            Project.title, Project.slug, Project.summary,
            Project.tags, Project.url, Project.repo_url,
        )
        .where(Project.published.eq(True))
        .where(Project.featured.eq(True))
        .order_by(Project.created_at, ascending=False)
        .limit(4)
    )
    projects = [{**p, "tags": parse_tags(p.get("tags", []))} for p in raw_projects]

    return Template(
        template_name="pages/index.html",
        context={"content": content, "posts": posts, "projects": projects},
    )


@get("/resume")
async def resume() -> Template:
    content = {
        "intro":      await get_content("resume.intro"),
        "experience": await get_content("resume.experience"),
        "education":  await get_content("resume.education"),
        "skills":     await get_content("resume.skills"),
    }
    return Template(template_name="pages/resume.html", context={"content": content})


@get("/contact")
async def contact_page(success: str | None = None, error: str | None = None) -> Template:
    return Template(
        template_name="pages/contact.html",
        context={
            "intro": await get_content("contact.intro"),
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
            return Template(
                template_name="htmx/contact/error.html",
                context={"error": "All fields are required."},
                status_code=422,
            )
        return Redirect(path="/contact?error=1")

    # TODO: integrate email/notification delivery
    if request.htmx:
        return Template(template_name="htmx/contact/success.html", context={})
    return Redirect(path="/contact?success=1")


pages_router = Router(path="/", route_handlers=[index, resume, contact_page, contact_post])
