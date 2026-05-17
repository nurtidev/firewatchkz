"""
Unit tests for import_osm_buildings pure functions.
No real Overpass or database calls — all mocked.
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.import_osm_buildings import _split_bbox, _dto_to_row, _map_osm_type
from services.providers.base import BBox, BuildingDTO


# ---------------------------------------------------------------------------
# 1. _split_bbox
# ---------------------------------------------------------------------------

def test_split_bbox_gives_correct_count():
    """_split_bbox(bbox, 2, 3) must return exactly 6 sub-bboxes."""
    bbox = BBox(min_lat=51.05, min_lon=71.30, max_lat=51.30, max_lon=71.60)
    chunks = _split_bbox(bbox, rows=2, cols=3)
    assert len(chunks) == 6


def test_split_bbox_covers_full_area():
    """All sub-bboxes together should span the original bbox exactly."""
    bbox = BBox(min_lat=51.0, min_lon=71.0, max_lat=52.0, max_lon=72.0)
    chunks = _split_bbox(bbox, rows=2, cols=2)

    # The union of latitudes and longitudes must span the original range
    assert min(c.min_lat for c in chunks) == pytest.approx(bbox.min_lat)
    assert max(c.max_lat for c in chunks) == pytest.approx(bbox.max_lat)
    assert min(c.min_lon for c in chunks) == pytest.approx(bbox.min_lon)
    assert max(c.max_lon for c in chunks) == pytest.approx(bbox.max_lon)


# ---------------------------------------------------------------------------
# 2. _dto_to_row — OSM type mapping via _dto_to_row
# ---------------------------------------------------------------------------

def _make_dto(building_type: str) -> BuildingDTO:
    return BuildingDTO(
        external_id="osm-1",
        source="osm",
        address="Test St 1",
        address_norm="test st 1",
        city_id="astana",
        lat=51.18,
        lon=71.44,
        geom_wkt="POLYGON((71.44 51.18, 71.45 51.18, 71.45 51.19, 71.44 51.19, 71.44 51.18))",
        centroid_wkt="POINT(71.445 51.185)",
        building_type=building_type,
        floors_above=5,
        floors_below=None,
        height_m=15.0,
        total_area_sqm=None,
        year_built=None,
        wall_material=None,
        fire_resistance=None,
        fire_hazard_class=None,
    )


def test_dto_to_row_maps_osm_type():
    """
    apartments -> residential, warehouse -> industrial, yes -> None
    """
    assert _dto_to_row(_make_dto("apartments"), "astana")["building_type"] == "residential"
    assert _dto_to_row(_make_dto("warehouse"), "astana")["building_type"] == "industrial"
    assert _dto_to_row(_make_dto("yes"), "astana")["building_type"] is None


def test_dto_to_row_preserves_city_id():
    row = _dto_to_row(_make_dto("residential"), "astana")
    assert row["city_id"] == "astana"
    assert row["source"] == "osm"
    assert row["external_id"] == "osm-1"


def test_dto_to_row_normalizes_address():
    dto = _make_dto("residential")
    row = _dto_to_row(dto, "astana")
    assert row["address_norm"] == dto.address.lower().strip()


# ---------------------------------------------------------------------------
# 3. _map_osm_type — unknown input returns None
# ---------------------------------------------------------------------------

def test_map_osm_type_unknown_returns_none():
    """Any unrecognised OSM building tag should map to None."""
    assert _map_osm_type("some_unknown_type") is None


def test_map_osm_type_none_input():
    assert _map_osm_type(None) is None


def test_map_osm_type_case_insensitive():
    assert _map_osm_type("Apartments") == "residential"
    assert _map_osm_type("HOSPITAL") == "medical"


