"""Root and health endpoints."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_embedder, get_repository, get_settings
from app.config import Settings
from app.db.repository import Repository
from app.embeddings.service import EmbeddingService
from app.exceptions import AppError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/")
def root(settings: Settings = Depends(get_settings)):
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
def health(
    repo: Repository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedder),
):
    database = "ok"
    try:
        repo.ping()
    except AppError:
        database = "unavailable"
    body = {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "storage_backend": settings.storage_backend,
        "embedding": embedder.info,
        "generation_provider": settings.generation_provider,
    }
    if database != "ok":
        return JSONResponse(status_code=503, content=body)
    return body
