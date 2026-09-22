import httpx
import pytest

from app.config import Settings
from app.db.repository import Repository
from app.exceptions import (
    EmbeddingError,
    GenerationError,
    InvalidQueryError,
)
from app.embeddings.service import EmbeddingService
from app.generation.service import (
    NO_ANSWER,
    ExtractiveGenerator,
    OpenAICompatibleGenerator,
    build_generation_service,
)
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.vector_search import VectorSearch
from tests.helpers import upload_and_ingest

DOCS = {
    "ec2-overview.txt": "Amazon EC2 provides resizable virtual servers in the cloud. EC2 instances run applications with configurable CPU and memory.",
    "s3-overview.txt": "Amazon S3 is object storage for files. S3 stores objects in buckets and provides durability and scalability.",
    "rds-overview.txt": "Amazon RDS is a managed relational database service. RDS supports PostgreSQL and automates backups.",
}


@pytest.fixture()
def indexed(client):
    return {name: upload_and_ingest(client, name, text) for name, text in DOCS.items()}


def _pipeline(session, storage, embedder):
    return IngestionPipeline(Repository(session), storage, embedder, chunk_size=800, chunk_overlap=100)


# ---- retrieval ---------------------------------------------------------
def test_vector_search_ranks_relevant_document_first(session, storage, embedder):
    pipeline = _pipeline(session, storage, embedder)
    for name, text in DOCS.items():
        storage.put(name, text.encode())
        pipeline.ingest(pipeline.register_object(name))

    search = VectorSearch(Repository(session), embedder)
    results = search.search("What is object storage in S3?", top_k=3)
    assert len(results) == 3
    assert results[0].source == "s3-overview.txt"
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert results[0].title == "s3 overview" and results[0].content


def test_vector_search_validates_input(session, embedder):
    search = VectorSearch(Repository(session), embedder)
    with pytest.raises(InvalidQueryError):
        search.search("   ")
    with pytest.raises(InvalidQueryError):
        search.search("valid question", top_k=0)


def test_vector_search_with_no_documents(session, embedder):
    assert VectorSearch(Repository(session), embedder).search("anything here") == []


# ---- ingestion atomicity -----------------------------------------------
def test_failed_embedding_leaves_no_chunks(session, storage):
    class BrokenEmbedder(EmbeddingService):
        def __init__(self):
            pass

        def embed_documents(self, texts):
            raise EmbeddingError("boom")

    repo = Repository(session)
    storage.put("x.txt", b"Some text that will fail to embed.")
    pipeline = IngestionPipeline(repo, storage, BrokenEmbedder(), 800, 100)
    doc = pipeline.register_object("x.txt")
    with pytest.raises(EmbeddingError):
        pipeline.ingest(doc)
    assert doc.status == "failed"
    assert doc.error_message == "boom"
    assert repo.get_chunks(doc.id) == []


# ---- API ---------------------------------------------------------------
def test_rag_query_returns_answer_and_sources(client, indexed):
    response = client.post("/rag/query", json={"question": "What is object storage in S3?", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What is object storage in S3?"
    assert body["generation_mode"] == "extractive"
    assert "object storage" in body["answer"].lower()
    assert len(body["sources"]) == 3
    top = body["sources"][0]
    assert top["source"] == "s3-overview.txt"
    assert {"document_id", "title", "chunk_id", "score"} <= set(top)
    scores = [s["score"] for s in body["sources"]]
    assert scores == sorted(scores, reverse=True)


def test_rag_query_other_topic(client, indexed):
    body = client.post(
        "/rag/query", json={"question": "Which service is a managed relational database?", "top_k": 2}
    ).json()
    assert body["sources"][0]["source"] == "rds-overview.txt"


def test_rag_top_k_is_respected(client, indexed):
    body = client.post("/rag/query", json={"question": "cloud services", "top_k": 1}).json()
    assert len(body["sources"]) == 1


def test_rag_document_filter(client, indexed):
    ec2_id = indexed["ec2-overview.txt"]["id"]
    body = client.post(
        "/rag/query", json={"question": "What is object storage?", "top_k": 5, "document_id": ec2_id}
    ).json()
    assert body["sources"] and all(s["document_id"] == ec2_id for s in body["sources"])


def test_rag_query_without_documents(client):
    body = client.post("/rag/query", json={"question": "What is EC2?"}).json()
    assert body["answer"] == NO_ANSWER
    assert body["sources"] == []


@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "   "}, {"question": "hi", "top_k": 0}])
def test_rag_query_validation(client, payload):
    response = client.post("/rag/query", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---- generation --------------------------------------------------------
def test_extractive_generator_uses_context_only():
    from app.db.repository import RetrievedChunk
    import uuid

    chunk = RetrievedChunk(uuid.uuid4(), uuid.uuid4(), "t", "s.txt", 0, "Cats are mammals. Dogs bark loudly.", 0.9)
    result = ExtractiveGenerator().generate("Do dogs bark?", [chunk])
    assert result.used_llm is False and result.mode == "extractive"
    assert "Dogs bark loudly." in result.answer
    assert "Cats" not in result.answer
    assert ExtractiveGenerator().generate("q", []).answer == NO_ANSWER


def test_llm_provider_requires_configuration():
    settings = Settings(_env_file=None, database_url="sqlite://", generation_provider="openai_compatible")
    with pytest.raises(GenerationError):
        build_generation_service(settings)


def _chunk():
    from app.db.repository import RetrievedChunk
    import uuid

    return RetrievedChunk(uuid.uuid4(), uuid.uuid4(), "Doc", "doc.txt", 0, "Context text.", 0.8)


def test_llm_generator_success(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert url.endswith("/chat/completions")
        assert "Context text." in json["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " The answer [1]. "}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OpenAICompatibleGenerator("http://llm.local/v1", "not-a-real-key", "test-model")
    result = generator.generate("question?", [_chunk()])
    assert result.answer == "The answer [1]."
    assert result.used_llm is True and result.mode == "llm:test-model"


def test_llm_generator_failure_is_wrapped(monkeypatch):
    def fake_post(*args, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OpenAICompatibleGenerator("http://llm.local/v1", "not-a-real-key", "test-model")
    with pytest.raises(GenerationError):
        generator.generate("question?", [_chunk()])
