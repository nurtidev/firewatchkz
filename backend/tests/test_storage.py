import asyncio
import tempfile
import pytest
from services.storage import LocalStorageBackend, get_storage, make_document_key


@pytest.mark.asyncio
async def test_local_storage_upload_download():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageBackend(base_path=tmpdir)
        content = b"Hello, FireWatch test!"
        key = "test/file.txt"

        url = await storage.upload(key, content, "text/plain")
        assert "test/file.txt" in url

        downloaded = await storage.download(key)
        assert downloaded == content


@pytest.mark.asyncio
async def test_local_storage_exists_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageBackend(base_path=tmpdir)
        key = "test/delete_me.txt"

        assert not await storage.exists(key)
        await storage.upload(key, b"data", "text/plain")
        assert await storage.exists(key)
        await storage.delete(key)
        assert not await storage.exists(key)


@pytest.mark.asyncio
async def test_document_key_format():
    key = make_document_key("user-123", "card-456", "card.pdf")
    assert key == "documents/user-123/card-456/original.pdf"


def test_get_storage_returns_local_without_r2_env(monkeypatch):
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    storage = get_storage()
    from services.storage import LocalStorageBackend
    assert isinstance(storage, LocalStorageBackend)
