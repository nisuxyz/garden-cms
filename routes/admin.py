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
from litestar.plugins.htmx import ClientRedirect, HTMXRequest
from litestar.response import Redirect, Response, Template

from db.tables import Collection, CollectionItem, CollectionItemSlugHistory, ContentBlock, MediaFile, Page, SiteSettings, Theme
from cms.css_frameworks import CSS_FRAMEWORKS
from cms.media import MediaError, delete_media, save_upload
from cms.renderer import render, render_themed
from cms.site_context import invalidate_site_dict
from cms.storage import get_backend, load_backend
from middleware.auth import admin_guard


def _safe_json(raw: str | None, default=None):
    """Parse a JSON string, returning *default* on failure."""
    if default is None:
        default = []
    raw = (raw or "").strip() or None
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


async def _get_media_list() -> list[dict]:
    """Return the filename/original_name pairs used by media pickers."""
    return await (
        MediaFile.select(MediaFile.filename, MediaFile.original_name)
        .order_by(MediaFile.original_name)
    )


async def _render_preview_themed(
    content_html: str, title: str, *, css_override: str | None = None,
) -> str:
    """Wrap *content_html* in the active theme, or return it bare."""
    theme = await Theme.select().where(Theme.active.eq(True)).first()
    if not theme:
        return content_html
    from cms.engine import get_nav_items, _get_site_head
    nav = await get_nav_items()
    site_head = await _get_site_head()
    return await render_themed(
        base_template=theme["base_template"],
        css=css_override if css_override is not None else theme.get("css", ""),
        title=title,
        content_html=content_html,
        nav_items=nav,
        site_head=site_head,
    )
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
async def logout(request: HTMXRequest) -> Redirect | ClientRedirect:
    request.clear_session()
    if request.htmx:
        return ClientRedirect(redirect_to="/admin/login")
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
    body = (data.get("body") or "").strip()
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
        body=body,
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
    body = (data.get("body") or "").strip()
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
            Page.body: body,
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
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect | ClientRedirect:
    direction = (data.get("direction") or "").strip()
    if direction not in ("up", "down"):
        if request.htmx:
            return ClientRedirect(redirect_to="/admin/pages")
        return Redirect(path="/admin/pages")

    rows = await (
        Page.select(Page.id, Page.nav_order)
        .order_by(Page.nav_order)
    )
    idx = next((i for i, r in enumerate(rows) if r["id"] == page_id), None)
    if idx is None:
        if request.htmx:
            return ClientRedirect(redirect_to="/admin/pages")
        return Redirect(path="/admin/pages")

    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(rows):
        if request.htmx:
            return ClientRedirect(redirect_to="/admin/pages")
        return Redirect(path="/admin/pages")

    a, b = rows[idx], rows[swap_idx]
    await Page.update({Page.nav_order: b["nav_order"]}).where(Page.id == a["id"])
    await Page.update({Page.nav_order: a["nav_order"]}).where(Page.id == b["id"])
    if request.htmx:
        return ClientRedirect(redirect_to="/admin/pages")
    return Redirect(path="/admin/pages")


# ── Content Blocks ─────────────────────────────────────────

@get("/content")
async def content_list() -> Template:
    rows = await (
        ContentBlock.select()
        .order_by(ContentBlock.key)
        
    )
    media_files = await _get_media_list()
    return Template(template_name="admin/content.html", context={"blocks": rows, "media_files": media_files})


@post("/content")
async def content_create(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect:
    key = (data.get("key") or "").strip()
    label = (data.get("label") or "").strip()
    block_type = (data.get("block_type") or "text").strip()
    value = (data.get("value") or "").strip()
    await ContentBlock(key=key, label=label, block_type=block_type, value=value).save()
    await invalidate_site_dict()
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
    await invalidate_site_dict()

    if request.htmx:
        return Response(
            content=(
                f'<button type="submit" id="save-btn-{block_id}">Saved ✓</button>'
                f'<script>setTimeout(()=>{{let e=document.getElementById("save-btn-{block_id}");if(e)e.textContent="Save"}},2000)</script>'
            ),
            status_code=200,
            media_type="text/html",
        )
    return Redirect(path="/admin/content")


@post("/content/{block_id:int}/delete")
async def content_delete(block_id: int, request: HTMXRequest) -> Response | Redirect:
    await ContentBlock.delete().where(ContentBlock.id == block_id)
    await invalidate_site_dict()
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

    fields_schema = _safe_json(fields_schema_raw)

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

    fields_schema = _safe_json(fields_schema_raw)

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
        .order_by(CollectionItem.sort_order)
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
    if isinstance(col["fields_schema"], str):
        col["fields_schema"] = _safe_json(col["fields_schema"])
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
    fields_schema = col.get("fields_schema", [])
    if isinstance(fields_schema, str):
        fields_schema = _safe_json(fields_schema)
    item_data = {}
    for field_def in fields_schema:
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
    if isinstance(col["fields_schema"], str):
        col["fields_schema"] = _safe_json(col["fields_schema"])
    if isinstance(item.get("data"), str):
        item["data"] = _safe_json(item["data"], default={})
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

    fields_schema = col.get("fields_schema", [])
    if isinstance(fields_schema, str):
        fields_schema = _safe_json(fields_schema)
    item_data = {}
    for field_def in fields_schema:
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


@post("/collections/{col_id:int}/items/{item_id:int}/reorder")
async def items_reorder(
    col_id: int,
    item_id: int,
    request: HTMXRequest,
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Redirect | ClientRedirect:
    path = f"/admin/collections/{col_id}/items"
    direction = (data.get("direction") or "").strip()
    if direction not in ("up", "down"):
        if request.htmx:
            return ClientRedirect(redirect_to=path)
        return Redirect(path=path)

    rows = await (
        CollectionItem.select(CollectionItem.id, CollectionItem.sort_order)
        .where(CollectionItem.collection == col_id)
        .order_by(CollectionItem.sort_order)
    )
    idx = next((i for i, r in enumerate(rows) if r["id"] == item_id), None)
    if idx is None:
        if request.htmx:
            return ClientRedirect(redirect_to=path)
        return Redirect(path=path)

    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(rows):
        if request.htmx:
            return ClientRedirect(redirect_to=path)
        return Redirect(path=path)

    a, b = rows[idx], rows[swap_idx]
    await CollectionItem.update({CollectionItem.sort_order: b["sort_order"]}).where(CollectionItem.id == a["id"])
    await CollectionItem.update({CollectionItem.sort_order: a["sort_order"]}).where(CollectionItem.id == b["id"])
    if request.htmx:
        return ClientRedirect(redirect_to=path)
    return Redirect(path=path)


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


# ── Settings ───────────────────────────────────────────────

_SETTINGS_KEYS = [
    "storage_backend",
    "s3_bucket",
    "s3_region",
    "s3_endpoint_url",
    "s3_access_key_id",
    "s3_secret_access_key",
    "s3_prefix",
    "s3_public_url",
    "favicon",
    "site_head",
]


async def _get_settings_dict() -> dict[str, str]:
    rows = await SiteSettings.select(SiteSettings.key, SiteSettings.value)
    return {r["key"]: r.get("value", "") or "" for r in rows}


@get("/settings")
async def settings_page() -> Template:
    settings = await _get_settings_dict()
    media_files = await _get_media_list()
    return Template(
        template_name="admin/settings.html",
        context={"settings": settings, "saved": False, "error": None, "media_files": media_files, "css_frameworks": CSS_FRAMEWORKS},
    )


@post("/settings")
async def settings_save(
    data: Annotated[dict, Body(media_type=RequestEncodingType.URL_ENCODED)],
) -> Template:
    settings: dict[str, str] = {}
    for key in _SETTINGS_KEYS:
        val = (data.get(key) or "").strip()
        settings[key] = val

        existing = await (
            SiteSettings.select()
            .where(SiteSettings.key == key)
            .first()
        )
        if existing:
            await (
                SiteSettings.update({SiteSettings.value: val})
                .where(SiteSettings.key == key)
            )
        else:
            await SiteSettings(key=key, value=val).save()

    # Reload the storage backend with the new settings.
    error = None
    try:
        await load_backend()
    except Exception as e:
        error = f"Settings saved but backend failed to initialise: {e}"

    return Template(
        template_name="admin/settings.html",
        context={"settings": settings, "saved": error is None, "error": error, "css_frameworks": CSS_FRAMEWORKS, "media_files": await _get_media_list()},
    )


# ── Media ──────────────────────────────────────────────────

@get("/media")
async def media_list() -> Template:
    rows = await (
        MediaFile.select()
        .order_by(MediaFile.created_at, ascending=False)
        
    )
    backend = get_backend()
    return Template(template_name="admin/media.html", context={"files": rows, "media_url": backend.url})


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
        file_data = (await upload.read()) if hasattr(upload, "read") else upload
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
async def themes_activate(theme_id: int, request: HTMXRequest) -> Redirect | ClientRedirect:
    await Theme.update({Theme.active: False}).where(Theme.active.eq(True))
    await Theme.update({Theme.active: True}).where(Theme.id == theme_id)
    if request.htmx:
        return ClientRedirect(redirect_to="/admin/themes")
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


# ── Preview ────────────────────────────────────────────────

@post("/preview")
async def preview(
    data: Annotated[dict, Body(media_type=RequestEncodingType.MULTI_PART)],
) -> Response:
    """Render a template source string and return full themed HTML.

    Used by the CodeJar live-preview iframe in edit pages.
    """
    print("Received preview request with data:", data, data.keys())
    source = (data.get("source") or "").strip()
    preview_type = (data.get("type") or "page").strip()

    print(f"Preview request: type={preview_type}, source={source[:100]}...")

    try:
        _sample_item = {
            "title": "Sample Item",
            "slug": "sample-item",
            "summary": "This is a preview with sample data.",
            "body": "<p>Sample body content.</p>",
            "tags": "sample, preview",
            "created_at": "2026-01-01",
        }

        if preview_type == "page":
            content_html = await render(source)
            html = await _render_preview_themed(content_html, "Preview")

        elif preview_type == "card":
            content_html = await render(source, {"item": _sample_item})
            html = await _render_preview_themed(content_html, "Card Preview")

        elif preview_type == "detail":
            content_html = await render(source, {"item": _sample_item})
            html = await _render_preview_themed(content_html, "Preview")

        elif preview_type == "theme":
            html = await render_themed(
                base_template=source,
                css="",
                title="Theme Preview",
                content_html="<h1>Theme Preview</h1><p>This is sample content.</p>",
                nav_items=[{"title": "Home", "slug": "home", "url": "/"}],
            )

        elif preview_type == "css":
            theme = await Theme.select().where(Theme.active.eq(True)).first()
            if theme:
                html = await render_themed(
                    base_template=theme["base_template"],
                    css=source,
                    title="CSS Preview",
                    content_html="<h1>CSS Preview</h1><p>This is sample content.</p><article><h3>Sample Card</h3><p>Card content here.</p></article>",
                    nav_items=[{"title": "Home", "slug": "home", "url": "/"}],
                )
            else:
                html = f"<style>{source}</style><p>No active theme.</p>"

        else:
            html = await render(source)

    except Exception as exc:
        html = f"<pre style='color:red'>{exc!s}</pre>"

    return Response(content=html, media_type="text/html")


# ── Guarded and unguarded handlers ─────────────────────────


async def _no_cache(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


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
    items_list, items_new, items_create, items_edit, items_update, items_reorder, items_delete,
    media_list, media_upload, media_delete,
    settings_page, settings_save,
    themes_list, themes_new, themes_create, themes_edit, themes_update,
    themes_activate, themes_delete,
    preview,
]

_guarded_router = Router(
    path="/", route_handlers=_guarded_handlers, guards=[admin_guard],
)
admin_router = Router(
    path="/admin", route_handlers=[*_public_handlers, _guarded_router],
    after_request=_no_cache,
)
