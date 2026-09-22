"""Build the configured storage backend."""

from app.config import Settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


def build_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket_name or "",
            region=settings.aws_region,
            prefix=settings.s3_prefix,
        )
    return LocalStorage(settings.local_storage_path)
