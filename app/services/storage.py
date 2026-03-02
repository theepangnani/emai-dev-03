"""
File storage service with local filesystem adapter.
Designed for easy swap to GCS — just replace LocalStorageAdapter with GCSAdapter.
"""
import os
import uuid
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Protocol

STORAGE_ROOT = os.environ.get("FILE_STORAGE_ROOT", "./file_storage")


@dataclass
class StoredFile:
    key: str          # e.g. "users/123/docs/abc123.pdf"
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    stored_at: datetime
    url: str          # signed URL or local serve URL


class StorageAdapter(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...
    def load(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def get_url(self, key: str, expires_in: int = 3600) -> str: ...


class LocalStorageAdapter:
    """Local filesystem adapter. Production: swap for GCSAdapter."""

    def __init__(self, root: str = STORAGE_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        # Local: return internal API URL; production GCS: return signed URL
        return f"/api/storage/files/{key}"


class FileStorageService:
    """High-level storage service. Use this in route handlers."""

    # Per-user quotas (bytes)
    QUOTA_FREE = 500 * 1024 * 1024          # 500 MB
    QUOTA_PREMIUM = 5 * 1024 * 1024 * 1024  # 5 GB

    # Per-file size limits
    MAX_FILE_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "20")) * 1024 * 1024

    def __init__(self, adapter: StorageAdapter | None = None):
        self.adapter = adapter or LocalStorageAdapter()

    def store_file(
        self,
        user_id: int,
        data: bytes,
        original_name: str,
        content_type: str | None = None,
        folder: str = "uploads",
    ) -> StoredFile:
        """Store a file, return StoredFile with key and URL."""
        if len(data) > self.MAX_FILE_SIZE:
            raise ValueError(f"File exceeds {self.MAX_FILE_SIZE // (1024 * 1024)} MB limit")

        if not content_type:
            content_type, _ = mimetypes.guess_type(original_name)
            content_type = content_type or "application/octet-stream"

        sha256 = hashlib.sha256(data).hexdigest()
        ext = Path(original_name).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        key = f"users/{user_id}/{folder}/{unique_name}"

        self.adapter.save(key, data, content_type)

        return StoredFile(
            key=key,
            original_name=original_name,
            content_type=content_type,
            size_bytes=len(data),
            sha256=sha256,
            stored_at=datetime.utcnow(),
            url=self.adapter.get_url(key),
        )

    def get_file(self, key: str) -> bytes:
        return self.adapter.load(key)

    def delete_file(self, key: str) -> None:
        self.adapter.delete(key)

    def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        return self.adapter.get_url(key, expires_in)

    def get_user_usage_bytes(self, storage_keys: list[str]) -> int:
        """Sum up storage usage for a list of keys."""
        total = 0
        for key in storage_keys:
            try:
                data = self.adapter.load(key)
                total += len(data)
            except Exception:
                pass
        return total


# Module-level singleton
_storage_service: FileStorageService | None = None


def get_storage_service() -> FileStorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = FileStorageService()
    return _storage_service
