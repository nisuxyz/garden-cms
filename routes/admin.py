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

from db.tables import Collection, CollectionItem, CollectionItemSlugHistory, ContentBlock, MediaFile, Page, Theme
from cms.media import MediaError, delete_media, save_upload
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
        context={
            "error": error,
            "oauth_enabled": oauth_configured(),
            "oauth_provider_name": os.environ.get("OAUTH_PROVIDER_NAME", "oauth"),
        },
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
    collection_count = len(await Collection.select(Collection.id).output(as_list=True))
    return Template(
        template_name="admin/dashboard.html",
        context={
            "page_count": page_count,
            "block_count": block_count,
            "collection_count": collection_count,
        },
    )


# ── Pages ──────────────────────────────────────────────────

@get("/pages")
async def pages_list() -> Template:
    rows = await (
        Page.select(
            Page.id, Page.title, Page.slug, Page.published,
            Page.is_homepage, Page.nav_order, Page.show_in_nav,
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
    published = data.get("published") == "on"

    # Auto-assign nav_order to end of list.
    max_row = await Page.raw("SELECT COALESCE(MAX(nav_order), -1) AS mx FROM page")
    nav_order = (max_row[0]["mx"] if max_row else 0) + 1

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
    row = await Page.select().where(Page.id == page_id).first()
    if not row:
        raise NotFoundException()
    return Template(template_name="admin/page_edit.html", context={"page": row})


@post("/pages/{page_id:int}/edit")
async def pages_update(
    page_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await Page.select(Page.id).where(Page.id == page_id).first()
    if not existing:
        raise NotFoundException()

    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    body_md = (data.get("body_md") or "").strip()
    meta_description = (data.get("meta_description") or "").strip() or None
    is_homepage = data.get("is_homepage") == "on"
    show_in_nav = data.get("show_in_nav") == "on"
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


@post("/pages/{page_id:int}/reorder")
async def pages_reorder(
    page_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    direction = (data.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return Redirect(path="/admin/pages")

    rows = await (
        Page.select(Page.id, Page.nav_order)
        .order_by(Page.nav_order)
    )
    idx = next((i for i, r in enumerate(rows) if r["id"] == page_id), None)
    if idx is None:
        return Redirect(path="/admin/pages")

    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(rows):
        return Redirect(path="/admin/pages")

    a, b = rows[idx], rows[swap_idx]
    await Page.update({Page.nav_order: b["nav_order"]}).where(Page.id == a["id"])
    await Page.update({Page.nav_order: a["nav_order"]}).where(Page.id == b["id"])
    return Redirect(path="/admin/pages")


# ── Content Blocks ─────────────────────────────────────────

@get("/content")
async def content_list() -> Template:
    rows = await (
        ContentBlock.select()
        .order_by(ContentBlock.key)
        
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
    ).first()
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


# ── Collections ────────────────────────────────────────────

@get("/collections")
async def collections_list() -> Template:
    rows = await (
        Collection.select(Collection.id, Collection.name, Collection.slug)
        .order_by(Collection.name)
        
    )
    # Add item counts.
    for row in rows:
        count = await (
            CollectionItem.count()
            .where(CollectionItem.collection == row["id"])
        )
        row["item_count"] = count
    return Template(template_name="admin/collections.html", context={"collections": rows})


@get("/collections/new")
async def collections_new() -> Template:
    return Template(template_name="admin/collection_edit.html", context={"collection": None})


@post("/collections")
async def collections_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip()
    description = (data.get("description") or "").strip() or None
    fields_schema_raw = (data.get("fields_schema") or "[]").strip()
    card_template = (data.get("card_template") or "").strip()
    detail_template = (data.get("detail_template") or "").strip()
    empty_template = (data.get("empty_template") or "").strip()
    items_per_page = int(data.get("items_per_page") or 10)

    try:
        fields_schema = json.loads(fields_schema_raw)
    except json.JSONDecodeError:
        fields_schema = []

    await Collection(
        name=name,
        slug=slug,
        description=description,
        fields_schema=fields_schema,
        card_template=card_template,
        detail_template=detail_template,
        empty_template=empty_template,
        items_per_page=items_per_page,
    ).save()
    return Redirect(path="/admin/collections")


@get("/collections/{col_id:int}/edit")
async def collections_edit(col_id: int) -> Template:
    row = await Collection.select().where(Collection.id == col_id).first()
    if not row:
        raise NotFoundException()
    return Template(template_name="admin/collection_edit.html", context={"collection": row})


@post("/collections/{col_id:int}/edit")
async def collections_update(
    col_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await Collection.select(Collection.id).where(Collection.id == col_id).first()
    if not existing:
        raise NotFoundException()

    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip()
    description = (data.get("description") or "").strip() or None
    fields_schema_raw = (data.get("fields_schema") or "[]").strip()
    card_template = (data.get("card_template") or "").strip()
    detail_template = (data.get("detail_template") or "").strip()
    empty_template = (data.get("empty_template") or "").strip()
    items_per_page = int(data.get("items_per_page") or 10)

    try:
        fields_schema = json.loads(fields_schema_raw)
    except json.JSONDecodeError:
        fields_schema = []

    await Collection.update(
        {
            Collection.name: name,
            Collection.slug: slug,
            Collection.description: description,
            Collection.fields_schema: fields_schema,
            Collection.card_template: card_template,
            Collection.detail_template: detail_template,
            Collection.empty_template: empty_template,
            Collection.items_per_page: items_per_page,
            Collection.updated_at: datetime.now(timezone.utc),
        }
    ).where(Collection.id == col_id)
    return Redirect(path="/admin/collections")


@post("/collections/{col_id:int}/delete")
async def collections_delete(col_id: int, request: HTMXRequest) -> Response | Redirect:
    # Delete all items + slug history first.
    item_ids = await (
        CollectionItem.select(CollectionItem.id)
        .where(CollectionItem.collection == col_id)
        .output(as_list=True)
    )
    if item_ids:
        await CollectionItemSlugHistory.delete().where(
            CollectionItemSlugHistory.item.is_in(item_ids)
        )
    await CollectionItem.delete().where(CollectionItem.collection == col_id)
    await Collection.delete().where(Collection.id == col_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/collections")


# ── Collection Items ───────────────────────────────────────

@get("/collections/{col_id:int}/items")
async def items_list(col_id: int) -> Template:
    col = await Collection.select().where(Collection.id == col_id).first()
    if not col:
        raise NotFoundException()
    rows = await (
        CollectionItem.select()
        .where(CollectionItem.collection == col_id)
        .order_by(CollectionItem.created_at, ascending=False)
        
    )
    return Template(
        template_name="admin/items.html",
        context={"collection": col, "items": rows},
    )


@get("/collections/{col_id:int}/items/new")
async def items_new(col_id: int) -> Template:
    col = await Collection.select().where(Collection.id == col_id).first()
    if not col:
        raise NotFoundException()
    return Template(
        template_name="admin/item_edit.html",
        context={"collection": col, "item": None},
    )


@post("/collections/{col_id:int}/items")
async def items_create(
    col_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    col = await Collection.select().where(Collection.id == col_id).first()
    if not col:
        raise NotFoundException()

    title = (data.get("title") or "").strip()
    slug = (data.get("slug") or "").strip()
    published = data.get("published") == "on"
    featured = data.get("featured") == "on"
    sort_order = int(data.get("sort_order") or 0)

    # Build data dict from fields_schema.
    item_data = {}
    for field_def in col.get("fields_schema", []):
        fname = field_def["name"]
        item_data[fname] = (data.get(f"field_{fname}") or "").strip()

    await CollectionItem(
        collection=col_id,
        title=title,
        slug=slug,
        data=item_data,
        published=published,
        featured=featured,
        sort_order=sort_order,
    ).save()
    return Redirect(path=f"/admin/collections/{col_id}/items")


@get("/collections/{col_id:int}/items/{item_id:int}/edit")
async def items_edit(col_id: int, item_id: int) -> Template:
    col = await Collection.select().where(Collection.id == col_id).first()
    if not col:
        raise NotFoundException()
    item = await (
        CollectionItem.select()
        .where(CollectionItem.id == item_id)
        .where(CollectionItem.collection == col_id)
        .first()
        
    )
    if not item:
        raise NotFoundException()
    return Template(
        template_name="admin/item_edit.html",
        context={"collection": col, "item": item},
    )


@post("/collections/{col_id:int}/items/{item_id:int}/edit")
async def items_update(
    col_id: int,
    item_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    col = await Collection.select().where(Collection.id == col_id).first()
    if not col:
        raise NotFoundException()
    existing = await (
        CollectionItem.select(CollectionItem.slug)
        .where(CollectionItem.id == item_id)
        .first()
        
    )
    if not existing:
        raise NotFoundException()

    title = (data.get("title") or "").strip()
    new_slug = (data.get("slug") or "").strip()
    published = data.get("published") == "on"
    featured = data.get("featured") == "on"
    sort_order = int(data.get("sort_order") or 0)

    item_data = {}
    for field_def in col.get("fields_schema", []):
        fname = field_def["name"]
        item_data[fname] = (data.get(f"field_{fname}") or "").strip()

    # Track slug change for 301 redirects.
    old_slug = existing["slug"]
    if new_slug != old_slug:
        await CollectionItemSlugHistory(
            item=item_id,
            collection_slug=col["slug"],
            old_slug=old_slug,
        ).save()

    await CollectionItem.update(
        {
            CollectionItem.title: title,
            CollectionItem.slug: new_slug,
            CollectionItem.data: item_data,
            CollectionItem.published: published,
            CollectionItem.featured: featured,
            CollectionItem.sort_order: sort_order,
            CollectionItem.updated_at: datetime.now(timezone.utc),
        }
    ).where(CollectionItem.id == item_id)
    return Redirect(path=f"/admin/collections/{col_id}/items")


@post("/collections/{col_id:int}/items/{item_id:int}/delete")
async def items_delete(
    col_id: int, item_id: int, request: HTMXRequest,
) -> Response | Redirect:
    await CollectionItemSlugHistory.delete().where(
        CollectionItemSlugHistory.item == item_id
    )
    await CollectionItem.delete().where(CollectionItem.id == item_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path=f"/admin/collections/{col_id}/items")


# ── Media ──────────────────────────────────────────────────

@get("/media")
async def media_list() -> Template:
    rows = await (
        MediaFile.select()
        .order_by(MediaFile.created_at, ascending=False)
        
    )
    return Template(template_name="admin/media.html", context={"files": rows})


@post("/media/upload")
async def media_upload(
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.MULTI_PART)],
) -> Response | Redirect:
    upload = data.get("file")
    alt_text = (data.get("alt_text") or "").strip() or None

    if upload is None:
        if request.htmx:
            return Response(content="<mark>No file provided</mark>", status_code=422, media_type="text/html")
        return Redirect(path="/admin/media")

    try:
        file_data = upload.read() if hasattr(upload, "read") else upload
        original_name = getattr(upload, "filename", "upload")
        content_type = getattr(upload, "content_type", "application/octet-stream")

        await save_upload(
            file_data=file_data,
            original_name=original_name,
            content_type=content_type,
            alt_text=alt_text,
        )
    except MediaError as e:
        if request.htmx:
            return Response(content=f"<mark>{e}</mark>", status_code=422, media_type="text/html")
        return Redirect(path="/admin/media")

    return Redirect(path="/admin/media")


@post("/media/{media_id:int}/delete")
async def media_delete(media_id: int, request: HTMXRequest) -> Response | Redirect:
    await delete_media(media_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/media")


# ── Themes ─────────────────────────────────────────────────

@get("/themes")
async def themes_list() -> Template:
    rows = await Theme.select().order_by(Theme.name)
    return Template(template_name="admin/themes.html", context={"themes": rows})


@get("/themes/new")
async def themes_new() -> Template:
    return Template(template_name="admin/theme_edit.html", context={"theme": None})


@post("/themes")
async def themes_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip()
    base_template = (data.get("base_template") or "").strip()
    css = (data.get("css") or "").strip()
    active = data.get("active") == "on"

    if active:
        await Theme.update({Theme.active: False}).where(Theme.active.eq(True))

    await Theme(
        name=name, slug=slug, base_template=base_template, css=css, active=active,
    ).save()
    return Redirect(path="/admin/themes")


@get("/themes/{theme_id:int}/edit")
async def themes_edit(theme_id: int) -> Template:
    row = await Theme.select().where(Theme.id == theme_id).first()
    if not row:
        raise NotFoundException()
    return Template(template_name="admin/theme_edit.html", context={"theme": row})


@post("/themes/{theme_id:int}/edit")
async def themes_update(
    theme_id: int,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    existing = await Theme.select(Theme.id).where(Theme.id == theme_id).first()
    if not existing:
        raise NotFoundException()

    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip()
    base_template = (data.get("base_template") or "").strip()
    css = (data.get("css") or "").strip()
    active = data.get("active") == "on"

    if active:
        await Theme.update({Theme.active: False}).where(
            Theme.active.eq(True)
        ).where(Theme.id != theme_id)

    await Theme.update(
        {
            Theme.name: name,
            Theme.slug: slug,
            Theme.base_template: base_template,
            Theme.css: css,
            Theme.active: active,
            Theme.updated_at: datetime.now(timezone.utc),
        }
    ).where(Theme.id == theme_id)
    return Redirect(path="/admin/themes")


@post("/themes/{theme_id:int}/activate")
async def themes_activate(theme_id: int) -> Redirect:
    await Theme.update({Theme.active: False}).where(Theme.active.eq(True))
    await Theme.update({Theme.active: True}).where(Theme.id == theme_id)
    return Redirect(path="/admin/themes")


@post("/themes/{theme_id:int}/delete")
async def themes_delete(theme_id: int, request: HTMXRequest) -> Response | Redirect:
    row = await Theme.select(Theme.active).where(Theme.id == theme_id).first()
    if row and row.get("active"):
        if request.htmx:
            return Response(
                content="<mark>Cannot delete the active theme</mark>",
                status_code=422,
                media_type="text/html",
            )
        return Redirect(path="/admin/themes")

    await Theme.delete().where(Theme.id == theme_id)
    if request.htmx:
        return Response(content="", status_code=200)
    return Redirect(path="/admin/themes")


# ── Guarded and unguarded handlers ─────────────────────────

_password_login_router = Router(
    path="/",
    route_handlers=[login_submit],
    middleware=[RateLimitConfig(rate_limit=("minute", 5)).middleware],
)

_public_handlers = [login_page, logout, _password_login_router, oauth_authorize, oauth_callback]
_guarded_handlers = [
    dashboard,
    pages_list, pages_new, pages_create, pages_edit, pages_update, pages_delete, pages_reorder,
    content_list, content_create, content_update, content_delete,
    collections_list, collections_new, collections_create, collections_edit,
    collections_update, collections_delete,
    items_list, items_new, items_create, items_edit, items_update, items_delete,
    media_list, media_upload, media_delete,
    themes_list, themes_new, themes_create, themes_edit, themes_update,
    themes_activate, themes_delete,
]

_guarded_router = Router(
    path="/", route_handlers=_guarded_handlers, guards=[admin_guard],
)
admin_router = Router(
    path="/admin", route_handlers=[*_public_handlers, _guarded_router],
)
