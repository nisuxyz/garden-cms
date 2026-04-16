#!/usr/bin/env python3
"""Generate db/connection.py seed constant assignments from DB snapshot JSON.

Typical flow:
1) uv run python scripts/export_db_views.py --pretty --out scripts/snapshots/db_views_snapshot.after.json
2) uv run python scripts/generate_seed_constants.py --snapshot scripts/snapshots/db_views_snapshot.after.json --out /tmp/seed_constants.py
3) Copy generated constants into db/connection.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _quote_multiline(name: str, value: str) -> str:
    escaped = value.replace('"""', '\\"\\"\\"')
    return f'{name} = """\\\n{escaped}\\n"""\n'


def _quote_list(name: str, rows: list[tuple[str, str, str, str]]) -> str:
    lines = [f"{name} = ["]
    for key, label, block_type, value in rows:
        dumped = json.dumps(value, ensure_ascii=False)
        lines.append(f'    ({json.dumps(key)}, {json.dumps(label)}, {json.dumps(block_type)}, {dumped}),')
    lines.append("]\n")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate seed constants from snapshot.")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def _first_by_slug(rows: list[dict], slug: str) -> dict | None:
    for row in rows:
        if row.get("slug") == slug:
            return row
    return None


def _page_body(rows: list[dict], slug: str) -> str:
    row = _first_by_slug(rows, slug)
    return row.get("body", "") if row else ""


def _collection_tpl(rows: list[dict], slug: str, field: str) -> str:
    row = _first_by_slug(rows, slug)
    return row.get(field, "") if row else ""


def main() -> int:
    args = _build_parser().parse_args()
    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))

    pages = payload.get("pages", [])
    collections = payload.get("collections", [])
    blocks = payload.get("content_blocks", [])
    active_theme = payload.get("active_theme") or {}

    block_rows: list[tuple[str, str, str, str]] = []
    for row in blocks:
        block_rows.append(
            (
                str(row.get("key", "")),
                str(row.get("label", "")),
                str(row.get("block_type", "text")),
                str(row.get("value", "")),
            )
        )

    output_parts = [
        "# Generated from DB snapshot. Paste into db/connection.py constants section.\n",
        _quote_multiline("_DEFAULT_THEME_TEMPLATE", str(active_theme.get("base_template", ""))),
        _quote_multiline("_DEFAULT_THEME_CSS", str(active_theme.get("css", ""))),
        _quote_list("_DEFAULT_CONTENT_BLOCKS", block_rows),
        _quote_multiline("_BLOG_CARD_TEMPLATE", _collection_tpl(collections, "blog", "card_template")),
        _quote_multiline("_BLOG_DETAIL_TEMPLATE", _collection_tpl(collections, "blog", "detail_template")),
        _quote_multiline("_PROJECT_CARD_TEMPLATE", _collection_tpl(collections, "projects", "card_template")),
        _quote_multiline("_PROJECT_DETAIL_TEMPLATE", _collection_tpl(collections, "projects", "detail_template")),
        _quote_multiline("_HOME_PAGE", _page_body(pages, "home")),
        _quote_multiline("_BLOG_PAGE", _page_body(pages, "blog")),
        _quote_multiline("_PROJECTS_PAGE", _page_body(pages, "projects")),
        _quote_multiline("_RESUME_PAGE", _page_body(pages, "resume")),
        _quote_multiline("_CONTACT_PAGE", _page_body(pages, "contact")),
    ]

    output = "\n".join(output_parts)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
