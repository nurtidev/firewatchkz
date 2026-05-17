"""
tests/test_inspector.py — Unit tests for H-8 inspector endpoints.

Tests:
  - test_haversine_astana_almaty
  - test_nearest_neighbour_tsp_3_points
  - test_nearest_neighbour_tsp_returns_all_points
  - test_inspector_endpoint_returns_array
  - test_inspector_requires_city
  - test_route_endpoint_empty_ids
  - test_risk_level_classification

All DB calls are mocked — no live network or DB needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from routers.v2.inspector import haversine_km, nearest_neighbour_tsp, classify_risk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db_override=None):
    from fastapi import FastAPI
    from routers.v2.inspector import router
    from db.session import get_db
    from services.auth import require_inspector_or_above

    _stub_user = {"id": "test-user", "role": "inspector", "email": "inspector@test.com"}

    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_inspector_or_above] = lambda: _stub_user
    return app


def _mock_session_returning(rows_by_call):
    """
    Return a mock AsyncSession whose execute() returns successive results.
    Each entry in rows_by_call is either a single dict/None (for .first()) or
    a list of dicts (for .all()).
    """
    call_index = {"i": 0}
    results = list(rows_by_call)

    async def _execute(*args, **kwargs):
        value = results[call_index["i"]]
        call_index["i"] += 1
        mock_result = MagicMock()
        if isinstance(value, list):
            mock_result.mappings.return_value.all.return_value = value
            mock_result.mappings.return_value.first.return_value = value[0] if value else None
        else:
            mock_result.mappings.return_value.first.return_value = value
            mock_result.mappings.return_value.all.return_value = [value] if value else []
        return mock_result

    session = AsyncMock()
    session.execute = _execute
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Pure-function tests (no DB, no HTTP)
# ---------------------------------------------------------------------------


def test_haversine_astana_almaty():
    """Distance between Astana (51.18, 71.45) and Almaty (43.24, 76.89) ≈ 970 km as-the-crow-flies."""
    dist = haversine_km(51.18, 71.45, 43.24, 76.89)
    assert 900 <= dist <= 1100, f"Expected ~970 km straight-line, got {dist:.1f} km"


def test_nearest_neighbour_tsp_3_points():
    """TSP on 3 points returns a valid permutation (all 3 IDs present)."""
    points = [
        {"building_id": "A", "lat": 51.18, "lon": 71.44},
        {"building_id": "B", "lat": 51.20, "lon": 71.46},
        {"building_id": "C", "lat": 51.15, "lon": 71.40},
    ]
    ordered = nearest_neighbour_tsp(points)
    assert len(ordered) == 3
    ids = {p["building_id"] for p in ordered}
    assert ids == {"A", "B", "C"}


def test_nearest_neighbour_tsp_returns_all_points():
    """TSP output contains every input building_id exactly once."""
    points = [
        {"building_id": f"bld-{i}", "lat": 51.0 + i * 0.01, "lon": 71.0 + i * 0.01}
        for i in range(10)
    ]
    ordered = nearest_neighbour_tsp(points)
    assert len(ordered) == 10
    assert {p["building_id"] for p in ordered} == {p["building_id"] for p in points}


def test_risk_level_classification():
    """Thresholds: <0.5 → low, 0.5-1.5 → medium, >1.5 → high."""
    assert classify_risk(0.0) == "low"
    assert classify_risk(0.49) == "low"
    assert classify_risk(0.5) == "medium"
    assert classify_risk(1.0) == "medium"
    assert classify_risk(1.5) == "medium"
    assert classify_risk(1.51) == "high"
    assert classify_risk(3.0) == "high"


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inspector_endpoint_returns_array():
    """GET /api/v2/inspector?city=astana returns a JSON array."""
    fake_rows = [
        {
            "id": "bld-001",
            "address": "ул. Достык 1",
            "building_type": "residential",
            "floors_above": 9,
            "lat": 51.18,
            "lon": 71.44,
            "final_score": 2.5,
            "baseline_score": 1.5,
            "dynamic_modifier": 1.67,
            "shap_values": None,
            "score_date": "2026-05-14",
        },
        {
            "id": "bld-002",
            "address": "пр. Республики 10",
            "building_type": "commercial",
            "floors_above": 5,
            "lat": 51.20,
            "lon": 71.46,
            "final_score": 0.8,
            "baseline_score": 0.6,
            "dynamic_modifier": 1.33,
            "shap_values": None,
            "score_date": "2026-05-14",
        },
    ]
    session = _mock_session_returning([fake_rows])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/inspector?city=astana")

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    first = data[0]
    assert first["building_id"] == "bld-001"
    assert first["risk_level"] == "high"
    assert first["final_score"] == 2.5

    second = data[1]
    assert second["building_id"] == "bld-002"
    assert second["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_inspector_requires_city():
    """GET /api/v2/inspector without city param returns 422."""
    app = _make_app()
    client = TestClient(app)
    response = client.get("/api/v2/inspector")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_route_endpoint_empty_ids():
    """GET /api/v2/inspector/route with building_ids=[] returns 422."""
    app = _make_app()
    client = TestClient(app)
    response = client.get('/api/v2/inspector/route?building_ids=[]')
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_route_endpoint_returns_ordered_route():
    """GET /api/v2/inspector/route returns ordered list and waypoints for known buildings."""
    fake_rows = [
        {"id": "bld-001", "address": "ул. Достык 1",    "lat": 51.18, "lon": 71.44, "final_score": 2.5},
        {"id": "bld-002", "address": "пр. Республики 10", "lat": 51.20, "lon": 71.46, "final_score": 0.8},
        {"id": "bld-003", "address": "ул. Сейфуллина 3",  "lat": 51.15, "lon": 71.40, "final_score": 1.2},
    ]
    session = _mock_session_returning([fake_rows])

    async def _fake_db():
        yield session

    app = _make_app(db_override=_fake_db)
    client = TestClient(app)

    ids_param = json.dumps(["bld-001", "bld-002", "bld-003"])
    response = client.get(f"/api/v2/inspector/route?building_ids={ids_param}")

    assert response.status_code == 200, response.text
    data = response.json()

    assert "ordered_buildings" in data
    assert "total_distance_km" in data
    assert "estimated_time_min" in data
    assert "waypoints" in data

    assert set(data["ordered_buildings"]) == {"bld-001", "bld-002", "bld-003"}
    assert len(data["waypoints"]) == 3
    assert data["total_distance_km"] >= 0
    assert data["estimated_time_min"] >= 0
