import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import AsyncMock, patch, MagicMock


def make_mock_session(rows):
    """Helper: returns a mock AsyncSessionLocal context that yields rows."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows
    mock_result.mappings.return_value.first.return_value = rows[0] if rows else None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


def test_get_data_loader_v2_singleton():
    from services.data_loader_v2 import get_data_loader_v2, DataLoaderV2
    loader1 = get_data_loader_v2()
    loader2 = get_data_loader_v2()
    assert loader1 is loader2
    assert isinstance(loader1, DataLoaderV2)


@pytest.mark.asyncio
async def test_get_cities():
    from services.data_loader_v2 import DataLoaderV2
    fake_rows = [{"code": "astana", "name": "Астана", "lat": 51.18, "lon": 71.45, "zoom": 12}]
    mock_session = make_mock_session(fake_rows)

    with patch("services.data_loader_v2.AsyncSessionLocal", return_value=mock_session):
        loader = DataLoaderV2()
        cities = await loader.get_cities()

    assert len(cities) == 1
    assert cities[0]["id"] == "astana"
    assert cities[0]["name"] == "Астана"
    assert cities[0]["center"] == [51.18, 71.45]


@pytest.mark.asyncio
async def test_get_hydrants_filters():
    from services.data_loader_v2 import DataLoaderV2
    fake = [{"id": "h1", "city": "astana", "district": "Есіл", "address": "ул.1",
             "status": "working", "lat": 51.18, "lon": 71.44}]
    mock_session = make_mock_session(fake)

    with patch("services.data_loader_v2.AsyncSessionLocal", return_value=mock_session):
        loader = DataLoaderV2()
        result = await loader.get_hydrants(city="astana", status="working")

    assert len(result) == 1
    assert result[0]["status"] == "working"


@pytest.mark.asyncio
async def test_get_building_not_found():
    from services.data_loader_v2 import DataLoaderV2
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("services.data_loader_v2.AsyncSessionLocal", return_value=mock_session):
        loader = DataLoaderV2()
        result = await loader.get_building("nonexistent-id")

    assert result is None
