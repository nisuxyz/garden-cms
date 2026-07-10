# tests/test_storage.py
"""
Unit tests for cms.storage — LocalStorageBackend (save/get/delete/url +
traversal guard) and the factory fallback path.

S3StorageBackend is covered by interface-level tests with a mocked
aioboto3 session in test_storage_s3.py.
"""
from __future__ import annotations

import pytest

from cms.storage import LocalStorageBackend, get_backend, load_backend


# ── LocalStorageBackend ────────────────────────────────────


@pytest.mark.asyncio
async def test_local_save_and_get_roundtrip(tmp_path):
    backend = LocalStorageBackend(root=tmp_path / "media")
    await backend.save("test.png", b"\x89PNG-data", "image/png")
    body, ct = await backend.get_object("test.png")
    assert body == b"\x89PNG-data"
    assert "image/png" in ct or "png" in ct


@pytest.mark.asyncio
async def test_local_delete_is_silent_on_missing(tmp_path):
    backend = LocalStorageBackend(root=tmp_path / "media")
    # Should not raise.
    await backend.delete("no-such-file.png")


@pytest.mark.asyncio
async def test_local_delete_removes_existing(tmp_path):
    backend = LocalStorageBackend(root=tmp_path / "media")
    await backend.save("to-delete.txt", b"bye", "text/plain")
    await backend.delete("to-delete.txt")
    with pytest.raises(FileNotFoundError):
        await backend.get_object("to-delete.txt")


def test_local_url_returns_media_path():
    backend = LocalStorageBackend()
    assert backend.url("foo.png") == "/media/foo.png"


@pytest.mark.asyncio
async def test_local_get_object_missing_raises_filenotfound(tmp_path):
    backend = LocalStorageBackend(root=tmp_path / "media")
    with pytest.raises(FileNotFoundError):
        await backend.get_object("missing.png")


@pytest.mark.asyncio
async def test_local_save_nested_subdir(tmp_path):
    """A filename with a subdirectory should create the parent dirs."""
    backend = LocalStorageBackend(root=tmp_path / "media")
    await backend.save("sub/dir/file.jpg", b"data", "image/jpeg")
    body, _ = await backend.get_object("sub/dir/file.jpg")
    assert body == b"data"


# ── Factory ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_backend_defaults_to_local(engine):
    backend = await load_backend()
    assert isinstance(backend, LocalStorageBackend)


def test_get_backend_fallback_returns_local(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    # Reset the cached singleton so the env fallback path runs.
    import cms.storage as s
    s._backend = None
    backend = get_backend()
    assert isinstance(backend, LocalStorageBackend)