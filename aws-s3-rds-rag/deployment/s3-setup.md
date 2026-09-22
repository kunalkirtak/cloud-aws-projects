# S3 Setup

Prices and Free Tier eligibility vary by account and region. Check current AWS pricing first and delete resources when finished.

1. **Choose a globally unique bucket name**, lowercase, e.g. `yourname-rag-docs-<random>`. Choose the same region as your compute/RDS.
2. **Create the bucket** (console: S3 > Create bucket).
   - Keep **Block all public access** ENABLED.
   - Leave ACLs disabled (bucket owner enforced).
   - Default encryption: SSE-S3 (the app also requests AES256 on upload).
   - Optional: enable versioning.
3. **Create an IAM role** for your compute resource (EC2 instance profile) and attach a policy based on `deployment/iam-policy.json` with your bucket name.
4. **Configure the app**:
```
   STORAGE_BACKEND=s3
   AWS_REGION=<your-region>
   S3_BUCKET_NAME=<your-bucket>
   S3_PREFIX=documents/
```
5. **Test**: upload a document through `POST /documents/upload`, then verify the object under `documents/uploads/` in the bucket.

For local testing against a real bucket use `aws configure sso`/`AWS_PROFILE` rather than long-lived keys; never commit credentials.

## Cleanup
Empty and delete the bucket (and versions) when you are done.
