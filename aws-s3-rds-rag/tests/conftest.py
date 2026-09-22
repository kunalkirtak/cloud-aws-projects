import os
import tempfile

# Configure the environment BEFORE importing the application.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["EMBEDDING_DIM"] = "384"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = tempfile.mkdtemp(prefix="rag-tests-")
os.environ["GENERATION_PROVIDER"] = "extractive"
os.environ["ENVIRONMENT"] = "test"
for _name in ("S3_BUCKET_NAME", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    os.environ.pop(_name, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_embedder, get_storage  # noqa: E402
from app.db.database import get_db, make_engine  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.embeddings.service import EmbeddingService, HashingBackend  # noqa: E402
from app.main import app  # noqa: E402
from app.storage.local import LocalStorage  # noqa: E402


@pytest.fixture()
def db_engine():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db_engine):
    with Session(db_engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture()
def embedder():
    return EmbeddingService(HashingBackend(384), 384)


@pytest.fixture()
def storage(tmp_path):
    return LocalStorage(tmp_path / "documents")


@pytest.fixture()
def client(db_engine, storage, embedder):
    def override_db():
        with Session(db_engine, expire_on_commit=False) as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_embedder] = lambda: embedder
    yield TestClient(app)
    app.dependency_overrides.clear()
