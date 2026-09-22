"""Application configuration loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # General
    app_name: str = "AWS S3 + RDS RAG Application"
    app_version: str = "1.0.0"
    environment: str = "local"
    log_level: str = "INFO"

    # Database (required: local Docker PostgreSQL or Amazon RDS PostgreSQL)
    database_url: str

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = "data/documents"
    aws_region: str = "us-east-1"
    s3_bucket_name: str | None = None
    s3_prefix: str = "documents/"
    max_upload_mb: int = Field(default=20, ge=1, le=200)

    # Embeddings
    embedding_backend: Literal["sentence-transformers", "hash"] = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = Field(default=384, ge=8, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=512)

    # Chunking / retrieval
    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    default_top_k: int = Field(default=5, ge=1, le=50)
    min_similarity_score: float = Field(default=-1.0, ge=-1.0, le=1.0)

    # Generation (extractive by default; LLM provider is optional)
    generation_provider: Literal["extractive", "openai_compatible"] = "extractive"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: int = Field(default=60, ge=1, le=600)

    @model_validator(mode="after")
    def _validate_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
