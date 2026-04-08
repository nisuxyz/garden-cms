# routes/admin.py
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated

from litestar import Router, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest
from litestar.response import Redirect, Response, Template

from db.tables import ContentBlock, Page
from middleware.auth import admin_guard
from middleware.oauth import (
    check_group_membership,
    exchange_code,
    get_authorization_url,
    oauth_configured,
)

# Optional: attempt to import Piccolo's BaseUser for the enhanced auth path.
# Falls back gracefully to env-var auth when piccolo user tables aren't available.
try:
    from piccolo.apps.user.tables import BaseUser

    _HAS_BASEUSER = True
except Exception:  # pragma: no cover
    _HAS_BASEUSER = False

_log = logging.getLogger(__name__)


# ── Auth ───────────────────────────────────────────────────

@get("/login")
async def login_page(error: str | None = None) -> Template:
    return Template(
        template_name="admin/login.html",
        context={"error": error, "oauth_enabled": oauth_configured()},
    )


@post("/login")
async def login_submit(
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Template | Redirect:
    password = (data.get("password") or "").strip()
    username = (data.get("username") or "").strip()

    authenticated = False

    # Path 1: Piccolo BaseUser (preferred when available)
    if _HAS_BASEUSER and username:
        user_id = await BaseUser.login(username=username, password=password)
        if user_id is not None:
            authenticated = True

    # Path 2: Legacy env-var password (fallback)
    if not authenticated:
        admin_pw = os.getenv("ADMIN_PASSWORD", "")
        if password and admin_pw and hmac.compare_digest(password, admin_pw):
            authenticated = True

    if authenticated:
        request.set_session({"admin_authenticated": True})
        return Redirect(path="/admin")

    return Template(
        template_name="admin/login.html",
        context={"error": "Invalid credentials."},
    )


@post("/logout")
async def logout(request: HTMXRequest) -> Redirect:
    request.clear_session()
    return Redirect(path="/admin/login")

# ── OAuth ──────────────────────────────────────────────────

@get("/oauth/authorize")
async def oauth_authorize(request: HTMXRequest) -> Redirect:
    """Redirect to Pocket ID with PKCE challenge."""
    url, state, code_verifier = await get_authorization_url()
    request.set_session({
        "oauth_state": state,
        "oauth_code_verifier": code_verifier,
    })
    return Redirect(path=url)


@get("/oauth/callback")
async def oauth_callback(request: HTMXRequest, code: str) -> Redirect:
    """Handle the OAuth callback, exchange code, validate group, set session."""
    oauth_state = request.query_params.get("state", "")
    session_state = request.session.get("oauth_state")
    code_verifier = request.session.get("oauth_code_verifier")

    if not session_state or oauth_state != session_state:
        _log.warning("OAuth state mismatch")
        return Redirect(path="/admin/login?error=OAuth+state+mismatch.+Please+try+again.")

    if not code_verifier:
        return Redirect(path="/admin/login?error=Missing+code+verifier.+Please+try+again.")

    try:
        userinfo = await exchange_code(code, oauth_state, code_verifier)
    except Exception:
        _log.exception("OAuth token exchange failed")
        return Redirect(path="/admin/login?error=OAuth+login+failed.+Please+try+again.")

    if not check_group_membership(userinfo):
        _log.warning("User %s not in required group", userinfo.get("sub", "?"))
        return Redirect(path="/admin/login?error=You+are+not+authorized.")

    request.set_session({"admin_authenticated": True})
    return Redirect(path="/admin")


# ── Dashboard ──────────────────────────────────────────────

@get("/")
async def dashboard() -> Template:
    page_count = len(await Page.select(Page.id).output(as_list=True))
    block_count = len(await ContentBlock.select(ContentBlock.id).output(as_list=True))
    return Template(
        template_name="admin/dashboard.html",
        context={
            "page_count": page_count,
            "block_count": block_count,
        },
    )


# ── Pages ──────────────────────────────────────────────────

@get("/pages")
async def pages_list() -> Template:
    rows = await (
        Page.select(
            Page.id, Page.title, Page.slug, Page.published,
            Page.is_homepage, Page.nav_order,
        )
        .order_by(Page.nav_order)
    )
    return Template(template_name="admin/pages.html", context={"pages": rows})


@get("/pages/new")
async def pages_new() -> Template:
    return Template(template_name="admin/page_edit.html", context={"page": None})


@post("/pages")
async def pages_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    body_md = (data.get("body_md") or "").strip()
    meta_description = (data.get("meta_description") or "").strip() or None
    is_homepage = data.get("is_homepage") == "on"
    show_in_nav = data.get("show_in_nav") == "on"
    nav_order = int(data.get("nav_order") or 0)
    published = data.get("published") == "on"

    if is_homepage:
        await Page.update({Page.is_homepage: False}).where(Page.is_homepage.eq(True))

    await Page(
        title=title,
        slug=slug,
        body_md=body_md,
        meta_description=meta_description,
        is_homepage=is_homepage,
        show_in_nav=show_in_nav,
        nav_order=nav_order,
        published=published,
    ).save()
    return Redirect(path="/admin/pages")


@get("/pages/{page_id:int}/edit")
async def pages_edit(page_id: int) -> Template:
    row = await Page.select().where(Page.id == page_id).first().output(as_dict=True)
    if not row:
        raise NotFoundException()
    return Template(template_name="admin/page_edit.html", context={"page": row})


@post("/pages/{page_id:int}/edit")
async def pages_update(
    page_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await Page.select(Page.id).where(Page.id == page_id).first().output(as_dict=True)
    if not existing:
        raise NotFoundException()

    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    body_md = (data.get("body_md") or "").strip()
    meta_description = (data.get("meta_description") or "").strip() or None
    is_homepage = data.get("is_homepage") == "on"
    show_in_nav = data.get("show_in_nav") == "on"
    nav_order = int(data.get("nav_order") or 0)
    published = data.get("published") == "on"

    if is_homepage:
        await Page.update({Page.is_homepage: False}).where(
            Page.is_homepage.eq(True)
        ).where(Page.id != page_id)

    await Page.update(
        {
            Page.title: title,
            Page.slug: slug,
            Page.body_md: body_md,
            Page.meta_description: meta_description,
            Page.is_homepage: is_homepage,
            Page.show_in_nav: show_in_nav,
            Page.nav_order: nav_order,
            Page.published: published,
            Page.updated_at: datetime.now(timezone.utc),
        }
    ).where(Page.id == page_id)
    return Redirect(path="/admin/pages")


@post("/pages/{page_id:int}/delete")
async def pages_delete(page_id: int, request: HTMXRequest) -> Response | Redirect:
    await Page.delete().where(Page.id == page_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/pages")


# ── Content Blocks ─────────────────────────────────────────

@get("/content")
async def content_list() -> Template:
    rows = await (
        ContentBlock.select()
        .order_by(ContentBlock.key)
        .output(as_dict=True)
    )
    return Template(template_name="admin/content.html", context={"blocks": rows})


@post("/content")
async def content_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    key = (data.get("key") or "").strip()
    label = (data.get("label") or "").strip()
    block_type = (data.get("block_type") or "text").strip()
    value = (data.get("value") or "").strip()
    await ContentBlock(key=key, label=label, block_type=block_type, value=value).save()
    return Redirect(path="/admin/content")


@post("/content/{block_id:int}")
async def content_update(
    block_id: int,
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Response | Redirect:
    existing = await ContentBlock.select(ContentBlock.id).where(
        ContentBlock.id == block_id
    ).first().output(as_dict=True)
    if not existing:
        raise NotFoundException()

    value = (data.get("value") or "").strip()
    await ContentBlock.update(
        {ContentBlock.value: value, ContentBlock.updated_at: datetime.now(timezone.utc)}
    ).where(ContentBlock.id == block_id)

    if request.htmx:
        return Response(
            content='<span class="meta"><ins>Saved ✓</ins></span>',
            status_code=200,
            media_type="text/html",
        )
    return Redirect(path="/admin/content")


@post("/content/{block_id:int}/delete")
async def content_delete(block_id: int, request: HTMXRequest) -> Response | Redirect:
    await ContentBlock.delete().where(ContentBlock.id == block_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/content")


# ── Guarded and unguarded handlers ─────────────────────────

_password_login_router = Router(
    path="/",
    route_handlers=[login_submit],
    middleware=[RateLimitConfig(rate_limit=("minute", 5)).middleware],
)

_public_handlers = [login_page, logout, _password_login_router, oauth_authorize, oauth_callback]
_guarded_handlers = [
    dashboard,
    pages_list, pages_new, pages_create, pages_edit, pages_update, pages_delete,
    content_list, content_create, content_update, content_delete,
]

_guarded_router = Router(
    path="/", route_handlers=_guarded_handlers, guards=[admin_guard],
)
admin_router = Router(
    path="/admin", route_handlers=[*_public_handlers, _guarded_router],
)
