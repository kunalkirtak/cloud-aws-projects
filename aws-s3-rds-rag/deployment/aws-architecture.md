# AWS Architecture

```
                USER
                  |
                  v
           FastAPI API  (EC2 / container, IAM role attached)
                  |
      +-----------+-----------+
      |                       |
      v                       v
     S3                 RDS PostgreSQL
 (documents)                  |
                          pgvector
                              |
                              v
                         RAG pipeline
              (embeddings -> retrieval -> generation)
```

## What is local vs AWS-managed

| Component | Local development | AWS deployment |
|---|---|---|
| API | `uvicorn` / Docker Compose | EC2 (Docker) now; ECS/Fargate later |
| Documents | `data/documents/` (`STORAGE_BACKEND=local`) | S3 private bucket (`STORAGE_BACKEND=s3`) |
| Database | Docker `pgvector/pgvector:pg16` | Amazon RDS for PostgreSQL + pgvector |
| Embeddings | sentence-transformers inside the API process | same (runs in the API container) |
| Credentials | none needed | IAM role on the compute resource |

## Networking

- **VPC**: your private network in AWS.
- **Subnets**: slices of the VPC. Put RDS in *private* subnets (DB subnet group needs subnets in at least two AZs). The API can live in a public subnet for a learning demo.
- **Security groups** (stateful firewalls):
  - `api-sg`: inbound TCP 8000 (or 80/443 behind a load balancer) from *your IP only* for a demo.
  - `rds-sg`: inbound TCP 5432 **only from `api-sg`** (reference the security group, not an IP range).
- **RDS** is never publicly accessible in the recommended setup.
- **S3** is a regional service reached over the AWS network via the instance's IAM role. Optionally add an S3 gateway VPC endpoint so traffic stays inside AWS.

## Simplified demo vs production

| Topic | Learning demo | Production |
|---|---|---|
| Compute | Single EC2 instance | ECS/Fargate, autoscaling, load balancer + HTTPS |
| Database | Single-AZ RDS | Multi-AZ, backups, monitoring, secrets rotation |
| Secrets | `.env` on the instance | AWS Secrets Manager / SSM Parameter Store |
| Auth | none | Cognito/OIDC/API gateway |
| Ingestion | synchronous | queue + workers |

## IAM

Attach a role with `deployment/iam-policy.json` (replace `YOUR-BUCKET-NAME`) to the compute resource. Do not use `AdministratorAccess` and do not put access keys in code or images.
