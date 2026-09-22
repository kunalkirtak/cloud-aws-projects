"""Document upload, ingestion and inspection endpoints."""

import logging
import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.deps import get_pipeline, get_repository, get_settings, get_storage
from app.config import Settings
from app.db.repository import Repository
from app.exceptions import (
    AppError,
    DatabaseError,
    DocumentNotFoundError,
    EmptyDocumentError,
    InvalidRequestError,
    PayloadTooLargeError,
)
from app.ingestion.loaders import get_loader, title_from_filename
from app.ingestion.pipeline import IngestionPipeline
from app.schemas.documents import (
    ChunkPreview,
    DocumentDetail,
    DocumentListResponse,
    DocumentOut,
    IngestRequest,
    IngestResponse,
    IngestResultOut,
)
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", name).strip("._")
    return cleaned or "document"


@router.post("/upload", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    ingest: bool = Query(False, description="Ingest immediately after upload"),
    settings: Settings = Depends(get_settings),
    repo: Repository = Depends(get_repository),
    storage: StorageBackend = Depends(get_storage),
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    original = Path((file.filename or "").replace("\\", "/")).name
    if not original:
        raise InvalidRequestError("An uploaded file with a filename is required")
    get_loader(original)  # validates the extension (raises UnsupportedFileTypeError)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"File exceeds the {settings.max_upload_mb} MB limit")
    if not data.strip():
        raise EmptyDocumentError("Uploaded file is empty")

    filename = _safe_filename(original)
    key = f"uploads/{uuid.uuid4().hex[:12]}-{filename}"
    content_type = mimetypes.guess_type(filename)[0] or file.content_type or "application/octet-stream"

    storage.put(key, data, content_type)
    try:
        doc = repo.create_document(
            filename=filename,
            title=title_from_filename(filename),
            storage_key=key,
            content_type=content_type,
            size=len(data),
        )
    except DatabaseError:
        try:
            storage.delete(key)  # do not leave orphaned objects behind
        except AppError:
            logger.warning("failed to clean up stored object after database error")
        raise
    logger.info("document uploaded document_id=%s filename=%s size=%d", doc.id, filename, len(data))

    if ingest:
        pipeline.ingest(doc)
    return DocumentOut.model_validate(doc)


@router.post("/ingest", response_model=IngestResponse)
def ingest_documents(
    request: IngestRequest | None = None,
    repo: Repository = Depends(get_repository),
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    request = request or IngestRequest()

    if request.document_id is not None:
        doc = repo.get_document(request.document_id)
        if doc is None:
            raise DocumentNotFoundError()
        doc = pipeline.ingest(doc)
        results = [IngestResultOut(document_id=doc.id, filename=doc.filename, status=doc.status, chunk_count=doc.chunk_count)]
    elif request.storage_key:
        doc = pipeline.register_object(request.storage_key)
        doc = pipeline.ingest(doc)
        results = [IngestResultOut(document_id=doc.id, filename=doc.filename, status=doc.status, chunk_count=doc.chunk_count)]
    else:
        outcomes = pipeline.ingest_all(force=request.force)
        results = [IngestResultOut.model_validate(o, from_attributes=True) for o in outcomes]

    failed = sum(1 for r in results if r.status == "failed")
    return IngestResponse(results=results, succeeded=len(results) - failed, failed=failed)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repo: Repository = Depends(get_repository),
):
    items, total = repo.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, repo: Repository = Depends(get_repository)):
    doc = repo.get_document(document_id)
    if doc is None:
        raise DocumentNotFoundError()
    chunks = repo.get_chunks(document_id, limit=50)
    base = DocumentOut.model_validate(doc).model_dump()
    previews = [
        ChunkPreview(
            id=c.id,
            chunk_index=c.chunk_index,
            preview=c.content[:200],
            metadata=c.chunk_metadata or {},
        )
        for c in chunks
    ]
    return DocumentDetail(**base, chunks=previews)
