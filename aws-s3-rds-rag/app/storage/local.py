"""Local filesystem storage - lets the project run without AWS."""

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from app.exceptions import InvalidStorageKeyError, ObjectNotFoundError, StorageError
from app.storage.base import StorageBackend, StoredObject


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")) or "\x00" in key:
            raise InvalidStorageKeyError()
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise InvalidStorageKeyError("Storage key escapes the storage root")
        return candidate

    def _info(self, key: str, path: Path) -> StoredObject:
        stat = path.stat()
        return StoredObject(
            key=key,
            size=stat.st_size,
            content_type=mimetypes.guess_type(path.name)[0],
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )

    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise StorageError("Could not write to local storage") from exc
        return self._info(key, path)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(f"Object not found: {key}")
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("Could not read from local storage") from exc

    def head(self, key: str) -> StoredObject:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(f"Object not found: {key}")
        return self._info(key, path)

    def list(self, prefix: str = "") -> list[StoredObject]:
        results: list[StoredObject] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            key = rel.as_posix()
            if key.startswith(prefix):
                results.append(self._info(key, path))
        return results

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            raise StorageError("Could not delete from local storage") from exc
