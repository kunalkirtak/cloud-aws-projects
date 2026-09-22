"""Integration test against a real PostgreSQL + pgvector database.

Skipped unless TEST_DATABASE_URL is set (CI provides a pgvector service container).
"""

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.database import init_db, make_engine
from app.db.models import Document
from app.db.repository import NewChunk, Repository
from app.embeddings.service import EmbeddingService, HashingBackend

URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set"),
]


def test_pgvector_similarity_search():
    engine = make_engine(URL)
    init_db(engine)
    embedder = EmbeddingService(HashingBackend(384), 384)
    texts = [
        "S3 stores objects in buckets for durable object storage.",
        "EC2 provides virtual servers with configurable CPU.",
        "RDS is a managed relational database service.",
    ]
    with Session(engine, expire_on_commit=False) as session:
        repo = Repository(session)
        doc = repo.create_document(
            filename="pg-it.txt",
            title="pg it",
            storage_key=f"it/{uuid.uuid4().hex}.txt",
            content_type="text/plain",
            size=100,
        )
        try:
            vectors = embedder.embed_documents(texts)
            repo.complete_ingestion(doc, [NewChunk(i, t, v, {}) for i, (t, v) in enumerate(zip(texts, vectors))])
            hits = repo.similarity_search(embedder.embed_query("object storage buckets"), top_k=3)
            assert len(hits) == 3
            assert "bucket" in hits[0].content.lower()
            assert hits[0].score >= hits[-1].score
        finally:
            session.execute(delete(Document).where(Document.id == doc.id))
            session.commit()
    engine.dispose()
