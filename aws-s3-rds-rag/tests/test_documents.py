import uuid

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.exceptions import MalformedDocumentError, UnsupportedFileTypeError
from app.ingestion.loaders import get_loader, normalize_text, title_from_filename
from app.main import app
from app.schemas.documents import IngestRequest
from app.schemas.rag import QueryRequest
from tests.helpers import upload_and_ingest


# ---- schemas -----------------------------------------------------------
def test_ingest_request_rejects_both_targets():
    with pytest.raises(ValidationError):
        IngestRequest(document_id=uuid.uuid4(), storage_key="a.txt")


def test_ingest_request_allows_empty_scan_mode():
    request = IngestRequest()
    assert request.document_id is None and request.storage_key is None and request.force is False


@pytest.mark.parametrize("payload", [{"question": ""}, {"question": "   "}, {"question": "ok", "top_k": 0}, {"question": "ok", "top_k": 51}])
def test_query_request_validation(payload):
    with pytest.raises(ValidationError):
        QueryRequest(**payload)


# ---- loaders -----------------------------------------------------------
def test_loader_selection_and_unsupported_type():
    assert get_loader("a.TXT").extensions == (".txt",)
    assert get_loader("b.md").extensions == (".md",)
    assert get_loader("c.pdf").extensions == (".pdf",)
    with pytest.raises(UnsupportedFileTypeError):
        get_loader("virus.exe")


def test_text_loader_rejects_binary_content():
    with pytest.raises(MalformedDocumentError):
        get_loader("bad.txt").load(b"abc\x00def")


def test_normalize_text():
    assert normalize_text("a \t b\r\n\r\n\r\n\r\nc  ") == "a b\n\nc"


def test_title_from_filename():
    assert title_from_filename("aws-s3_overview.txt") == "aws s3 overview"


def test_pdf_loader_extracts_text():
    fitz = pytest.importorskip("fitz")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Hello from a PDF about vector search")
    data = pdf.tobytes()
    pdf.close()
    assert "vector search" in get_loader("doc.pdf").load(data)


def test_pdf_loader_rejects_garbage():
    pytest.importorskip("fitz")
    with pytest.raises(MalformedDocumentError):
        get_loader("doc.pdf").load(b"this is not a pdf")


# ---- upload validation --------------------------------------------------
def test_upload_rejects_unsupported_extension(client):
    response = client.post("/documents/upload", files={"file": ("malware.exe", b"data", "application/octet-stream")})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_empty_file(client):
    response = client.post("/documents/upload", files={"file": ("empty.txt", b"   ", "text/plain")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_document"


def test_upload_requires_file(client):
    response = client.post("/documents/upload")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_upload_rejects_oversized_file(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, database_url="sqlite://", max_upload_mb=1
    )
    response = client.post(
        "/documents/upload",
        files={"file": ("big.txt", b"a" * (1024 * 1024 + 1), "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_upload_sanitizes_filename(client, storage):
    response = client.post(
        "/documents/upload",
        files={"file": ("../../etc/passwd.txt", b"some harmless text", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert ".." not in body["storage_key"]
    assert storage.exists(body["storage_key"])


# ---- upload / ingest / list / detail -----------------------------------
def test_upload_then_ingest_flow(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("guide.md", b"# Guide\n\nAmazon S3 stores objects in buckets.", "text/markdown")},
    )
    assert response.status_code == 201
    doc = response.json()
    assert doc["status"] == "pending" and doc["chunk_count"] == 0

    ingest = client.post("/documents/ingest", json={"document_id": doc["id"]})
    assert ingest.status_code == 200
    result = ingest.json()
    assert result["succeeded"] == 1 and result["failed"] == 0
    assert result["results"][0]["status"] == "ingested"

    detail = client.get(f"/documents/{doc['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ingested"
    assert body["chunk_count"] == len(body["chunks"]) >= 1
    assert body["chunks"][0]["metadata"]["source"] == "guide.md"


def test_upload_with_immediate_ingest(client):
    response = client.post(
        "/documents/upload?ingest=true",
        files={"file": ("quick.txt", b"RDS is a managed relational database service.", "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ingested"


def test_list_documents(client):
    upload_and_ingest(client, "a.txt", "Alpha document text.")
    upload_and_ingest(client, "b.txt", "Beta document text.")
    response = client.get("/documents?limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2 and len(body["items"]) == 1


def test_get_unknown_document_returns_404(client):
    response = client.get(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_get_document_invalid_uuid(client):
    assert client.get("/documents/not-a-uuid").status_code == 422


def test_ingest_unknown_document_returns_404(client):
    response = client.post("/documents/ingest", json={"document_id": str(uuid.uuid4())})
    assert response.status_code == 404


def test_ingest_failure_marks_document_failed(client):
    upload = client.post("/documents/upload", files={"file": ("broken.txt", b"abc\x00def", "text/plain")})
    doc = upload.json()
    response = client.post("/documents/ingest", json={"document_id": doc["id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "malformed_document"
    detail = client.get(f"/documents/{doc['id']}").json()
    assert detail["status"] == "failed"
    assert detail["chunk_count"] == 0 and detail["error_message"]


def test_ingest_scan_mode_is_idempotent(client, storage):
    storage.put("manual-notes.md", b"# Notes\n\nPostgreSQL stores relational data.")
    storage.put("README.md", b"# ignored")
    storage.put("image.png", b"\x89PNG")

    first = client.post("/documents/ingest").json()
    names = [r["filename"] for r in first["results"]]
    assert names == ["manual-notes.md"]
    assert first["results"][0]["status"] == "ingested"

    second = client.post("/documents/ingest").json()
    assert second["results"][0]["skipped"] is True

    forced = client.post("/documents/ingest", json={"force": True}).json()
    assert forced["results"][0]["skipped"] is False


def test_ingest_by_storage_key(client, storage):
    storage.put("direct.txt", b"Security groups act as virtual firewalls.")
    response = client.post("/documents/ingest", json={"storage_key": "direct.txt"})
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "ingested"
    missing = client.post("/documents/ingest", json={"storage_key": "nope.txt"})
    assert missing.status_code == 404
