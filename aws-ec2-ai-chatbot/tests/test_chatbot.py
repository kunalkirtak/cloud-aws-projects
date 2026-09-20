"""Tests for the /chat endpoint: happy path, validation, and fallback."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """TestClient as a context manager so lifespan startup/shutdown run."""
    with TestClient(app) as test_client:
        yield test_client


def test_chat_with_relevant_question_returns_sources(client):
    response = client.post("/chat", json={"question": "What is Amazon EC2?"})
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What is Amazon EC2?"
    assert len(body["answer"]) > 0
    assert len(body["sources"]) > 0
    assert body["sources"][0]["score"] > 0


def test_chat_with_empty_question_is_rejected(client):
    response = client.post("/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_with_whitespace_only_question_is_rejected(client):
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 422


def test_chat_with_excessively_long_question_is_rejected(client):
    response = client.post("/chat", json={"question": "a" * 1000})
    assert response.status_code == 422


def test_chat_with_malformed_request_is_rejected(client):
    response = client.post("/chat", json={"not_a_question": "hello"})
    assert response.status_code == 422


def test_chat_with_unrelated_question_returns_fallback(client):
    response = client.post("/chat", json={"question": "zzz qwqw unrelated nonsense xyzabc"})
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert "could not find" in body["answer"].lower()


def test_chat_with_docker_question_cites_docker_source(client):
    response = client.post("/chat", json={"question": "How does Docker package an application?"})
    assert response.status_code == 200
    body = response.json()
    source_ids = [source["id"] for source in body["sources"]]
    assert "backend-002" in source_ids
