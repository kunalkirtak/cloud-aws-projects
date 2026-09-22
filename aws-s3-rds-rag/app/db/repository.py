"""Data-access layer. All SQLAlchemy errors are converted to DatabaseError."""

import functools
import logging
import math
import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk, DocumentStatus
from app.exceptions import DatabaseError

logger = logging.getLogger(__name__)


@dataclass
class NewChunk:
    chunk_index: int
    content: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    source: str
    chunk_index: int
    content: str
    score: float


def _db_errors(func_):
    @functools.wraps(func_)
    def wrapper(self, *args, **kwargs):
        try:
            return func_(self, *args, **kwargs)
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.error("database error op=%s error_type=%s", func_.__name__, type(exc).__name__)
            raise DatabaseError() from exc

    return wrapper


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- documents -------------------------------------------------
    @_db_errors
    def create_document(self, *, filename, title, storage_key, content_type, size) -> Document:
        doc = Document(
            filename=filename,
            title=title,
            storage_key=storage_key,
            content_type=content_type,
            size=size,
            status=DocumentStatus.PENDING,
        )
        self.session.add(doc)
        self.session.commit()
        return doc

    @_db_errors
    def get_document(self, document_id: uuid.UUID) -> Document | None:
        return self.session.get(Document, document_id)

    @_db_errors
    def get_document_by_storage_key(self, storage_key: str) -> Document | None:
        return self.session.scalar(select(Document).where(Document.storage_key == storage_key))

    @_db_errors
    def list_documents(self, limit: int = 50, offset: int = 0) -> tuple[list[Document], int]:
        total = self.session.scalar(select(func.count()).select_from(Document)) or 0
        items = self.session.scalars(
            select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        ).all()
        return list(items), int(total)

    @_db_errors
    def mark_processing(self, doc: Document) -> None:
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = None
        self.session.commit()

    @_db_errors
    def complete_ingestion(self, doc: Document, chunks: list[NewChunk]) -> None:
        """Atomically replace chunks and mark the document as ingested."""
        self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        self.session.add_all(
            [
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    embedding=c.embedding,
                    chunk_metadata=c.metadata,
                )
                for c in chunks
            ]
        )
        doc.status = DocumentStatus.INGESTED
        doc.chunk_count = len(chunks)
        doc.error_message = None
        self.session.commit()

    @_db_errors
    def mark_failed(self, doc: Document, message: str) -> None:
        doc.status = DocumentStatus.FAILED
        doc.chunk_count = 0
        doc.error_message = message[:1000]
        self.session.commit()

    @_db_errors
    def get_chunks(self, document_id: uuid.UUID, limit: int = 50) -> list[DocumentChunk]:
        return list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
                .limit(limit)
            ).all()
        )

    @_db_errors
    def ping(self) -> bool:
        self.session.execute(text("SELECT 1"))
        return True

    # ---- vector search ---------------------------------------------
    @_db_errors
    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
    ) -> list[RetrievedChunk]:
        dialect = self.session.get_bind().dialect.name
        base_cols = (
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            Document.title,
            Document.filename,
        )

        if dialect == "postgresql":
            distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
            stmt = (
                select(*base_cols, distance)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.status == DocumentStatus.INGESTED)
            )
            if document_id is not None:
                stmt = stmt.where(DocumentChunk.document_id == document_id)
            stmt = stmt.order_by(distance).limit(top_k)
            rows = self.session.execute(stmt).all()
            return [
                RetrievedChunk(r[0], r[1], r[4], r[5], r[2], r[3], 1.0 - float(r[6]))
                for r in rows
            ]

        # Fallback (SQLite, used by unit tests): exact cosine similarity in Python.
        stmt = (
            select(*base_cols, DocumentChunk.embedding)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.status == DocumentStatus.INGESTED)
        )
        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)
        rows = self.session.execute(stmt).all()
        scored = [
            RetrievedChunk(r[0], r[1], r[4], r[5], r[2], r[3], cosine_similarity(query_embedding, list(r[6])))
            for r in rows
        ]
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]
