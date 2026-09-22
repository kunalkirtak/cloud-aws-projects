from app.api.deps import get_repository
from app.exceptions import DatabaseError
from app.main import app


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "name" in body and body["docs"] == "/docs"


def test_health_endpoint_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["storage_backend"] == "local"
    assert body["embedding"]["dimension"] == 384


def test_health_reports_database_failure(client):
    class BrokenRepo:
        def ping(self):
            raise DatabaseError()

    app.dependency_overrides[get_repository] = lambda: BrokenRepo()
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
