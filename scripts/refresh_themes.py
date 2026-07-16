"""Refresh the seeded themes in the DB from the current connection.py constants.

The themes are seeded once on first boot. When the templates change,
existing installs keep the old template. This script upserts the
on-disk theme definitions in the DB — updating existing rows and
inserting missing ones (inactive) — without changing which is active.

Usage:
    PYTHONPATH=. uv run python scripts/refresh_themes.py                  # all
    PYTHONPATH=. uv run python scripts/refresh_themes.py --slug sprig     # only sprig
    PYTHONPATH=. uv run python scripts/refresh_themes.py --slug nightshade  # only nightshade

The current active theme is preserved. An inserted theme is created
inactive. The script never touches ``ContentBlock`` rows.
"""
from __future__ import annotations

import argparse
import asyncio

from db.connection import (
    _MYCELIUM_CSS,
    _MYCELIUM_CSS_FRAMEWORK,
    _MYCELIUM_SITE_HEAD,
    _MYCELIUM_TEMPLATE,
    _NIGHTSHADE_CSS,
    _NIGHTSHADE_CSS_FRAMEWORK,
    _NIGHTSHADE_SITE_HEAD,
    _NIGHTSHADE_TEMPLATE,
    _SPRIG_CSS,
    _SPRIG_CSS_FRAMEWORK,
    _SPRIG_SITE_HEAD,
    _SPRIG_TEMPLATE,
)
from db.tables import Theme
from piccolo_conf import DB


# slug → dict of column → value
_DEFS = {
    "mycelium": {
        "name": "Mycelium", "base_template": _MYCELIUM_TEMPLATE, "css": _MYCELIUM_CSS,
        "css_framework": _MYCELIUM_CSS_FRAMEWORK, "site_head": _MYCELIUM_SITE_HEAD,
    },
    "sprig": {
        "name": "Sprig", "base_template": _SPRIG_TEMPLATE, "css": _SPRIG_CSS,
        "css_framework": _SPRIG_CSS_FRAMEWORK, "site_head": _SPRIG_SITE_HEAD,
    },
    "nightshade": {
        "name": "Nightshade", "base_template": _NIGHTSHADE_TEMPLATE, "css": _NIGHTSHADE_CSS,
        "css_framework": _NIGHTSHADE_CSS_FRAMEWORK, "site_head": _NIGHTSHADE_SITE_HEAD,
    },
}


async def refresh(slug: str) -> str:
    """Upsert a theme's definition. Never changes ``active`` — an
    inserted theme is created inactive; an existing theme keeps its
    current active flag."""
    d = _DEFS.get(slug)
    if not d:
        raise SystemExit(f"Unknown slug: {slug!r}. Choose from {list(_DEFS)}.")
    existing = await Theme.select(Theme.id).where(Theme.slug == slug).first()
    if existing:
        await Theme.update(
            {
                Theme.base_template: d["base_template"],
                Theme.css: d["css"],
                Theme.css_framework: d["css_framework"],
                Theme.site_head: d["site_head"],
            }
        ).where(Theme.slug == slug)
        return "updated"
    await Theme(slug=slug, active=False, **d).save()
    return "inserted (inactive)"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        choices=list(_DEFS.keys()) + ["all"],
        default="all",
        help="Which theme to refresh (default: all).",
    )
    args = parser.parse_args()

    targets = list(_DEFS.keys()) if args.slug == "all" else [args.slug]

    await DB.start_connection_pool()
    try:
        for slug in targets:
            result = await refresh(slug)
            print(f"{slug}: {result}")
        # Final state
        rows = await Theme.select(Theme.id, Theme.slug, Theme.name, Theme.active)
        for r in rows:
            active = "active" if r["active"] else "inactive"
            print(f"  id={r['id']} slug={r['slug']} name={r['name']!r} {active}")
    finally:
        await DB.close_connection_pool()


if __name__ == "__main__":
    asyncio.run(main())