import os
import asyncio
from pathlib import Path
from typing import Optional
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        """Upload content and return public/presigned URL."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download and return content bytes."""

    @abstractmethod
    async def presigned_get(self, key: str, ttl_seconds: int = 3600) -> str:
        """Return a presigned GET URL valid for ttl_seconds."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete object by key."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if object exists."""


class R2Backend(StorageBackend):
    """Cloudflare R2 backend using the S3-compatible API via boto3."""

    def __init__(self) -> None:
        self.account_id = os.environ["R2_ACCOUNT_ID"]
        self.access_key_id = os.environ["R2_ACCESS_KEY_ID"]
        self.secret_access_key = os.environ["R2_SECRET_ACCESS_KEY"]
        self.bucket = os.getenv("R2_BUCKET", "firewatch-documents")
        self.public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

    def _get_client(self):
        import boto3  # noqa: PLC0415 — lazy import to avoid hard dependency
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
        )

    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _put() -> None:
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )

        await loop.run_in_executor(None, _put)

        if self.public_url:
            return f"{self.public_url}/{key}"
        return await self.presigned_get(key)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _get() -> bytes:
            response = client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()

        return await loop.run_in_executor(None, _get)

    async def presigned_get(self, key: str, ttl_seconds: int = 3600) -> str:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _presign() -> str:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )

        return await loop.run_in_executor(None, _presign)

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _delete() -> None:
            client.delete_object(Bucket=self.bucket, Key=key)

        await loop.run_in_executor(None, _delete)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _head() -> bool:
            import botocore.exceptions  # noqa: PLC0415
            try:
                client.head_object(Bucket=self.bucket, Key=key)
                return True
            except botocore.exceptions.ClientError:
                return False

        return await loop.run_in_executor(None, _head)


class LocalStorageBackend(StorageBackend):
    """Local filesystem backend for development without R2 credentials."""

    def __init__(self, base_path: str = "./local_storage") -> None:
        self.base_path = Path(base_path)

    def _resolve(self, key: str) -> Path:
        return self.base_path / key

    async def upload(self, key: str, content: bytes, content_type: str) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"file://{target.resolve()}"

    async def download(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    async def presigned_get(self, key: str, ttl_seconds: int = 3600) -> str:
        # No real signing needed in dev — return the same file:// URL.
        target = self._resolve(key)
        return f"file://{target.resolve()}"

    async def delete(self, key: str) -> None:
        self._resolve(key).unlink()

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()


def get_storage() -> StorageBackend:
    """Return the appropriate storage backend based on available env vars."""
    r2_vars = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    if all(os.getenv(v) for v in r2_vars):
        return R2Backend()
    return LocalStorageBackend(
        base_path=os.getenv("LOCAL_STORAGE_PATH", "./local_storage")
    )


# ---------------------------------------------------------------------------
# Key structure helpers
# ---------------------------------------------------------------------------

def make_document_key(user_id: str, card_id: str, filename: str) -> str:
    """Return the canonical storage key for an original uploaded document.

    Format: documents/{user_id}/{card_id}/original.{ext}
    """
    ext = Path(filename).suffix.lower()
    return f"documents/{user_id}/{card_id}/original{ext}"


def make_converted_key(user_id: str, card_id: str) -> str:
    """Return the canonical storage key for a PDF-converted document."""
    return f"documents/{user_id}/{card_id}/converted.pdf"


def make_thumbnail_key(user_id: str, card_id: str) -> str:
    """Return the canonical storage key for a document thumbnail."""
    return f"documents/{user_id}/{card_id}/thumb.jpg"
