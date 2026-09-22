"""Embedding service with pluggable backends.

- sentence-transformers (default): real local semantic embeddings.
- hash: deterministic feature-hashing vectors. Lexical only - intended for
  offline unit tests/CI, NOT for semantic retrieval quality.
"""

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import Settings, get_settings
from app.exceptions import AppError, EmbeddingError

logger = logging.getLogger(__name__)


class EmbeddingBackend(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class SentenceTransformerBackend(EmbeddingBackend):
    name = "sentence-transformers"

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self.model = model_name
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("loading embedding model model=%s", self.model)
            self._model = SentenceTransformer(self.model)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()


_TOKEN = re.compile(r"[a-z0-9]+")


class HashingBackend(EmbeddingBackend):
    name = "hash"
    model = "feature-hashing"

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            vec[idx] += 1.0 if digest[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            vec[0] = 1.0
            return vec
        return [x / norm for x in vec]


class EmbeddingService:
    """Single reusable entry point for document and query embeddings."""

    def __init__(self, backend: EmbeddingBackend, dimension: int) -> None:
        self.backend = backend
        self.dimension = dimension

    @property
    def info(self) -> dict:
        return {"backend": self.backend.name, "model": self.backend.model, "dimension": self.dimension}

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self.backend.embed(texts)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("embedding backend failure backend=%s", self.backend.name)
            raise EmbeddingError("Failed to generate embeddings") from exc
        if len(vectors) != len(texts) or any(len(v) != self.dimension for v in vectors):
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {self.dimension}. "
                "Check EMBEDDING_DIM against the embedding model and database schema."
            )
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embedding_service(settings: Settings) -> EmbeddingService:
    if settings.embedding_backend == "hash":
        backend: EmbeddingBackend = HashingBackend(settings.embedding_dim)
    else:
        backend = SentenceTransformerBackend(settings.embedding_model, settings.embedding_batch_size)
    return EmbeddingService(backend, settings.embedding_dim)


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return build_embedding_service(get_settings())
