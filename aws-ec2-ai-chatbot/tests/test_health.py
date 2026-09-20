"""Tests for the root and health endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """TestClient as a context manager so lifespan startup/shutdown run."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["knowledge_base_documents"] > 0


def test_root_endpoint_returns_service_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "service" in body
    assert body["status"] == "running"
