"""Storage backend interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.exceptions import ObjectNotFoundError


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    content_type: str | None = None
    last_modified: datetime | None = None


class StorageBackend(ABC):
    name: str = "base"

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        """Store an object and return its metadata."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Return the object's bytes (raises ObjectNotFoundError)."""

    @abstractmethod
    def head(self, key: str) -> StoredObject:
        """Return object metadata (raises ObjectNotFoundError)."""

    @abstractmethod
    def list(self, prefix: str = "") -> list[StoredObject]:
        """List objects whose (relative) key starts with prefix."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object (no error if it does not exist)."""

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except ObjectNotFoundError:
            return False
