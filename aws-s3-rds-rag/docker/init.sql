-- Runs once when the local PostgreSQL (pgvector image) container initializes an empty data volume.
-- Tables and the HNSW index are created by the application at startup (app/db/database.py).
CREATE EXTENSION IF NOT EXISTS vector;
