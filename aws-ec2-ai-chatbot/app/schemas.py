"""Pydantic request/response models for the chatbot API."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming payload for POST /chat."""

    question: str = Field(..., min_length=1, max_length=500, description="The user's question.")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty or whitespace only")
        return stripped


class SourceItem(BaseModel):
    """A single retrieved knowledge base source with its relevance score."""

    id: str
    title: str
    score: float


class ChatResponse(BaseModel):
    """Response payload for POST /chat."""

    question: str
    answer: str
    sources: List[SourceItem]


class HealthResponse(BaseModel):
    """Response payload for GET /health."""

    status: str
    knowledge_base_documents: int
