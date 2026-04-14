# cms/storage.py
"""
Pluggable storage backends for media files.

Backends
────────
  LocalStorageBackend  – writes to ``data/media/`` on disk (default)
  S3StorageBackend     – uploads to an S3-compatible bucket

Selection is controlled by the ``STORAGE_BACKEND`` env-var
(``"local"`` or ``"s3"``).  Call :func:`get_backend` to obtain the
active singleton.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    """Abstract interface that every storage adapter must implement."""

    @abstractmethod
    async def save(self, filename: str, data: bytes, content_type: str) -> str:
        """Persist *data* under *filename*.

        Returns the backend-specific path stored in ``MediaFile.file_path``.
        """

    @abstractmethod
    async def delete(self, filename: str) -> None:
        """Remove a previously-stored file.  Must not raise if missing."""

    @abstractmethod
    def url(self, filename: str) -> str:
        """Return the public URL (or path) at which *filename* is served."""


# ── Local disk ─────────────────────────────────────────────


class LocalStorageBackend(StorageBackend):
    """Store files under a local directory (default: ``data/media/``)."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path("data/media")

    async def save(self, filename: str, data: bytes, content_type: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        dest = self.root / filename
        dest.write_bytes(data)
        return str(dest)

    async def delete(self, filename: str) -> None:
        try:
            (self.root / filename).unlink()
        except FileNotFoundError:
            pass

    def url(self, filename: str) -> str:
        return f"/media/{filename}"

    async def get_object(self, filename: str) -> tuple[bytes, str]:
        """Read a file from disk."""
        import mimetypes

        path = self.root / filename
        if not path.is_file():
            raise FileNotFoundError(filename)
        data = path.read_bytes()
        ct = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return data, ct


# ── S3-compatible ──────────────────────────────────────────


class S3StorageBackend(StorageBackend):
    """Store files in an S3-compatible bucket.

    Configured via environment variables:

    * ``S3_BUCKET``          – bucket name (**required**)
    * ``S3_REGION``          – AWS region (default ``us-east-1``)
    * ``S3_ENDPOINT_URL``    – custom endpoint (MinIO, R2, etc.)
    * ``S3_ACCESS_KEY_ID``   – credentials
    * ``S3_SECRET_ACCESS_KEY``
    * ``S3_PREFIX``          – optional key prefix (e.g. ``"uploads/"``)
    * ``S3_PUBLIC_URL``      – if set, :meth:`url` returns a direct URL
                               instead of the ``/media/`` proxy path
    """

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str | None = None,
        public_url: str | None = None,
    ) -> None:
        self.bucket = bucket or os.environ.get("S3_BUCKET", "")
        self.region = region or os.getenv("S3_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.access_key_id = access_key_id or os.getenv("S3_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY")
        self.prefix = (prefix or os.getenv("S3_PREFIX", "")).strip("/")
        self.public_url = (public_url or os.getenv("S3_PUBLIC_URL", "")).rstrip("/")

    def _key(self, filename: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{filename}"
        return filename

    def _session_kwargs(self) -> dict:
        kwargs: dict = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id:
            kwargs["aws_access_key_id"] = self.access_key_id
        if self.secret_access_key:
            kwargs["aws_secret_access_key"] = self.secret_access_key
        return kwargs

    async def save(self, filename: str, data: bytes, content_type: str) -> str:
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", **self._session_kwargs()) as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=self._key(filename),
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        return self._key(filename)

    async def delete(self, filename: str) -> None:
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", **self._session_kwargs()) as s3:
            await s3.delete_object(Bucket=self.bucket, Key=self._key(filename))

    def url(self, filename: str) -> str:
        if self.public_url:
            return f"{self.public_url}/{self._key(filename)}"
        # Fall back to the local proxy route.
        return f"/media/{filename}"

    async def get_object(self, filename: str) -> tuple[bytes, str]:
        """Download an object — used by the media proxy route."""
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", **self._session_kwargs()) as s3:
            resp = await s3.get_object(Bucket=self.bucket, Key=self._key(filename))
            body = await resp["Body"].read()
            ct = resp.get("ContentType", "application/octet-stream")
        return body, ct


# ── Factory ────────────────────────────────────────────────

_backend: StorageBackend | None = None


async def _load_settings() -> dict[str, str]:
    """Load media-related settings from the DB ``site_settings`` table.

    Falls back to environment variables when a key is missing or empty.
    """
    from db.tables import SiteSettings

    rows = await SiteSettings.select(SiteSettings.key, SiteSettings.value)
    db_map = {r["key"]: r["value"] for r in rows if r["value"]}
    return db_map


async def load_backend() -> StorageBackend:
    """Build a :class:`StorageBackend` from DB settings (with env-var fallback).

    Called during app startup and when settings are saved via the admin UI.
    """
    global _backend
    settings = await _load_settings()

    name = (settings.get("storage_backend") or os.getenv("STORAGE_BACKEND", "local")).lower()
    if name == "s3":
        _backend = S3StorageBackend(
            bucket=settings.get("s3_bucket") or os.environ.get("S3_BUCKET", ""),
            region=settings.get("s3_region") or os.getenv("S3_REGION", "us-east-1"),
            endpoint_url=settings.get("s3_endpoint_url") or os.getenv("S3_ENDPOINT_URL"),
            access_key_id=settings.get("s3_access_key_id") or os.getenv("S3_ACCESS_KEY_ID"),
            secret_access_key=settings.get("s3_secret_access_key") or os.getenv("S3_SECRET_ACCESS_KEY"),
            prefix=settings.get("s3_prefix") or os.getenv("S3_PREFIX", ""),
            public_url=settings.get("s3_public_url") or os.getenv("S3_PUBLIC_URL", ""),
        )
    else:
        _backend = LocalStorageBackend()
    return _backend


def get_backend() -> StorageBackend:
    """Return the configured :class:`StorageBackend` singleton.

    Before :func:`load_backend` has been called (e.g. at import time),
    this falls back to env-var based initialisation.
    """
    global _backend
    if _backend is None:
        name = os.getenv("STORAGE_BACKEND", "local").lower()
        if name == "s3":
            _backend = S3StorageBackend()
        else:
            _backend = LocalStorageBackend()
    return _backend


async def ensure_fresh_backend() -> None:
    """Reload the storage backend from DB settings when running stateless.

    In stateful mode (``STATELESS`` env-var unset) this is a no-op — the
    backend is initialised once at startup and only rebuilt on admin
    settings save.  In stateless mode the backend is rebuilt from
    database settings on every call so that configuration changes made by
    another instance take effect immediately.
    """
    from cms.site_context import STATELESS

    if STATELESS:
        await load_backend()
