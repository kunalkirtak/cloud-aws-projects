"""Document-related schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    title: str
    storage_key: str
    content_type: str | None = None
    size: int
    status: str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ChunkPreview(BaseModel):
    id: uuid.UUID
    chunk_index: int
    preview: str
    metadata: dict = Field(default_factory=dict)


class DocumentDetail(DocumentOut):
    chunks: list[ChunkPreview] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class IngestRequest(BaseModel):
    """Target for ingestion.

    - document_id: (re)ingest an already registered document
    - storage_key: register + ingest an object that already exists in storage
    - neither: scan the storage backend and ingest all new/failed documents
    """

    document_id: uuid.UUID | None = None
    storage_key: str | None = Field(default=None, min_length=1, max_length=512)
    force: bool = Field(default=False, description="Re-ingest documents that are already ingested (scan mode)")

    @model_validator(mode="after")
    def _exclusive_targets(self) -> "IngestRequest":
        if self.document_id is not None and self.storage_key:
            raise ValueError("Provide either document_id or storage_key, not both")
        return self


class IngestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID | None = None
    filename: str
    status: str
    chunk_count: int = 0
    error: str | None = None
    skipped: bool = False


class IngestResponse(BaseModel):
    results: list[IngestResultOut]
    succeeded: int
    failed: int
