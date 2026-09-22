# Sample documents

Files in this folder are used when `STORAGE_BACKEND=local`.

- Drop `.txt`, `.md` or `.pdf` files here, then call `POST /documents/ingest` (no body) to ingest them.
- `README.md` itself is ignored by the ingestion scan.
- Files uploaded through the API are stored under `uploads/` (git-ignored).
