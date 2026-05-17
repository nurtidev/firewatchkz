"""workers/backup.py — daily pg_dump to R2."""
import datetime
import logging
import os
import subprocess
import tempfile

from celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db_url() -> str:
    """Return the DATABASE_URL normalised to a plain postgresql:// scheme."""
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    # pg_dump needs the plain postgresql:// scheme (no +asyncpg driver qualifier)
    return (
        db_url.replace("postgresql+asyncpg://", "postgresql://")
              .replace("postgresql+psycopg://", "postgresql://")
    )


def _upload_to_r2(key: str, file_path: str) -> int:
    """Upload *file_path* to R2 under *key*. Returns the file size in bytes."""
    try:
        import boto3  # noqa: PLC0415 — optional at import time
    except ImportError as exc:
        raise RuntimeError("boto3 is not installed; cannot upload backup") from exc

    account_id = os.environ["R2_ACCOUNT_ID"]
    access_key_id = os.environ["R2_ACCESS_KEY_ID"]
    secret_access_key = os.environ["R2_SECRET_ACCESS_KEY"]
    bucket = os.getenv("R2_BUCKET", "firewatch-documents")
    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )

    size_bytes = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=f,
            ContentType="application/octet-stream",
        )

    return size_bytes


@celery_app.task(name="workers.backup.daily_backup", queue="backup")
def daily_backup() -> dict:
    """Dump the database and upload to R2 under backups/postgres/{date}.dump.

    Always returns a result dict — never raises.
    """
    date_str = datetime.date.today().isoformat()
    key = f"backups/postgres/{date_str}.dump"

    try:
        db_url = _get_db_url()

        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["pg_dump", db_url, "-Fc", "-f", tmp_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes max
            )

            if result.returncode != 0:
                logger.error("pg_dump failed (rc=%d): %s", result.returncode, result.stderr)
                return {
                    "status": "error",
                    "error": f"pg_dump exited with code {result.returncode}: {result.stderr.strip()}",
                }

            size_bytes = _upload_to_r2(key, tmp_path)

        finally:
            # Always clean up the temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        logger.info("daily_backup: uploaded %s (%d bytes)", key, size_bytes)
        return {"status": "ok", "key": key, "size_bytes": size_bytes}

    except Exception as exc:  # noqa: BLE001 — never raise from a backup task
        logger.exception("daily_backup failed: %s", exc)
        return {"status": "error", "error": str(exc)}
