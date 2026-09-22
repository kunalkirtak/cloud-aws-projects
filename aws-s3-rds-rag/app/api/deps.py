"""FastAPI dependencies (overridable in tests)."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.database import get_db
from app.db.repository import Repository
from app.embeddings.service import EmbeddingService, get_embedding_service
from app.generation.service import GenerationService, build_generation_service
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.vector_search import VectorSearch
from app.storage.base import StorageBackend
from app.storage.factory import build_storage

__all__ = [
    "get_db",
    "get_settings",
    "get_repository",
    "get_storage",
    "get_embedder",
    "get_generator",
    "get_pipeline",
    "get_vector_search",
]


def get_repository(session: Session = Depends(get_db)) -> Repository:
    return Repository(session)


@lru_cache
def _storage_singleton() -> StorageBackend:
    return build_storage(get_settings())


def get_storage() -> StorageBackend:
    return _storage_singleton()


def get_embedder() -> EmbeddingService:
    return get_embedding_service()


@lru_cache
def _generator_singleton() -> GenerationService:
    return build_generation_service(get_settings())


def get_generator() -> GenerationService:
    return _generator_singleton()


def get_pipeline(
    repo: Repository = Depends(get_repository),
    storage: StorageBackend = Depends(get_storage),
    embedder: EmbeddingService = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> IngestionPipeline:
    return IngestionPipeline(
        repo=repo,
        storage=storage,
        embedder=embedder,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def get_vector_search(
    repo: Repository = Depends(get_repository),
    embedder: EmbeddingService = Depends(get_embedder),
) -> VectorSearch:
    return VectorSearch(repo, embedder)
