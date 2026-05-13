import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.providers.base import BBox, BuildingDTO, get_provider


def test_bbox_to_overpass():
    bbox = BBox(min_lat=51.0, min_lon=71.0, max_lat=51.5, max_lon=72.0)
    assert bbox.to_overpass() == "51.0,71.0,51.5,72.0"


def test_bbox_to_wkt():
    bbox = BBox(min_lat=51.0, min_lon=71.0, max_lat=51.5, max_lon=72.0)
    wkt = bbox.to_wkt_polygon()
    assert "POLYGON" in wkt
    assert "71.0 51.0" in wkt


def test_get_provider_osm(monkeypatch):
    monkeypatch.setenv("BUILDINGS_PROVIDER", "osm")
    provider = get_provider()
    assert provider.source_name() == "osm"


def test_get_provider_unknown():
    with pytest.raises(ValueError):
        get_provider("unknown_provider")


def test_twogis_raises():
    import asyncio
    from services.providers.twogis_provider import TwoGISProvider
    p = TwoGISProvider()
    bbox = BBox(51.0, 71.0, 51.5, 72.0)
    with pytest.raises(NotImplementedError):
        asyncio.run(p.fetch_buildings("astana", bbox))


@pytest.mark.asyncio
async def test_osm_provider_parses_response(monkeypatch):
    """Test OSM provider with mocked HTTP response."""
    mock_response = {
        "elements": [
            {
                "type": "way",
                "id": 123456,
                "tags": {
                    "building": "apartments",
                    "addr:street": "Туран",
                    "addr:housenumber": "10",
                    "building:levels": "5",
                    "height": "15.0",
                },
                "geometry": [
                    {"lat": 51.18, "lon": 71.44},
                    {"lat": 51.181, "lon": 71.44},
                    {"lat": 51.181, "lon": 71.441},
                    {"lat": 51.18, "lon": 71.441},
                    {"lat": 51.18, "lon": 71.44},
                ],
            }
        ]
    }

    from services.providers.osm_provider import OSMProvider

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        provider = OSMProvider()
        bbox = BBox(51.0, 71.0, 51.5, 72.0)
        buildings = await provider.fetch_buildings("astana", bbox)

    assert len(buildings) == 1
    b = buildings[0]
    assert b.external_id == "123456"
    assert b.source == "osm"
    assert b.building_type == "residential"
    assert b.floors_above == 5
    assert b.height_m == 15.0
    assert "Туран" in b.address
    assert b.geom_wkt is not None
    assert b.centroid_wkt is not None
