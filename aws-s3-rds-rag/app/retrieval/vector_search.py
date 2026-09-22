"""Question embedding + top-k vector similarity search."""

import logging
import uuid

from app.db.repository import Repository, RetrievedChunk
from app.embeddings.service import EmbeddingService
from app.exceptions import AppError, InvalidQueryError, RetrievalError

logger = logging.getLogger(__name__)

__all__ = ["VectorSearch", "RetrievedChunk"]


class VectorSearch:
    def __init__(self, repo: Repository, embedder: EmbeddingService) -> None:
        self.repo = repo
        self.embedder = embedder

    def search(
        self, question: str, top_k: int = 5, document_id: uuid.UUID | None = None
    ) -> list[RetrievedChunk]:
        query = (question or "").strip()
        if not query:
            raise InvalidQueryError("Question must not be empty")
        if not 1 <= top_k <= 50:
            raise InvalidQueryError("top_k must be between 1 and 50")

        logger.info("retrieval query question_chars=%d top_k=%d", len(query), top_k)
        vector = self.embedder.embed_query(query)
        try:
            results = self.repo.similarity_search(vector, top_k=top_k, document_id=document_id)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("retrieval failure")
            raise RetrievalError() from exc
        logger.info("retrieval results count=%d", len(results))
        return results
