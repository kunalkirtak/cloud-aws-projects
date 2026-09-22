import pytest

from app.exceptions import InvalidStorageKeyError, ObjectNotFoundError, StorageError
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


# ---- local storage -----------------------------------------------------
def test_local_put_get_roundtrip(tmp_path):
    store = LocalStorage(tmp_path)
    info = store.put("nested/file.txt", b"hello")
    assert info.size == 5
    assert store.get("nested/file.txt") == b"hello"
    assert store.exists("nested/file.txt")
    assert store.head("nested/file.txt").content_type == "text/plain"


def test_local_list_and_prefix(tmp_path):
    store = LocalStorage(tmp_path)
    store.put("a.txt", b"1")
    store.put("sub/b.txt", b"22")
    store.put(".hidden", b"x")
    assert [o.key for o in store.list()] == ["a.txt", "sub/b.txt"]
    assert [o.key for o in store.list("sub/")] == ["sub/b.txt"]


def test_local_missing_object(tmp_path):
    store = LocalStorage(tmp_path)
    with pytest.raises(ObjectNotFoundError):
        store.get("missing.txt")
    assert not store.exists("missing.txt")


def test_local_rejects_path_traversal(tmp_path):
    store = LocalStorage(tmp_path / "root")
    for bad in ("../evil.txt", "/etc/passwd", "a/../../evil.txt", ""):
        with pytest.raises(InvalidStorageKeyError):
            store.put(bad, b"x")


def test_local_delete(tmp_path):
    store = LocalStorage(tmp_path)
    store.put("gone.txt", b"x")
    store.delete("gone.txt")
    store.delete("gone.txt")  # idempotent
    assert not store.exists("gone.txt")


# ---- S3 storage (mocked with moto; no AWS credentials needed) ----------
@pytest.fixture()
def s3_env(monkeypatch):
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="unit-test-bucket")
        yield client


def test_s3_put_get_roundtrip_with_prefix(s3_env):
    store = S3Storage("unit-test-bucket", region="us-east-1", prefix="documents/")
    store.put("uploads/a.txt", b"hello s3", "text/plain")
    assert store.get("uploads/a.txt") == b"hello s3"
    keys = [o["Key"] for o in s3_env.list_objects_v2(Bucket="unit-test-bucket")["Contents"]]
    assert keys == ["documents/uploads/a.txt"]


def test_s3_head_and_list_return_relative_keys(s3_env):
    store = S3Storage("unit-test-bucket", region="us-east-1", prefix="documents/")
    store.put("one.txt", b"12345", "text/plain")
    store.put("two.md", b"1", "text/markdown")
    assert store.head("one.txt").size == 5
    assert sorted(o.key for o in store.list()) == ["one.txt", "two.md"]


def test_s3_missing_object_and_delete(s3_env):
    store = S3Storage("unit-test-bucket", region="us-east-1", prefix="documents/")
    with pytest.raises(ObjectNotFoundError):
        store.get("nope.txt")
    store.put("x.txt", b"x")
    store.delete("x.txt")
    assert not store.exists("x.txt")


def test_s3_missing_bucket_maps_to_storage_error(s3_env):
    store = S3Storage("bucket-that-does-not-exist", region="us-east-1")
    with pytest.raises(StorageError):
        store.get("a.txt")


def test_s3_requires_bucket_name():
    with pytest.raises(StorageError):
        S3Storage("")


def test_s3_rejects_unsafe_keys():
    store = S3Storage("bucket", client=object())
    with pytest.raises(InvalidStorageKeyError):
        store.get("../secret.txt")
