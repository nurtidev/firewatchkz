"""
tests/test_hydrants_stations.py — Unit tests for H-9 hydrants and fire-stations endpoints (API v2).

Tests (no live DB — dependency_overrides for get_db and auth):
  - test_list_hydrants_returns_array
  - test_list_hydrants_requires_city
  - test_list_hydrants_bbox_filter_accepted
  - test_list_hydrants_invalid_bbox_returns_422
  - test_list_stations_returns_array
  - test_list_stations_requires_city
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_session_returning(rows):
    """Return a mock AsyncSession whose execute() returns a list of row-dicts."""
    async def _execute(*args, **kwargs):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = rows
        mock_result.mappings.return_value.first.return_value = rows[0] if rows else None
        return mock_result

    session = AsyncMock()
    session.execute = _execute
    session.commit = AsyncMock()
    return session


def _make_hydrants_app(db_override=None):
    from fastapi import FastAPI
    from routers.v2.hydrants import router
    from db.session import get_db
    from services.auth import require_inspector_or_above

    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "test", "role": "admin"}
    return app


def _make_stations_app(db_override=None):
    from fastapi import FastAPI
    from routers.v2.fire_stations import router
    from db.session import get_db
    from services.auth import require_inspector_or_above

    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    if db_override:
        app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "test", "role": "admin"}
    return app


# ---------------------------------------------------------------------------
# Hydrant fixtures
# ---------------------------------------------------------------------------

HYDRANT_ROW = {
    "id": "hyd-001",
    "city": "astana",
    "address": "ул. Пушкина 1",
    "status": "working",
    "lat": 51.12,
    "lon": 71.44,
    "capacity_l_s": 10.0,
    "last_check_at": "2025-01-01T00:00:00+00:00",
    "winter_access": True,
}

STATION_ROW = {
    "id": "sta-001",
    "city": "astana",
    "name": "ПЧ №1",
    "address": "пр. Республики 5",
    "lat": 51.15,
    "lon": 71.46,
    "units": 3,
    "staff_count": 24,
}


# ---------------------------------------------------------------------------
# Hydrant tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_hydrants_returns_array():
    """GET /api/v2/hydrants?city=astana returns a JSON array."""
    session = _mock_session_returning([HYDRANT_ROW])

    async def _fake_db():
        yield session

    app = _make_hydrants_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/hydrants?city=astana")

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "hyd-001"
    assert data[0]["city"] == "astana"
    assert data[0]["status"] == "working"


@pytest.mark.asyncio
async def test_list_hydrants_requires_city():
    """GET /api/v2/hydrants without city param returns 422."""
    session = _mock_session_returning([])

    async def _fake_db():
        yield session

    app = _make_hydrants_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/hydrants")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_hydrants_bbox_filter_accepted():
    """GET /api/v2/hydrants with valid bbox returns 200."""
    session = _mock_session_returning([HYDRANT_ROW])

    async def _fake_db():
        yield session

    app = _make_hydrants_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get(
        "/api/v2/hydrants?city=astana&bbox=71.0,51.0,72.0,52.0"
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_hydrants_invalid_bbox_returns_422():
    """GET /api/v2/hydrants with malformed bbox returns 422."""
    session = _mock_session_returning([])

    async def _fake_db():
        yield session

    app = _make_hydrants_app(db_override=_fake_db)
    client = TestClient(app)

    # Only 3 values instead of 4
    response = client.get("/api/v2/hydrants?city=astana&bbox=71.0,51.0,72.0")
    assert response.status_code == 422, response.text

    # Non-numeric value
    response2 = client.get("/api/v2/hydrants?city=astana&bbox=71.0,51.0,abc,52.0")
    assert response2.status_code == 422, response2.text


# ---------------------------------------------------------------------------
# Fire station tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_stations_returns_array():
    """GET /api/v2/fire-stations?city=astana returns a JSON array."""
    session = _mock_session_returning([STATION_ROW])

    async def _fake_db():
        yield session

    app = _make_stations_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/fire-stations?city=astana")

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "sta-001"
    assert data[0]["name"] == "ПЧ №1"
    assert data[0]["units"] == 3
    assert data[0]["staff_count"] == 24


@pytest.mark.asyncio
async def test_list_stations_requires_city():
    """GET /api/v2/fire-stations without city param returns 422."""
    session = _mock_session_returning([])

    async def _fake_db():
        yield session

    app = _make_stations_app(db_override=_fake_db)
    client = TestClient(app)
    response = client.get("/api/v2/fire-stations")

    assert response.status_code == 422
