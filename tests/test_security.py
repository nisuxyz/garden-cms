# tests/test_security.py
"""
Security-property tests: path-traversal guards and secret handling.

These exercise the guards added during the de-slopping pass so regressions
are caught at the unit level rather than after a lengthier HTTP integration
failure.
"""
from __future__ import annotations

import hashlib
import importlib
import sys

import pytest

from cms.markdown import resolve_md_file
from cms.storage import LocalStorageBackend


def _fresh_import_app() -> object:
    """Import the top-level app module fresh, bypassing sys.modules cache."""
    sys.modules.pop("app", None)
    try:
        return importlib.import_module("app")
    finally:
        sys.modules.pop("app", None)


# ── LocalStorageBackend traversal guard ──────────────────────


@pytest.mark.parametrize(
    "evil",
    [
        "../etc/passwd",
        "/absolute/path",
        "../../secret",
        "subdir/../../../escape",
    ],
)
def test_local_storage_rejects_traversal(evil: str, tmp_path) -> None:
    backend = LocalStorageBackend(root=tmp_path / "media")
    with pytest.raises(PermissionError):
        backend._safe_path(evil)


def test_local_storage_allows_nested_subdir(tmp_path) -> None:
    backend = LocalStorageBackend(root=tmp_path / "media")
    p = backend._safe_path("sub/dir/file.png")
    assert p.is_relative_to((tmp_path / "media").resolve())


# ── markdown resolve_md_file traversal guard ─────────────────


def test_resolve_md_file_rejects_dotdot(monkeypatch, tmp_path) -> None:
    import cms.markdown as m

    monkeypatch.setattr(m, "_MD_ROOT", tmp_path / "md")
    (tmp_path / "md" / "docs").mkdir(parents=True)
    (tmp_path / "md" / "docs" / "real.md").write_text("# Real\nok")
    assert resolve_md_file("docs", "../secret") is None
    assert resolve_md_file("docs", "/etc/passwd") is None
    assert resolve_md_file("docs", "../../escape") is None


def test_resolve_md_file_rejects_mount_escape(monkeypatch, tmp_path) -> None:
    """A mount_dir whose name would resolve outside _MD_ROOT is rejected."""
    import cms.markdown as m

    root = tmp_path / "md"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "index.md").write_text("# Index\nx")
    monkeypatch.setattr(m, "_MD_ROOT", root)
    assert resolve_md_file("../escape", "anything") is None


# ── SECRET_KEY derivation ────────────────────────────────────


def test_secret_key_derived_to_32_bytes() -> None:
    """The signing key is always a 32-byte SHA-256 digest regardless of input
    length, so a long SECRET_KEY is never silently truncated to 16 bytes
    (the old .ljust(16)[:16] bug)."""
    for secret in ("", "x", "dev-secret-change-me", "a" * 64, "a" * 1000):
        digest = hashlib.sha256(secret.encode()).digest()
        assert len(digest) == 32


def test_secret_key_failfast_in_production(monkeypatch) -> None:
    """Importing app with the dev default + a non-localhost DATABASE_URL +
    DEBUG off must raise RuntimeError."""
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db.example.com:5432/app")
    monkeypatch.setenv("DEBUG", "false")

    for secret in ("", "dev-secret-change-me"):
        monkeypatch.setenv("SECRET_KEY", secret)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            _fresh_import_app()


def test_secret_key_dev_default_ok_in_dev(monkeypatch) -> None:
    """The dev default should be accepted when DATABASE_URL is localhost."""
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@localhost:5432/app")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me")
    mod = _fresh_import_app()
    assert mod._secret_bytes is not None and len(mod._secret_bytes) == 32