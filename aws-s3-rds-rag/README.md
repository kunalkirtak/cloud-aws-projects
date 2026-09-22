# AWS S3 + RDS RAG Application

A Retrieval-Augmented Generation (RAG) backend that stores documents in **Amazon S3**, keeps metadata and **vector embeddings in PostgreSQL (Amazon RDS + pgvector)**, and serves answers through **FastAPI**. Everything runs locally without AWS (local file storage + Docker PostgreSQL) so it can be reviewed and tested without credentials.

This is **Project 02** of an AWS cloud portfolio. Project 01 covered EC2, FastAPI, IAM, Security Groups and Docker. This project adds S3, RDS, PostgreSQL/pgvector, document ingestion, chunking, embeddings and vector similarity search.

## Overview

Organizations keep knowledge in documents. RAG lets users ask natural-language questions and get answers grounded in those documents, with sources. This project implements the full pipeline: upload, extraction, chunking, embedding, vector storage, similarity search, context construction and answer generation.

> **Honest note on generation:** the default answer generator is **extractive** (it selects the most relevant sentences from retrieved chunks; no LLM is used). Retrieval is genuinely embedding-based. An OpenAI-compatible LLM provider is available as an **optional**, disabled-by-default plug-in. The API response always reports `generation_mode`.

## Features

- S3 document storage (private bucket, SSE, IAM-role access) with a local-filesystem backend for development
- PostgreSQL metadata (documents, chunks, ingestion status) via SQLAlchemy 2.x
- pgvector storage and cosine-similarity search inside PostgreSQL (HNSW index)
- Document ingestion for `.txt`, `.md`, `.pdf` (PyMuPDF), with normalization and configurable chunking
- Local embeddings with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- Retrieval and generation are separate layers (`VectorSearch`, `GenerationService`)
- FastAPI with Pydantic schemas and clean JSON errors
- Docker Compose (API + pgvector PostgreSQL with health checks)
- Pytest suite that needs no AWS and no PostgreSQL (S3 mocked with `moto`), plus an optional real-pgvector integration test
- GitHub Actions CI, AWS architecture/IAM/S3/RDS documentation

## Architecture

```mermaid
flowchart LR
    U[User] --> API[FastAPI API]
    API -->|upload / read| S3[(S3 bucket)]
    API --> ING[Ingestion: extract, chunk]
    S3 --> ING
    ING --> EMB[Embedding service]
    EMB -->|vectors + metadata| PG[(RDS PostgreSQL + pgvector)]
    U -->|question| API
    API --> QE[Question embedding]
    QE --> RET[Vector similarity search]
    PG --> RET
    RET -->|top-k chunks| GEN[Generation service]
    GEN --> ANS[Answer + sources]
    ANS --> U
```

### Local development architecture

```mermaid
flowchart LR
    U[User / curl / Swagger] --> API[FastAPI in Docker or uvicorn]
    API --> FS[(data/documents/)]
    API --> PG[(Docker PostgreSQL + pgvector)]
```

| Layer | Local | AWS |
|---|---|---|
| Documents | `data/documents/` | S3 bucket |
| Database | Docker `pgvector/pgvector:pg16` | RDS PostgreSQL + pgvector |
| API | uvicorn / Docker | EC2 (Docker) today, ECS later |
| Credentials | none | IAM role |

## AWS Architecture

- **S3**: private bucket for the raw documents.
- **RDS PostgreSQL**: relational metadata + pgvector embeddings, in private subnets.
- **VPC / subnets**: the API runs in one subnet; RDS uses a DB subnet group in at least two AZs.
- **Security groups**: `api-sg` allows the API port from your IP; `rds-sg` allows TCP 5432 **only from `api-sg`**.
- **IAM**: a role attached to the compute resource grants least-privilege S3 access (see [`deployment/iam-policy.json`](deployment/iam-policy.json)).
- **Compute**: an EC2 instance running the Docker image (simplest learning path); ECS/Fargate is a future improvement.

Details: [`deployment/aws-architecture.md`](deployment/aws-architecture.md), [`s3-setup.md`](deployment/s3-setup.md), [`rds-setup.md`](deployment/rds-setup.md).

## RAG Pipeline

**Indexing:** Document -> S3/local storage -> text extraction -> normalization -> chunking (with overlap) -> embedding -> vector storage (PostgreSQL/pgvector).

**Querying:** Question -> question embedding -> cosine similarity search -> top-k chunks -> context construction -> answer generation -> answer + sources.

## Why S3?

S3 is durable, scalable **object storage**. Documents are blobs addressed by key, not rows, so they belong in object storage rather than the database. It keeps the database small, supports encryption, versioning and fine-grained IAM access, and separates storage from compute.

## Why RDS PostgreSQL?

RDS is managed PostgreSQL: automated backups, patching, monitoring and optional Multi-AZ. PostgreSQL gives transactional, relational persistence for document metadata, ingestion status and chunks. Ingestion updates chunks and status in a single transaction.

## Why pgvector?

pgvector adds a `vector` type and similarity operators (cosine, L2, inner product) plus HNSW/IVFFlat indexes to PostgreSQL. Similarity search runs in the same database as your metadata, so you can filter and join with SQL and avoid operating a separate vector database.

## Why Embeddings?

Embeddings map text to vectors so that texts with similar **meaning** are close together, even without shared keywords. "How do I store files in the cloud?" can match a passage about "object storage" - keyword search would miss that.

## Project Structure

```
aws-s3-rds-rag/
├── app/
│   ├── main.py, config.py, exceptions.py, logging_config.py
│   ├── api/            deps.py, health.py, documents.py, rag.py
│   ├── db/             database.py, models.py, repository.py
│   ├── ingestion/      loaders.py, chunker.py, pipeline.py
│   ├── embeddings/     service.py
│   ├── retrieval/      vector_search.py
│   ├── generation/     service.py
│   ├── storage/        base.py, local.py, s3.py, factory.py
│   └── schemas/        documents.py, rag.py
├── data/documents/     README.md + sample documents
├── tests/              conftest.py, helpers.py, test_health.py, test_chunking.py,
│                       test_embeddings.py, test_documents.py, test_storage.py,
│                       test_rag.py, test_pgvector_integration.py
├── docker/init.sql
├── deployment/         aws-architecture.md, iam-policy.json, s3-setup.md, rds-setup.md
├── .github/workflows/tests.yml
├── .env.example, .gitignore, .dockerignore
├── Dockerfile, docker-compose.yml
├── requirements.txt, requirements-dev.txt, pytest.ini
└── README.md, LICENSE
```

## Tech Stack

Python 3.12, FastAPI, PostgreSQL, pgvector, SQLAlchemy 2.x, psycopg 3, Amazon S3 (boto3), sentence-transformers, PyMuPDF, Docker / Docker Compose, Pytest (+ moto), GitHub Actions.

## Local Setup

```bash
git clone <your-repo-url> aws-s3-rds-rag && cd aws-s3-rds-rag
python -m venv .venv && source .venv/bin/activate

# CPU-only PyTorch (much smaller than the default CUDA build)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env
docker compose up -d postgres          # local PostgreSQL + pgvector
uvicorn app.main:app --reload          # http://localhost:8000/docs
```

The first request that needs embeddings downloads the ~90 MB `all-MiniLM-L6-v2` model from Hugging Face.

## Docker Setup

```bash
cp .env.example .env
docker compose up --build              # API on :8000, PostgreSQL on 127.0.0.1:5432
```

Useful commands:

```bash
docker compose logs -f api             # follow API logs
docker compose ps                      # service health
docker compose exec postgres psql -U raguser -d ragdb -c "\dt"
docker compose down                    # stop (keeps the database volume)
docker compose down -v                 # stop and DELETE database + model-cache volumes
```

`./data/documents` is mounted into the container. The API container runs as UID 1000; on Linux hosts make sure that user can write to `data/documents`.

## Database

| | Local | AWS |
|---|---|---|
| Server | Docker `pgvector/pgvector:pg16` | Amazon RDS PostgreSQL |
| Extension | `docker/init.sql` runs `CREATE EXTENSION vector` | Run `CREATE EXTENSION vector` as the master user (the app also tries at startup) |
| Config | `DATABASE_URL=postgresql+psycopg://...@localhost:5432/ragdb` | Same variable, RDS endpoint, `?sslmode=require` |
| Network | published on localhost | private subnets, `rds-sg` allows 5432 from the API only |

Tables (`documents`, `document_chunks`) and the HNSW index are created at API startup. `document_chunks.embedding` is `vector(384)`; if you change the embedding model, update `EMBEDDING_DIM` and recreate the chunk table (or the database).

## API Documentation

Interactive docs: `http://localhost:8000/docs`.

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info |
| GET | `/health` | Health (`503` if the database is unavailable) |
| POST | `/documents/upload` | Multipart upload (`file`); `?ingest=true` ingests immediately |
| POST | `/documents/ingest` | `{"document_id": "..."}`, `{"storage_key": "..."}`, or no body to scan storage. `{"force": true}` re-ingests in scan mode |
| GET | `/documents` | List documents (`limit`, `offset`) |
| GET | `/documents/{document_id}` | Document details + chunk previews |
| POST | `/rag/query` | Ask a question (`question`, optional `top_k`, optional `document_id`) |

Errors use a uniform shape: `{"error": {"code": "unsupported_file_type", "message": "..."}}`. Internal stack traces are never returned.

## Uploading Documents

```bash
curl -F "file=@data/documents/aws-s3-overview.txt" "http://localhost:8000/documents/upload?ingest=true"
```

Or place files in `data/documents/` (local mode) or under the S3 prefix, then ingest everything new:

```bash
curl -X POST http://localhost:8000/documents/ingest
```

## Ingestion

1. Receive the file and validate the extension (`.txt`, `.md`, `.pdf`), size and emptiness.
2. Store it in local storage or S3.
3. Register a `documents` row (`pending`).
4. Extract text (TextLoader / MarkdownLoader / PDFLoader) and normalize it.
5. Split into overlapping chunks (`CHUNK_SIZE`, `CHUNK_OVERLAP`), keeping `document_id`, `source`, `title`, `chunk_index`.
6. Generate embeddings in batches.
7. In **one transaction**: replace the document's chunks and mark it `ingested`.
8. On any failure the document is marked `failed` with an error message and no partial chunks remain.

## Example RAG Request

```json
POST /rag/query
{
  "question": "What is object storage in S3?",
  "top_k": 3
}
```

## Example RAG Response

```json
{
  "question": "What is object storage in S3?",
  "answer": "Based on the retrieved documents: Amazon S3 (Simple Storage Service) is object storage. [1]",
  "generation_mode": "extractive",
  "sources": [
    {
      "document_id": "3f0c6a52-9d3e-4a35-8a1b-3c2f7a0d9e11",
      "title": "aws s3 overview",
      "source": "aws-s3-overview.txt",
      "chunk_id": "b6d1c7a4-2f47-4d0e-9a5e-1e1f2c3d4e5f",
      "chunk_index": 0,
      "score": 0.7412,
      "snippet": "Amazon S3 Overview ..."
    }
  ]
}
```

(Values are illustrative.)

## AWS S3 Setup

Summary (full steps in [`deployment/s3-setup.md`](deployment/s3-setup.md)):

1. Create a private bucket with a globally unique lowercase name; keep **Block all public access** on; use SSE-S3 encryption.
2. Create an IAM role for your compute resource from [`deployment/iam-policy.json`](deployment/iam-policy.json) (replace `YOUR-BUCKET-NAME`).
3. Set `STORAGE_BACKEND=s3`, `AWS_REGION`, `S3_BUCKET_NAME`, `S3_PREFIX=documents/`.

## AWS RDS Setup

Summary (full steps in [`deployment/rds-setup.md`](deployment/rds-setup.md)):

1. Create a DB subnet group (private subnets, 2+ AZs) and security groups `api-sg` / `rds-sg`.
2. Create RDS PostgreSQL with **Public access = No**, `rds-sg`, backups on, deletion protection on.
3. Run `CREATE EXTENSION IF NOT EXISTS vector;` and set `DATABASE_URL` from a secret store with `sslmode=require`.

## IAM

Attach an **IAM role** (instance profile) to the EC2/ECS compute resource; the AWS SDK picks up temporary credentials automatically, so no access keys live in code, images or `.env`. Conceptual policy (least privilege):

- `s3:ListBucket` on the bucket, limited to the `documents/` prefix
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::BUCKET/documents/*`

Do not attach `AdministratorAccess`. `s3:DeleteObject` is only used to remove an object when the database insert fails after an upload; remove it if you prefer.

## Security Groups

| SG | Inbound | Source |
|---|---|---|
| `api-sg` | TCP 8000 (or 443 behind a load balancer) | your IP / load balancer only |
| `rds-sg` | TCP 5432 | `api-sg` only |

Never open 5432 to `0.0.0.0/0`.

## Environment Variables

See [`.env.example`](.env.example). Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL (required) | - |
| `STORAGE_BACKEND` | `local` or `s3` | `local` |
| `LOCAL_STORAGE_PATH` | Folder for local mode | `data/documents` |
| `AWS_REGION`, `S3_BUCKET_NAME`, `S3_PREFIX` | S3 settings | `us-east-1`, empty, `documents/` |
| `EMBEDDING_BACKEND` | `sentence-transformers` or `hash` (tests only) | `sentence-transformers` |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | Model and vector size | MiniLM, `384` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | Chunking | `800`, `100` |
| `DEFAULT_TOP_K`, `MIN_SIMILARITY_SCORE` | Retrieval | `5`, `-1` (off) |
| `GENERATION_PROVIDER` | `extractive` or `openai_compatible` (optional) | `extractive` |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Optional LLM settings | empty |
| `MAX_UPLOAD_MB` | Upload size limit | `20` |

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The default suite runs **without AWS credentials and without PostgreSQL**: SQLite stands in for the database (vector search falls back to exact cosine similarity), S3 is mocked with `moto`, and a deterministic hashing embedder avoids model downloads.

- Real-model test: `RUN_MODEL_TESTS=1 pytest -m slow`
- Real pgvector test: `TEST_DATABASE_URL=postgresql+psycopg://raguser:ragpassword@localhost:5432/ragdb pytest -m integration` (with `docker compose up -d postgres`)

## GitHub Actions

`.github/workflows/tests.yml` runs on every push and pull request on Ubuntu with Python 3.12. It installs CPU PyTorch and the dependencies, starts a throwaway `pgvector/pgvector:pg16` service container, and runs `pytest` (including the pgvector integration test). No AWS credentials are used.

## Cost Safety

- AWS pricing varies by account, region, service and usage; Free Tier / Free Plan eligibility varies. **This project is not guaranteed to be free.**
- RDS instances, storage, backups and snapshots can generate charges depending on configuration and usage.
- S3 storage, requests and data transfer can generate charges.
- EC2 / container compute can generate charges while running.
- Check current AWS pricing before deploying; set a budget alert.
- **Stop or delete resources when finished**: RDS instance + snapshots, EC2 instances/volumes/Elastic IPs, S3 objects/versions/bucket.

## Security

- No credentials in code or the repo; `.env`, `*.pem`, `*.key` are git-ignored; `.env.example` has placeholders only (the local Docker password is a development placeholder - change it for anything else).
- S3: private bucket, Block Public Access, SSE, IAM-role access, least privilege.
- RDS: private subnets, `rds-sg` restricted to the API security group, TLS, credentials from environment/secret store, backups, deletion protection.
- Filenames are sanitized, storage keys are checked against path traversal, uploads are size-limited.
- Logs never contain secrets, passwords or document text (only counts and IDs).

## Limitations

- Embeddings run locally inside the API process (CPU); large ingests are slow.
- Default "generation" is extractive - it quotes relevant sentences and cannot synthesize or reason across sources.
- Limited document processing: no OCR (scanned PDFs yield no text), no tables/layout awareness, character-based chunking.
- Synchronous ingestion; no distributed queue or workers.
- No authentication or multi-tenancy.
- Simplified AWS deployment (single instance, no autoscaling / HTTPS included).
- Schema changes require manual migration (no Alembic yet).

## Future Improvements

ECS + ECR, authentication, Redis, asynchronous ingestion (SQS/workers), agent workflows, hybrid search, reranking, evaluation, observability, additional LLM providers, multi-tenant RAG, Alembic migrations.

## Learning Outcomes

- **AWS**: designing a private, least-privilege S3 + RDS + compute architecture; local-vs-cloud parity.
- **RAG**: separating indexing, retrieval and generation, and keeping answers traceable to sources.
- **PostgreSQL / vector databases**: transactional ingestion, pgvector columns, cosine distance, HNSW indexes.
- **Embeddings**: semantic similarity vs keyword matching, batch embedding, dimension consistency.
- **FastAPI**: dependency injection, Pydantic schemas, uniform error handling.
- **Docker**: multi-service Compose with health checks and named volumes.
- **IAM**: roles instead of access keys; resource- and prefix-scoped policies.
- **S3 / RDS**: bucket security, object storage abstractions, private database networking, cleanup and cost awareness.
