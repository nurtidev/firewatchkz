"""
tests/test_extract_task.py — Unit tests for the extract_document Celery task (F-6).

All external dependencies (DB, storage, DocumentExtractor) are mocked so the
tests run without a live database, S3/R2, or Anthropic API key.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.extraction.schema import (
    ExtractionResult,
    FieldWithConfidence,
    FireSafetySystem,
    OperationalCardExtraction,
)


# ---------------------------------------------------------------------------
# Helpers — build realistic fake objects
# ---------------------------------------------------------------------------

def _make_field(value=None, confidence: float = 0.9) -> dict:
    return {"value": value, "confidence": confidence, "source_page": None}


def _make_extraction() -> OperationalCardExtraction:
    """Return a fully-populated OperationalCardExtraction for mock responses."""
    f = _make_field
    return OperationalCardExtraction(
        card_number=f("КА-2024-001"),
        approved_date=f("2024-01-15"),
        revision_date=f("2024-06-01"),
        building_name=f("ТРЦ Мега Астана"),
        address=f("ул. Кабанбай батыра, 62"),
        city=f("Астана"),
        hazard_class=f("Ф3.2"),
        floors_above=f(4),
        floors_below=f(1),
        total_area_sqm=f(42000.0),
        height_m=f(22.5),
        year_built=f(2010),
        wall_material=f("concrete"),
        fire_resistance_degree=f("II"),
        fire_safety={},
        fire_safety_confidence=0.9,
        hydrants=[],
        max_occupancy=f(5000),
        has_gas_systems=f(False),
        has_hazardous_materials=f(False),
        hazardous_materials_description=f(None, confidence=0.0),
        overall_confidence=0.92,
        missing_fields=[],
        extraction_notes=None,
    )


def _make_extraction_result() -> ExtractionResult:
    return ExtractionResult(
        extraction=_make_extraction(),
        input_tokens=800,
        output_tokens=150,
        cost_usd=0.00465,
        pages_processed=2,
    )


def _make_cursor_factory(fetchone_return):
    """
    Return a context-manager-compatible mock cursor whose fetchone() returns
    fetchone_return on the first call and None on subsequent calls (so that
    INSERT … RETURNING is handled naturally if needed).
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_conn(fetchone_return):
    """
    Return a mock psycopg connection whose cursor() context manager yields a
    mock cursor that returns fetchone_return on the first fetchone() call.
    """
    cursor = _make_cursor_factory(fetchone_return)
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ---------------------------------------------------------------------------
# Test 1: happy path
# ---------------------------------------------------------------------------

def test_extract_document_happy_path():
    """
    Given a card with status='ready_for_extraction', extract_document should:
    - download the file
    - call DocumentExtractor
    - insert into card_extractions
    - update operational_cards
    - return dict with card_id, extraction_id, status='extracted', cost_usd
    """
    card_row = (
        "card-abc",           # id
        "file://some/path",   # file_url
        "application/pdf",    # file_mime
        None,                 # converted_key
        "ready_for_extraction",  # status
        None,                 # building_id
    )

    mock_conn = _make_conn(fetchone_return=card_row)
    extraction_result = _make_extraction_result()

    # DocumentExtractor is imported inside the task body from services.extraction.extractor.
    # We patch it at the source module so the task picks up the mock instance.
    mock_extractor_instance = MagicMock()
    mock_extractor_cls = MagicMock(return_value=mock_extractor_instance)
    # extract_from_pdf_bytes returns a coroutine — _run_async is also mocked, so the
    # coroutine object is never awaited; we just need it to be a non-None value.
    mock_extractor_instance.extract_from_pdf_bytes.return_value = object()

    with (
        patch("workers.documents._sync_db_conn", return_value=mock_conn),
        patch("workers.documents._download_file_sync", return_value=b"%PDF-1.4 fake"),
        patch("workers.documents._run_async", return_value=extraction_result),
        patch("services.extraction.extractor.DocumentExtractor", mock_extractor_cls),
    ):
        from workers.documents import extract_document

        result = extract_document.apply(args=["card-abc"]).result

    assert result["card_id"] == "card-abc"
    assert result["status"] == "extracted"
    assert "extraction_id" in result
    assert isinstance(result["extraction_id"], str) and len(result["extraction_id"]) == 36  # UUID
    assert result["cost_usd"] == pytest.approx(0.00465, rel=1e-6)


# ---------------------------------------------------------------------------
# Test 2: wrong status → skip without extraction
# ---------------------------------------------------------------------------

def test_extract_document_skips_wrong_status():
    """
    If the card's status is not 'ready_for_extraction', the task must return
    {"card_id": ..., "status": "skipped"} without touching the extractor.
    """
    card_row = (
        "card-xyz",
        "file://some/path",
        "application/pdf",
        None,
        "uploaded",   # wrong status
        None,
    )

    mock_conn = _make_conn(fetchone_return=card_row)

    with (
        patch("workers.documents._sync_db_conn", return_value=mock_conn),
        patch("workers.documents._download_file_sync") as mock_dl,
        patch("workers.documents._run_async") as mock_run,
    ):
        from workers.documents import extract_document

        result = extract_document.apply(args=["card-xyz"]).result

    assert result == {"card_id": "card-xyz", "status": "skipped"}
    mock_dl.assert_not_called()
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: card not found → not_found
# ---------------------------------------------------------------------------

def test_extract_document_card_not_found():
    """
    If the DB returns no row for the given card_id, the task must return
    {"card_id": ..., "status": "not_found"} without any further processing.
    """
    mock_conn = _make_conn(fetchone_return=None)

    with (
        patch("workers.documents._sync_db_conn", return_value=mock_conn),
        patch("workers.documents._download_file_sync") as mock_dl,
        patch("workers.documents._run_async") as mock_run,
    ):
        from workers.documents import extract_document

        result = extract_document.apply(args=["nonexistent-card"]).result

    assert result == {"card_id": "nonexistent-card", "status": "not_found"}
    mock_dl.assert_not_called()
    mock_run.assert_not_called()
