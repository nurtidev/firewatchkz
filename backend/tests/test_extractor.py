"""Tests for backend/services/extraction — schema validation and extractor logic.

All tests are fully mocked; no real Anthropic API calls are made.
"""
from __future__ import annotations

import math
import types
from unittest.mock import MagicMock, patch

import pytest

from services.extraction.schema import (
    ExtractionResult,
    FieldWithConfidence,
    FireSafetySystem,
    Hydrant,
    OperationalCardExtraction,
    Vulnerability,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_field(value=None, confidence: float = 0.9, source_page: int = None) -> dict:
    """Build a raw dict for FieldWithConfidence."""
    return {"value": value, "confidence": confidence, "source_page": source_page}


def _full_extraction_data() -> dict:
    """Return a dict with all required fields populated."""
    field = _make_field
    return {
        "card_number": field("КА-2024-001"),
        "approved_date": field("2024-01-15"),
        "revision_date": field("2024-06-01"),
        "building_name": field("ТРЦ Мега Астана"),
        "address": field("ул. Кабанбай батыра, 62, Астана"),
        "city": field("Астана"),
        "hazard_class": field("Ф3.2"),
        "floors_above": field(4),
        "floors_below": field(1),
        "total_area_sqm": field(42000.0),
        "height_m": field(22.5),
        "year_built": field(2010),
        "wall_material": field("concrete"),
        "fire_resistance_degree": field("II"),
        "fire_safety": {
            "alarm_type": "automatic",
            "sprinkler_present": True,
            "sprinkler_coverage_pct": 100.0,
            "smoke_extraction": True,
            "evacuation_exits": 8,
            "emergency_lighting": True,
        },
        "fire_safety_confidence": 0.95,
        "hydrants": [
            {"distance_m": 50.0, "address": "ул. Кабанбай батыра, 60", "type": "underground"},
            {"distance_m": 120.0, "address": "пр. Достык, 1", "type": "pillar"},
        ],
        "max_occupancy": field(5000),
        "has_gas_systems": field(False),
        "has_hazardous_materials": field(False),
        "hazardous_materials_description": field(None, confidence=0.0),
        "overall_confidence": 0.92,
        "missing_fields": [],
        "extraction_notes": None,
    }


# ---------------------------------------------------------------------------
# Test 1: full extraction validates without errors
# ---------------------------------------------------------------------------

def test_schema_validates_full_extraction():
    """A complete OperationalCardExtraction with all fields must validate cleanly."""
    data = _full_extraction_data()
    extraction = OperationalCardExtraction(**data)

    assert extraction.card_number.value == "КА-2024-001"
    assert extraction.card_number.confidence == 0.9
    assert extraction.building_name.value == "ТРЦ Мега Астана"
    assert extraction.fire_safety.alarm_type == "automatic"
    assert extraction.fire_safety.sprinkler_present is True
    assert len(extraction.hydrants) == 2
    assert extraction.hydrants[0].distance_m == 50.0
    assert extraction.hydrants[1].type == "pillar"
    assert extraction.overall_confidence == 0.92
    assert extraction.missing_fields == []
    # ExtractionResult wrapper
    result = ExtractionResult(
        extraction=extraction,
        input_tokens=1000,
        output_tokens=200,
        cost_usd=0.006,
        pages_processed=3,
    )
    assert result.pages_processed == 3


# ---------------------------------------------------------------------------
# Test 2: minimal extraction (only required fields)
# ---------------------------------------------------------------------------

def test_schema_missing_optional_fields():
    """OperationalCardExtraction with minimal required fields and all optionals absent."""
    field = _make_field
    minimal = {
        "card_number": field(None, confidence=0.0),
        "approved_date": field(None, confidence=0.0),
        "revision_date": field(None, confidence=0.0),
        "building_name": field("Объект без данных"),
        "address": field(None, confidence=0.0),
        "city": field(None, confidence=0.0),
        "hazard_class": field(None, confidence=0.0),
        "floors_above": field(None, confidence=0.0),
        "floors_below": field(None, confidence=0.0),
        "total_area_sqm": field(None, confidence=0.0),
        "height_m": field(None, confidence=0.0),
        "year_built": field(None, confidence=0.0),
        "wall_material": field(None, confidence=0.0),
        "fire_resistance_degree": field(None, confidence=0.0),
        "fire_safety": {},          # FireSafetySystem with all None
        "fire_safety_confidence": 0.0,
        "hydrants": [],
        "max_occupancy": field(None, confidence=0.0),
        "has_gas_systems": field(None, confidence=0.0),
        "has_hazardous_materials": field(None, confidence=0.0),
        "hazardous_materials_description": field(None, confidence=0.0),
        "overall_confidence": 0.1,
        "missing_fields": [
            "card_number", "approved_date", "revision_date",
            "address", "city", "hazard_class",
        ],
        # extraction_notes is Optional — omitted
    }
    extraction = OperationalCardExtraction(**minimal)

    assert extraction.building_name.value == "Объект без данных"
    assert extraction.fire_safety.alarm_type is None
    assert extraction.fire_safety.sprinkler_present is None
    assert extraction.hydrants == []
    assert len(extraction.missing_fields) == 6
    assert extraction.extraction_notes is None
    assert extraction.overall_confidence == 0.1


# ---------------------------------------------------------------------------
# Test 3: extractor parses a mocked tool_use response correctly
# ---------------------------------------------------------------------------

def test_extractor_parses_tool_use_response():
    """
    Mock client.messages.create to return a tool_use block and verify
    DocumentExtractor returns a correctly populated ExtractionResult.
    """
    import asyncio

    # Build a fake tool_use block (like the real Anthropic SDK returns)
    tool_input = _full_extraction_data()

    fake_tool_block = MagicMock()
    fake_tool_block.type = "tool_use"
    fake_tool_block.input = tool_input

    fake_usage = MagicMock()
    fake_usage.input_tokens = 800
    fake_usage.output_tokens = 150

    fake_response = MagicMock()
    fake_response.content = [fake_tool_block]
    fake_response.usage = fake_usage

    # Patch anthropic.Anthropic so no real client is created
    mock_anthropic_module = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = fake_response
    mock_anthropic_module.Anthropic.return_value = mock_client_instance

    with patch.dict("sys.modules", {"anthropic": mock_anthropic_module}):
        # Import after patching so the constructor picks up the mock
        import importlib
        import sys

        # Remove cached module if present
        for key in list(sys.modules.keys()):
            if "services.extraction.extractor" in key:
                del sys.modules[key]

        from services.extraction.extractor import DocumentExtractor

        extractor = DocumentExtractor()

        async def run():
            # Provide a single-pixel JPEG-like bytes blob (content not validated by mock)
            fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG header
            return await extractor.extract_from_image_bytes(
                image_bytes=fake_jpeg,
                mime_type="image/jpeg",
                card_id="test-card-001",
            )

        result = asyncio.get_event_loop().run_until_complete(run())

    assert isinstance(result, ExtractionResult)
    assert result.input_tokens == 800
    assert result.output_tokens == 150
    assert result.pages_processed == 1
    assert result.extraction.building_name.value == "ТРЦ Мега Астана"
    assert result.extraction.overall_confidence == 0.92


# ---------------------------------------------------------------------------
# Test 4: cost calculation
# ---------------------------------------------------------------------------

def test_cost_calculation():
    """
    1 000 input tokens at $3/MTok + 200 output tokens at $15/MTok
    = 0.003 + 0.003 = 0.006 USD.
    """
    from services.extraction.extractor import DocumentExtractor

    input_tokens = 1000
    output_tokens = 200

    # Calculate directly using the class constants (no API call needed)
    cost = (
        input_tokens * DocumentExtractor.COST_PER_INPUT_TOKEN
        + output_tokens * DocumentExtractor.COST_PER_OUTPUT_TOKEN
    )

    expected = 0.003 + 0.003  # = 0.006
    assert math.isclose(cost, expected, rel_tol=1e-9), f"Expected {expected}, got {cost}"
    assert math.isclose(cost, 0.006, rel_tol=1e-9)
