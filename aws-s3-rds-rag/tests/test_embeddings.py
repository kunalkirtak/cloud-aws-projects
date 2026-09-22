import os

import pytest

from app.embeddings.service import (
    EmbeddingService,
    HashingBackend,
    SentenceTransformerBackend,
)
from app.exceptions import EmbeddingError


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_embedding_dimension_and_normalization(embedder):
    vector = embedder.embed_query("Amazon S3 stores objects in buckets")
    assert len(vector) == 384
    assert abs(_dot(vector, vector) - 1.0) < 1e-6


def test_embeddings_are_deterministic(embedder):
    assert embedder.embed_query("hello world") == embedder.embed_query("hello world")


def test_batch_embedding(embedder):
    vectors = embedder.embed_documents(["one", "two words", "three more words here"])
    assert len(vectors) == 3
    assert all(len(v) == 384 for v in vectors)
    assert embedder.embed_documents([]) == []


def test_related_text_scores_higher_than_unrelated(embedder):
    query = embedder.embed_query("virtual servers in the cloud")
    related = embedder.embed_query("EC2 provides virtual servers in the cloud")
    unrelated = embedder.embed_query("chocolate cake recipe with flour and sugar")
    assert _dot(query, related) > _dot(query, unrelated)


def test_dimension_mismatch_raises_embedding_error():
    service = EmbeddingService(HashingBackend(16), dimension=384)
    with pytest.raises(EmbeddingError):
        service.embed_query("hello")


def test_backend_exceptions_are_wrapped():
    class Boom(HashingBackend):
        def embed(self, texts):
            raise RuntimeError("model crashed")

    with pytest.raises(EmbeddingError):
        EmbeddingService(Boom(384), 384).embed_query("x")


@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1 to download the real model")
def test_real_sentence_transformer_model():
    pytest.importorskip("sentence_transformers")
    service = EmbeddingService(SentenceTransformerBackend("sentence-transformers/all-MiniLM-L6-v2"), 384)
    q = service.embed_query("How do I store files in the cloud?")
    good = service.embed_query("Amazon S3 is object storage for files.")
    bad = service.embed_query("Bananas are yellow fruit.")
    assert _dot(q, good) > _dot(q, bad)
