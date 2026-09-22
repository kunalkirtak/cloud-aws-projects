"""Ingestion workflow: storage -> extraction -> chunking -> embeddings -> PostgreSQL."""

import logging
import mimetypes
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.db.models import Document, DocumentStatus
from app.db.repository import NewChunk, Repository
from app.embeddings.service import EmbeddingService
from app.exceptions import AppError, EmptyDocumentError, IngestionError
from app.ingestion.chunker import chunk_text
from app.ingestion.loaders import (
    SUPPORTED_EXTENSIONS,
    get_loader,
    normalize_text,
    title_from_filename,
)
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

IGNORED_FILENAMES = {"README.md"}


@dataclass
class IngestOutcome:
    document_id: uuid.UUID | None
    filename: str
    status: str
    chunk_count: int = 0
    error: str | None = None
    skipped: bool = False


class IngestionPipeline:
    def __init__(
        self,
        repo: Repository,
        storage: StorageBackend,
        embedder: EmbeddingService,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self.repo = repo
        self.storage = storage
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def register_object(self, storage_key: str) -> Document:
        """Register an object that already exists in storage (idempotent)."""
        existing = self.repo.get_document_by_storage_key(storage_key)
        if existing is not None:
            return existing
        info = self.storage.head(storage_key)  # raises ObjectNotFoundError
        filename = Path(storage_key).name
        get_loader(filename)  # validates extension
        return self.repo.create_document(
            filename=filename,
            title=title_from_filename(filename),
            storage_key=storage_key,
            content_type=info.content_type or mimetypes.guess_type(filename)[0],
            size=info.size,
        )

    def ingest(self, document: Document) -> Document:
        started = time.perf_counter()
        logger.info("ingestion started document_id=%s filename=%s", document.id, document.filename)
        self.repo.mark_processing(document)
        try:
            data = self.storage.get(document.storage_key)
            text = normalize_text(get_loader(document.filename).load(data))
            if not text:
                raise EmptyDocumentError("Document contains no extractable text")

            text_chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
            logger.info("chunking complete document_id=%s chunk_count=%d", document.id, len(text_chunks))

            vectors = self.embedder.embed_documents([c.content for c in text_chunks])
            logger.info("embeddings generated document_id=%s count=%d", document.id, len(vectors))

            new_chunks = [
                NewChunk(
                    chunk_index=c.index,
                    content=c.content,
                    embedding=v,
                    metadata={
                        "document_id": str(document.id),
                        "source": document.filename,
                        "title": document.title,
                        "chunk_index": c.index,
                        "start_char": c.start_char,
                        "end_char": c.end_char,
                    },
                )
                for c, v in zip(text_chunks, vectors)
            ]
            self.repo.complete_ingestion(document, new_chunks)  # atomic
        except AppError as exc:
            logger.warning("ingestion failed document_id=%s code=%s", document.id, exc.code)
            self._record_failure(document, exc.message)
            raise
        except Exception as exc:
            logger.exception("unexpected ingestion failure document_id=%s", document.id)
            self._record_failure(document, "Unexpected error during ingestion")
            raise IngestionError("Ingestion failed unexpectedly") from exc

        logger.info(
            "ingestion completed document_id=%s chunks=%d seconds=%.2f",
            document.id,
            document.chunk_count,
            time.perf_counter() - started,
        )
        return document

    def ingest_all(self, force: bool = False) -> list[IngestOutcome]:
        """Scan storage; register and ingest supported objects."""
        outcomes: list[IngestOutcome] = []
        for obj in self.storage.list():
            name = Path(obj.key).name
            if name in IGNORED_FILENAMES or Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            doc: Document | None = None
            try:
                doc = self.register_object(obj.key)
                if doc.status == DocumentStatus.INGESTED and not force:
                    outcomes.append(
                        IngestOutcome(doc.id, doc.filename, doc.status, doc.chunk_count, skipped=True)
                    )
                    continue
                doc = self.ingest(doc)
                outcomes.append(IngestOutcome(doc.id, doc.filename, doc.status, doc.chunk_count))
            except AppError as exc:
                outcomes.append(
                    IngestOutcome(
                        document_id=doc.id if doc is not None else None,
                        filename=name,
                        status=DocumentStatus.FAILED,
                        error=exc.message,
                    )
                )
        return outcomes

    def _record_failure(self, document: Document, message: str) -> None:
        try:
            self.repo.mark_failed(document, message)
        except AppError:
            logger.error("could not record ingestion failure document_id=%s", document.id)
