"""
tests/test_documents_crud.py — Unit tests for F-9 document CRUD endpoints.

Tests cover:
  GET  /{card_id}/status
  GET  /{card_id}/extraction
  PATCH /{card_id}/extraction
  DELETE /{card_id}

All DB calls are mocked — no live network or DB needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db_override=None):
    from fastapi import FastAPI
    from routers.v2.documents import router
    from db.session import get_db
    from services.auth import require_inspector_or_above, require_analyst_or_above

    _stub_user = {"id": "test-user", "role": "admin", "email": "test@test.com"}

    app = FastAPI()
    app.include_router(router, prefix="/api/v2/documents")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_inspector_or_above] = lambda: _stub_user
    app.dependency_overrides[require_analyst_or_above] = lambda: _stub_user
    return app


def _mock_session_returning(rows_by_call):
    """
    Return a mock AsyncSession whose execute() returns different results
    depending on call order. rows_by_call is a list of values; each call to
    session.execute() pops the next one and wraps it so that either
    .mappings().first() or .mappings().all() returns the value.
    """
    call_index = {"i": 0}
    results = list(rows_by_call)

    async def _execute(*args, **kwargs):
        value = results[call_index["i"]]
        call_index["i"] += 1
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = value
        mock_result.mappings.return_value.all.return_value = [value] if value else []
        return mock_result

    session = AsyncMock()
    session.execute = _execute
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test 1 — GET /{card_id}/status returns card_id and status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_returns_card_status():
    """GET /status returns {card_id, status, processed_at} for a known card."""
    fake_row = {
        "id": "card-001",
        "status": "extracted",
        "approved_at": None,
    }
    session = _mock_session_returning([fake_row])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/documents/card-001/status")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["card_id"] == "card-001"
    assert data["status"] == "extracted"
    assert "processed_at" in data


# ---------------------------------------------------------------------------
# Test 2 — GET /{card_id}/status 404 for missing card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_404_for_missing_card():
    """GET /status returns 404 when the card does not exist."""
    session = _mock_session_returning([None])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/documents/nonexistent-card/status")

    assert response.status_code == 404
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Test 3 — GET /{card_id}/extraction returns extraction data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_extraction_returns_data():
    """GET /extraction returns the linked card_extractions row."""
    card_row = {"extraction_id": "ext-001"}
    extraction_row = {
        "id": "ext-001",
        "card_id": "card-002",
        "model_version": "claude-haiku-4-5",
        "extracted_data": {"floors": 5},
        "field_confidences": {"floors": 0.95},
        "vulnerabilities": None,
        "extraction_cost_usd": "0.002",
        "duration_ms": 1200,
        "human_corrections": None,
        "created_at": "2026-05-13 11:00:00+00:00",
    }
    session = _mock_session_returning([card_row, extraction_row])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/documents/card-002/extraction")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == "ext-001"
    assert data["card_id"] == "card-002"
    assert data["extracted_data"] == {"floors": 5}
    assert data["field_confidences"] == {"floors": 0.95}


# ---------------------------------------------------------------------------
# Test 4 — PATCH /{card_id}/extraction updates human corrections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_extraction_updates_corrections():
    """PATCH /extraction merges field_corrections and returns 200."""
    card_row = {"extraction_id": "ext-002"}
    extraction_row = {
        "id": "ext-002",
        "card_id": "card-003",
        "model_version": "claude-haiku-4-5",
        "extracted_data": {"floors": 3},
        "field_confidences": {"floors": 0.80},
        "vulnerabilities": None,
        "extraction_cost_usd": None,
        "duration_ms": None,
        "human_corrections": None,
        "created_at": "2026-05-13 12:00:00+00:00",
    }

    # PATCH endpoint calls execute 4 times:
    # 1. SELECT extraction_id FROM operational_cards
    # 2. SELECT extraction row
    # 3. UPDATE card_extractions (returns None result — not read)
    # 4. INSERT audit_log (returns None result — not read)
    execute_results = [card_row, extraction_row, None, None]
    session = _mock_session_returning(execute_results)

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.patch(
        "/api/v2/documents/card-003/extraction",
        json={
            "field_corrections": {"floors": 4, "wall_material": "brick"},
            "reviewer_id": "user-analyst-1",
            "notes": "Corrected floor count from plan",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == "ext-002"
    # human_corrections should contain the merged corrections
    assert data["human_corrections"]["floors"] == 4
    assert data["human_corrections"]["wall_material"] == "brick"


# ---------------------------------------------------------------------------
# Test 5 — DELETE /{card_id} soft-deletes and returns 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_sets_status_deleted():
    """DELETE /{card_id} performs soft delete and returns 204 No Content."""
    card_row = {"id": "card-004", "file_url": "documents/user/card-004/original.pdf"}

    # DELETE endpoint calls execute 3 times:
    # 1. SELECT id, file_url FROM operational_cards
    # 2. UPDATE status='deleted'
    # 3. INSERT audit_log
    execute_results = [card_row, None, None]
    session = _mock_session_returning(execute_results)

    async def _fake_db():
        yield session

    # Mock get_storage so it doesn't try to hit the filesystem
    from unittest.mock import patch, AsyncMock as AM

    mock_storage = MagicMock()
    mock_storage.delete = AM(return_value=None)

    app = _make_app(db_override=_fake_db)

    with patch("routers.v2.documents.get_storage", return_value=mock_storage):
        client = TestClient(app)
        response = client.delete("/api/v2/documents/card-004")

    assert response.status_code == 204
    assert response.content == b""
