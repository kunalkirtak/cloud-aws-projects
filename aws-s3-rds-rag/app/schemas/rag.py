"""RAG query schemas."""

import uuid

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    document_id: uuid.UUID | None = Field(default=None, description="Optional: restrict search to one document")

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


class SourceOut(BaseModel):
    document_id: uuid.UUID
    title: str
    source: str
    chunk_id: uuid.UUID
    chunk_index: int
    score: float
    snippet: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    generation_mode: str
    sources: list[SourceOut]
