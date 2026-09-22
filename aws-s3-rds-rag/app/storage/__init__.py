"""Object storage abstraction (local filesystem or Amazon S3)."""

from app.storage.base import StorageBackend, StoredObject
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage

__all__ = ["StorageBackend", "StoredObject", "LocalStorage", "S3Storage"]
