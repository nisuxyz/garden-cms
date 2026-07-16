"""One-shot data migration for the head-architecture split.

Brings an existing install's live data in line with the new model:

1. Removes the orphan site-level ``css_framework`` setting — the base
   classless framework now lives on each Theme (``Theme.css_framework``).
2. Strips the UnoCSS runtime <script> out of the *site-level* ``site_head``
   setting — that engine now lives in the Sprig theme's own Site Head
   (populated by scripts/refresh_themes.py). Any other site_head content
   is preserved.
3. Ensures a generic ``error`` Page exists and ``status_page`` points at it.

Idempotent — safe to run more than once. Never touches ContentBlock rows
and never changes which theme is active.

Run:
    PYTHONPATH=. uv run python scripts/migrate_head_settings.py
"""
from __future__ import annotations

import asyncio

from db.connection import _ERROR_PAGE
from db.tables import Page, SiteSettings
from piccolo_conf import DB

_UNOCSS_NEEDLE = "@unocss/runtime/uno.global.js"


async def _get(key: str) -> str | None:
    row = await SiteSettings.select(SiteSettings.value).where(
        SiteSettings.key == key
    ).first()
    return (row.get("value") if row else None)


async def _set(key: str, value: str) -> None:
    existing = await SiteSettings.select(SiteSettings.id).where(
        SiteSettings.key == key
    ).first()
    if existing:
        await SiteSettings.update({SiteSettings.value: value}).where(
            SiteSettings.key == key
        )
    else:
        await SiteSettings(key=key, value=value).save()


async def main() -> None:
    await DB.start_connection_pool()
    try:
        # 1. The base CSS framework now lives on each Theme (Theme.css_framework),
        #    not the site settings. Drop the orphan site-level row if present.
        from db.tables import SiteSettings as _SS
        deleted = await _SS.delete().where(_SS.key == "css_framework")
        print(f"css_framework: removed site-level setting (rows={len(deleted)})")

        # 2. Strip UnoCSS <script> lines out of the site-level site_head
        site_head = await _get("site_head") or ""
        if _UNOCSS_NEEDLE in site_head:
            kept = "\n".join(
                line for line in site_head.splitlines()
                if _UNOCSS_NEEDLE not in line
            ).strip()
            await _set("site_head", kept)
            print(f"site_head: removed UnoCSS line (now {len(kept)} chars)")
        else:
            print("site_head: no UnoCSS line found (left as-is)")

        # 3. Ensure an 'error' page + status_page setting
        err = await Page.select(Page.id).where(Page.slug == "error").first()
        if not err:
            await Page(
                title="Error",
                slug="error",
                body=_ERROR_PAGE,
                is_homepage=False,
                show_in_nav=False,
                nav_order=99,
                published=True,
            ).save()
            print("pages: created 'error' status page")
        else:
            print("pages: 'error' page already exists")

        status_page = await _get("status_page")
        if not status_page:
            await _set("status_page", "error")
            print("status_page: set to 'error'")
        else:
            print(f"status_page: already {status_page!r} (left as-is)")
    finally:
        await DB.close_connection_pool()


if __name__ == "__main__":
    asyncio.run(main())
