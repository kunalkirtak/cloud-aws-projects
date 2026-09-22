# RDS PostgreSQL Setup

Prices and Free Tier eligibility vary by account, region and configuration. RDS instances, storage and backups can generate charges. Verify current pricing.

1. **Create a DB subnet group** with private subnets in at least two Availability Zones of your VPC.
2. **Create security groups**: `api-sg` for the compute resource and `rds-sg` for the database. In `rds-sg` allow inbound **TCP 5432 from `api-sg` only**.
3. **Create the database** (console: RDS > Create database):
   - Engine: PostgreSQL (a recent major version with pgvector support; confirm in the AWS documentation).
   - Template: Dev/Test; smallest instance class that suits your budget; single-AZ for a demo.
   - Public access: **No**.
   - VPC security group: `rds-sg`.
   - Credentials: choose a master username; let RDS manage the password in Secrets Manager or generate a strong password. Do not reuse passwords.
   - Backups: keep automated backups on with a short retention; enable deletion protection while running.
4. **Enable pgvector** by connecting as the master user (from the EC2 instance) and running:
```sql
   CREATE EXTENSION IF NOT EXISTS vector;
```
   The application also runs this at startup if the role is allowed to.
5. **Configure the app** (value comes from your secret store, never from git):
```
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<rds-endpoint>:5432/<db>?sslmode=require
```
6. **Verify**: `GET /health` should report `"database": "ok"`.

## Cleanup
Delete the DB instance, uncheck "create final snapshot" only if you do not need it, and delete leftover manual snapshots and automated backups to stop charges.
