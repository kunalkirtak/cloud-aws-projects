"""Amazon S3 storage backend.

Credentials are never configured here: boto3's default credential chain is used
(IAM role on EC2/ECS, AWS_PROFILE, or environment variables for local testing).
"""

import logging

from botocore.exceptions import BotoCoreError, ClientError

from app.exceptions import InvalidStorageKeyError, ObjectNotFoundError, StorageError
from app.storage.base import StorageBackend, StoredObject

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}


class S3Storage(StorageBackend):
    name = "s3"

    def __init__(self, bucket: str, region: str | None = None, prefix: str = "", client=None) -> None:
        if not bucket:
            raise StorageError("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3")
        self.bucket = bucket
        self.region = region
        prefix = prefix.lstrip("/")
        self.prefix = prefix if (not prefix or prefix.endswith("/")) else prefix + "/"
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _full_key(self, key: str) -> str:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise InvalidStorageKeyError()
        return f"{self.prefix}{key}"

    @staticmethod
    def _translate(exc: Exception, key: str) -> Exception:
        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in _NOT_FOUND_CODES:
                return ObjectNotFoundError(f"Object not found: {key}")
            logger.error("s3 request failed code=%s", code)
        else:
            logger.error("s3 request failed error_type=%s", type(exc).__name__)
        return StorageError()

    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        full = self._full_key(key)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=full,
                Body=data,
                ContentType=content_type or "application/octet-stream",
                ServerSideEncryption="AES256",
            )
        except (ClientError, BotoCoreError) as exc:
            raise self._translate(exc, key) from exc
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get(self, key: str) -> bytes:
        full = self._full_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=full)
            return response["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            raise self._translate(exc, key) from exc

    def head(self, key: str) -> StoredObject:
        full = self._full_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=full)
        except (ClientError, BotoCoreError) as exc:
            raise self._translate(exc, key) from exc
        return StoredObject(
            key=key,
            size=int(response.get("ContentLength", 0)),
            content_type=response.get("ContentType"),
            last_modified=response.get("LastModified"),
        )

    def list(self, prefix: str = "") -> list[StoredObject]:
        results: list[StoredObject] = []
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{self.prefix}{prefix}"):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/"):
                        continue
                    results.append(
                        StoredObject(
                            key=obj["Key"][len(self.prefix):],
                            size=int(obj["Size"]),
                            last_modified=obj.get("LastModified"),
                        )
                    )
        except (ClientError, BotoCoreError) as exc:
            raise self._translate(exc, prefix) from exc
        return results

    def delete(self, key: str) -> None:
        full = self._full_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=full)
        except (ClientError, BotoCoreError) as exc:
            raise self._translate(exc, key) from exc
