# cms/markdown.py
"""
Markdown directory discovery and file-based routing.

Subdirectories of ``data/md/`` can be mounted as URL prefixes.
Each ``.md`` file becomes a routable page; directory structure maps
directly to URL paths.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import markdown as md

from db.tables import SiteSettings

_MD_ROOT = Path("data/md")

_md_converter = md.Markdown(extensions=["fenced_code", "tables", "toc"])

_HEADING_RE = re.compile(r"^#\s+(.+)", re.MULTILINE)


def discover_md_dirs() -> list[str]:
    """Return sorted names of immediate subdirectories under ``data/md/``."""
    if not _MD_ROOT.is_dir():
        return []
    return sorted(
        d.name for d in _MD_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def list_md_routes(mount_dir: str) -> list[str]:
    """Recursively list all ``.md`` file paths as route suffixes.

    For a file at ``data/md/docs/styling/css.md`` with *mount_dir* ``"docs"``,
    returns ``"styling/css"``.
    """
    root = (_MD_ROOT / mount_dir).resolve()
    if not root.is_dir() or not str(root).startswith(str(_MD_ROOT.resolve())):
        return []
    routes: list[str] = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).with_suffix("")
        routes.append(str(rel).replace("\\", "/"))
    return routes


def resolve_md_file(mount_dir: str, sub_path: str) -> tuple[str, str, str | None] | None:
    """Read a markdown file and convert it to HTML.

    Returns ``(title, html, layout_source)`` or ``None`` if the file doesn't
    exist.  *layout_source* is the contents of the nearest ``_layout.jinja``
    file (walking from the file's directory up to the mount root), or ``None``.
    *sub_path* must not contain ``..`` or start with ``/``.
    """
    # Path-traversal protection.
    if ".." in sub_path or sub_path.startswith("/"):
        return None

    target = (_MD_ROOT / mount_dir / f"{sub_path}.md").resolve()
    safe_root = (_MD_ROOT / mount_dir).resolve()
    if not str(target).startswith(str(safe_root)):
        return None
    if not target.is_file():
        return None

    source = target.read_text(encoding="utf-8")

    # Extract title from first heading.
    m = _HEADING_RE.search(source)
    title = m.group(1).strip() if m else target.stem.replace("-", " ").title()

    _md_converter.reset()
    html = _md_converter.convert(source)

    # Find nearest _layout.jinja walking up to the mount root.
    layout_source = _find_layout(target.parent, safe_root)

    return title, html, layout_source


def _find_layout(start: Path, root: Path) -> str | None:
    """Walk from *start* up to *root* looking for ``_layout.jinja``.

    Returns the file contents of the nearest layout, or ``None``.
    """
    current = start
    while True:
        candidate = current / "_layout.jinja"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        if current == root:
            break
        current = current.parent
    return None


async def load_md_mounts() -> dict[str, str]:
    """Load the ``md_mounts`` mapping from SiteSettings.

    Returns ``{dir_name: slug_prefix, ...}``.
    """
    row = await (
        SiteSettings.select(SiteSettings.value)
        .where(SiteSettings.key == "md_mounts")
        .first()
    )
    raw = (row.get("value", "") or "") if row else ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


async def save_md_mounts(mounts: dict[str, str]) -> None:
    """Persist the ``md_mounts`` mapping to SiteSettings."""
    val = json.dumps(mounts)
    existing = await (
        SiteSettings.select()
        .where(SiteSettings.key == "md_mounts")
        .first()
    )
    if existing:
        await (
            SiteSettings.update({SiteSettings.value: val})
            .where(SiteSettings.key == "md_mounts")
        )
    else:
        await SiteSettings(key="md_mounts", value=val).save()
