# File Storage — Security & Operations

## Architecture
Files are stored on a **Railway Volume** mounted at `/data/deals` in the backend container.
Access is gated by HMAC-signed tokens (TTL: 10 min) served via `GET /api/files/serve/{token}`.
Files are **never publicly accessible** — the endpoint validates auth before streaming.

## Key Isolation
Storage keys follow the pattern `{broker_id}/{deal_id}/{uuid}.{ext}` ensuring:
- Cross-tenant isolation by prefix
- Non-enumerable paths (UUID)
- No PII in filename (original name stored only in DB)

## Retention Policy
- Files from **cancelled deals older than 180 days** are deleted by the `cleanup_cancelled_deal_files` Celery task (runs daily at 02:00 UTC).
- DB audit records (`DealDocument`) are **kept** even after file deletion (storage_key set to NULL).
- Active deal files are retained indefinitely until deal completion or explicit deletion.

## Backup Procedure (Railway Volume Snapshots)
1. Go to Railway dashboard → your project → backend service → Volumes tab
2. Click on the volume → "Create Snapshot"
3. Label with date: `deals-YYYY-MM-DD`
4. Recommended: weekly snapshots, keep last 4

## Restore Procedure
1. Railway dashboard → Volumes → select snapshot
2. Click "Restore" → confirm
3. Backend service will restart automatically after volume restore

## Scaling Considerations
⚠️ **Railway Volumes are tied to a single replica.** If horizontal scaling is needed:
- Migrate driver to S3/R2 (code already supports it via `STORAGE_DRIVER=s3`)
- Run migration script to copy files from volume to bucket
- Update env vars and redeploy

## Local Development
Set `STORAGE_DRIVER=local` and `STORAGE_LOCAL_PATH=./.local-storage` (gitignored).
The signing secret (`STORAGE_SIGNING_SECRET`) should be any non-empty string locally.
