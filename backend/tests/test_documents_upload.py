"""
tests/test_documents_upload.py — Unit tests for F-3 document upload + normalization.

All tests mock storage and DB — no live network or DB calls needed.
"""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db_override=None):
    """Return a minimal FastAPI app with only the v2 documents router.

    Accepts an optional async generator callable for the get_db dependency so
    tests can use app.dependency_overrides (FastAPI DI ignores module-level patches).
    Auth dependencies are bypassed with a stub user.
    """
    from fastapi import FastAPI
    from routers.v2.documents import router
    from db.session import get_db
    from services.auth import require_inspector_or_above, require_analyst_or_above

    _stub_user = {"id": "test-user", "role": "admin", "email": "test@test.com"}

    app = FastAPI()
    app.include_router(router, prefix="/api/v2/documents")
    if db_override is not None:
        app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_inspector_or_above] = lambda: _stub_user
    app.dependency_overrides[require_analyst_or_above] = lambda: _stub_user
    return app


# ---------------------------------------------------------------------------
# Test 1 — Upload endpoint returns 200 with card_id + status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_returns_card_id_and_status(monkeypatch):
    """POST /api/v2/documents/upload returns 200 with card_id and status='uploaded'."""
    # Patch get_db to yield a mock async session
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()

    async def _fake_get_db():
        yield mock_session

    # Patch get_storage to return a local-like mock
    mock_storage = AsyncMock()
    mock_storage.upload = AsyncMock(return_value="file:///tmp/test.pdf")

    # Patch normalize_document.delay so it doesn't hit Celery broker
    mock_task = MagicMock()

    with (
        patch("routers.v2.documents.get_storage", return_value=mock_storage),
        patch("workers.documents.normalize_document") as mock_nd,
    ):
        mock_nd.delay = mock_task
        app = _make_app(db_override=_fake_get_db)
        client = TestClient(app)

        file_content = b"%PDF-1.4 fake pdf content"
        response = client.post(
            "/api/v2/documents/upload",
            files={"file": ("test_card.pdf", io.BytesIO(file_content), "application/pdf")},
        )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "card_id" in data
    assert data["status"] == "uploaded"
    assert "upload_url" in data
    # card_id must be a non-empty string (UUID format)
    assert len(data["card_id"]) > 0


# ---------------------------------------------------------------------------
# Test 2 — normalize_document task returns expected dict shape
# ---------------------------------------------------------------------------


def test_normalize_document_task_shape():
    """normalize_document.apply() returns a dict with card_id and status keys."""
    # We only test the task registration and return shape here without a real DB.
    # The real DB path is covered by integration tests.
    from workers.documents import normalize_document

    # Mock the sync DB connection and storage calls
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = None  # card not found -> early return
    mock_conn.cursor.return_value = mock_cursor

    with patch("workers.documents._sync_db_conn", return_value=mock_conn):
        result = normalize_document.apply(args=["test-card-id-999"])

    result_dict = result.result
    assert isinstance(result_dict, dict)
    assert "card_id" in result_dict
    assert result_dict["card_id"] == "test-card-id-999"
    assert "status" in result_dict


# ---------------------------------------------------------------------------
# Test 3 — list endpoint returns array
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_documents_returns_array(monkeypatch):
    """GET /api/v2/documents/ returns a JSON array (possibly empty)."""
    from unittest.mock import MagicMock

    mock_session = AsyncMock()

    # Build a fake row mapping
    fake_row = {
        "id": "card-abc-123",
        "status": "uploaded",
        "file_name": "plan.pdf",
        "file_mime": "application/pdf",
        "uploaded_at": "2026-05-13 10:00:00+00:00",
        "building_id": None,
        "uploaded_by": None,
        "thumbnail_key": None,
        "converted_key": None,
    }
    fake_result = MagicMock()
    fake_result.mappings.return_value.all.return_value = [fake_row]
    mock_session.execute = AsyncMock(return_value=fake_result)

    async def _fake_get_db():
        yield mock_session

    app = _make_app(db_override=_fake_get_db)
    client = TestClient(app)
    response = client.get("/api/v2/documents/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "card-abc-123"
    assert data[0]["status"] == "uploaded"


# ---------------------------------------------------------------------------
# Test 4 — detail endpoint returns 404 for unknown card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_404_for_unknown_card(monkeypatch):
    """GET /api/v2/documents/{card_id} returns 404 when card does not exist."""
    mock_session = AsyncMock()

    fake_result = MagicMock()
    fake_result.mappings.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=fake_result)

    async def _fake_get_db():
        yield mock_session

    app = _make_app(db_override=_fake_get_db)
    client = TestClient(app)
    response = client.get("/api/v2/documents/nonexistent-card-id")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
