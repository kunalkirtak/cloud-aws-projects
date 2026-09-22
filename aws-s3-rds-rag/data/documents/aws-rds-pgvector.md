# Amazon RDS for PostgreSQL and pgvector

Amazon RDS is a managed relational database service. RDS for PostgreSQL handles provisioning, patching, backups and failover so you can focus on the application.

The pgvector extension adds a vector data type and similarity operators to PostgreSQL. Embeddings can be stored in a vector column and searched with cosine distance, so semantic retrieval runs inside the same database as your metadata.

An HNSW index speeds up approximate nearest neighbor search on vector columns.

Place the RDS instance in private subnets and allow port 5432 only from the application's security group. Do not expose the database publicly.

RDS instances, storage and backups can incur charges. Delete the instance and manual snapshots when you finish experimenting.
