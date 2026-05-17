# FireWatch — Database Recovery Runbook

## Backup location
Daily backups are stored in Cloudflare R2:
- Bucket: `firewatch-documents`
- Key pattern: `backups/postgres/{YYYY-MM-DD}.dump`
- Schedule: 02:00 UTC daily (Celery beat — `workers.backup.daily_backup`)
- Retention: 30 days (R2 lifecycle rule — configure manually in R2 dashboard)

## List available backups
```bash
aws s3 ls s3://firewatch-documents/backups/postgres/ \
  --endpoint-url https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

## Download a backup
```bash
aws s3 cp s3://firewatch-documents/backups/postgres/2026-05-14.dump ./restore.dump \
  --endpoint-url https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
```

## Restore to a database
```bash
pg_restore -d $DATABASE_URL -Fc --no-owner ./restore.dump
```

## Steps
1. Spin up a new Railway Postgres service
2. Set DATABASE_URL env var to the new service
3. Download the latest backup from R2
4. Run `pg_restore` as above
5. Run `alembic upgrade head` to ensure migrations are current
6. Restart backend service
7. Smoke-test: `GET /health` returns 200

## R2 Lifecycle rule (30-day retention)
Set in Cloudflare R2 dashboard → Bucket settings → Lifecycle rules:
- Prefix: `backups/postgres/`
- Expire after: 30 days

## Checking backup status via API
```bash
# Requires admin JWT token
curl -H "Authorization: Bearer <token>" \
  https://<backend-url>/api/v2/admin/backup/status
```
