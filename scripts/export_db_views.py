#!/usr/bin/env python3
"""Export DB-backed view templates/content for responsive audit and seed sync.

This script snapshots runtime-editable view surfaces:
- Theme (active theme template + CSS)
- Pages (slug/title/body)
- Collections (card/detail/empty templates)
- Content blocks (key/type/value)

Usage:
  uv run python scripts/export_db_views.py --pretty --out db_views_snapshot.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is importable when running this file directly.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.tables import Collection, ContentBlock, Page, Theme
from piccolo_conf import DB


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export DB-backed view content.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path for JSON snapshot.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


async def _snapshot() -> dict[str, Any]:
    active_theme = await (
        Theme.select(
            Theme.id,
            Theme.name,
            Theme.slug,
            Theme.active,
            Theme.base_template,
            Theme.css,
        )
        .where(Theme.active.eq(True))
        .first()
    )

    themes = await Theme.select(
        Theme.id,
        Theme.name,
        Theme.slug,
        Theme.active,
    )

    pages = await Page.select(
        Page.id,
        Page.title,
        Page.slug,
        Page.published,
        Page.show_in_nav,
        Page.nav_order,
        Page.body,
    ).order_by(Page.nav_order)

    collections = await Collection.select(
        Collection.id,
        Collection.name,
        Collection.slug,
        Collection.description,
        Collection.items_per_page,
        Collection.fields_schema,
        Collection.card_template,
        Collection.detail_template,
        Collection.empty_template,
    ).order_by(Collection.name)

    blocks = await ContentBlock.select(
        ContentBlock.id,
        ContentBlock.key,
        ContentBlock.label,
        ContentBlock.block_type,
        ContentBlock.value,
    ).order_by(ContentBlock.key)

    return {
        "summary": {
            "theme_count": len(themes),
            "page_count": len(pages),
            "collection_count": len(collections),
            "content_block_count": len(blocks),
            "active_theme_slug": active_theme.get("slug") if active_theme else None,
        },
        "active_theme": active_theme,
        "themes": themes,
        "pages": pages,
        "collections": collections,
        "content_blocks": blocks,
    }


async def _run(args: argparse.Namespace) -> int:
    await DB.start_connection_pool(max_inactive_connection_lifetime=1)
    try:
        payload = await _snapshot()
    finally:
        await DB.close_connection_pool()

    indent = 2 if args.pretty else None
    output = json.dumps(payload, indent=indent, ensure_ascii=False)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")

    print(output)
    return 0


def main() -> int:
    args = _build_parser().parse_args()

    import asyncio

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
