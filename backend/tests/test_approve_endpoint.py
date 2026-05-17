"""
tests/test_approve_endpoint.py — Unit tests for F-8 POST /{card_id}/approve.

Tests cover:
  1. Successful approval that creates/updates a building record.
  2. 404 when the card does not exist.
  3. 422 when the card exists but has no linked extraction.

All DB calls are mocked — no live network or DB needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_documents_crud.py)
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
    depending on call order.

    Each entry in rows_by_call is either:
    - A dict/MagicMock     → used for .mappings().first() / .mappings().all()
    - A scalar value       → used for .scalar_one()
    - None                 → no-op result (UPDATE/INSERT without RETURNING)
    """
    call_index = {"i": 0}
    results = list(rows_by_call)

    async def _execute(*args, **kwargs):
        value = results[call_index["i"]]
        call_index["i"] += 1

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = value
        mock_result.mappings.return_value.all.return_value = [value] if value else []
        # scalar_one() is used by the UPSERT RETURNING id statement
        mock_result.scalar_one.return_value = value if isinstance(value, str) else None
        return mock_result

    session = AsyncMock()
    session.execute = _execute
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Fixtures — a minimal extracted_data dict matching FieldWithConfidence shape
# ---------------------------------------------------------------------------

SAMPLE_EXTRACTED_DATA = {
    "address": {"value": "ул. Достык 1, Астана", "confidence": 0.92},
    "hazard_class": {"value": "Ф1", "confidence": 0.88},
    "floors_above": {"value": 9, "confidence": 0.95},
    "floors_below": {"value": 1, "confidence": 0.80},
    "height_m": {"value": 28.5, "confidence": 0.85},
    "total_area_sqm": {"value": 5400.0, "confidence": 0.90},
    "year_built": {"value": 2005, "confidence": 0.75},
    "wall_material": {"value": "concrete", "confidence": 0.87},
    "fire_resistance_degree": {"value": "II", "confidence": 0.82},
    "city": {"value": "Астана", "confidence": 0.99},
    "card_number": {"value": "КП-2024-001", "confidence": 0.95},
    "approved_date": {"value": None, "confidence": 0.0},
    "revision_date": {"value": None, "confidence": 0.0},
    "building_name": {"value": "Жилой дом №1", "confidence": 0.88},
}


# ---------------------------------------------------------------------------
# Test 1 — Successful approval creates building and returns building_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_creates_building():
    """POST /approve returns {card_id, building_id, status='approved'} on success."""
    card_row = {
        "id": "card-approve-001",
        "status": "review",
        "extraction_id": "ext-approve-001",
        "file_name": "test_card.pdf",
    }
    extraction_row = {
        "id": "ext-approve-001",
        "extracted_data": SAMPLE_EXTRACTED_DATA,
    }
    # City lookup by name returns astana
    city_row = {"id": "astana"}
    # UPSERT RETURNING id — the scalar_one() value
    building_id_str = "bld-uuid-001"

    # Call sequence for approve endpoint:
    # 1. SELECT card             → card_row
    # 2. SELECT extraction       → extraction_row
    # 3. SELECT cities (lookup)  → city_row
    # 4. INSERT ... RETURNING id → building_id_str  (scalar_one)
    # 5. UPDATE operational_cards → None
    # 6. INSERT audit_log        → None
    execute_results = [card_row, extraction_row, city_row, building_id_str, None, None]
    session = _mock_session_returning(execute_results)

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.post(
        "/api/v2/documents/card-approve-001/approve",
        json={"approved_by": "user-analyst-1"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["card_id"] == "card-approve-001"
    assert data["building_id"] == building_id_str
    assert data["status"] == "approved"


# ---------------------------------------------------------------------------
# Test 2 — 404 when card does not exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_card_not_found():
    """POST /approve returns 404 when the card_id does not exist in DB."""
    # First execute (SELECT card) returns None
    session = _mock_session_returning([None])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.post(
        "/api/v2/documents/nonexistent-card/approve",
        json={},
    )

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


# ---------------------------------------------------------------------------
# Test 3 — 422 when card exists but has no extraction_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_no_extraction():
    """POST /approve returns 422 when the card has no linked extraction."""
    card_row = {
        "id": "card-approve-002",
        "status": "uploaded",
        "extraction_id": None,  # no extraction yet
        "file_name": "pending_card.pdf",
    }
    session = _mock_session_returning([card_row])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.post(
        "/api/v2/documents/card-approve-002/approve",
        json={},
    )

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
