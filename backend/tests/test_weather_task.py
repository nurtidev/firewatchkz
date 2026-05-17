"""
tests/test_weather_task.py — Unit tests for the fetch_weather Celery task (H-3).

All external dependencies (DB, HTTP, h3) are mocked so the tests run
without a live database, API key, or installed optional packages.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: build a mock psycopg connection
# ---------------------------------------------------------------------------


def _make_cursor():
    """Return a context-manager-compatible mock cursor."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_conn():
    """Return a mock psycopg connection."""
    conn = MagicMock()
    conn.cursor.return_value = _make_cursor()
    return conn


# ---------------------------------------------------------------------------
# Sample OWM API response
# ---------------------------------------------------------------------------

_SAMPLE_OWM_RESPONSE = {
    "main": {"temp": 22.5, "humidity": 45},
    "wind": {"speed": 5.2},
    "rain": {"1h": 0.0},
}


# ---------------------------------------------------------------------------
# Test 1: task returns {"skipped": True} when OPENWEATHERMAP_API_KEY not set
# ---------------------------------------------------------------------------


def test_fetch_weather_skips_without_api_key():
    """
    When OPENWEATHERMAP_API_KEY is not set in the environment, the task must
    return {"skipped": True, "reason": "no_api_key"} immediately without
    making any HTTP requests or DB connections.
    """
    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENWEATHERMAP_API_KEY"}

    with (
        patch.dict(os.environ, env_without_key, clear=True),
        patch("workers.weather._fetch_owm_data") as mock_fetch,
        patch("workers.weather._sync_db_conn") as mock_db,
    ):
        from workers.weather import fetch_weather

        result = fetch_weather.apply(args=[]).result

    assert result == {"skipped": True, "reason": "no_api_key"}
    mock_fetch.assert_not_called()
    mock_db.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: happy path — mock HTTP + DB, verify INSERT is called correctly
# ---------------------------------------------------------------------------


def test_fetch_weather_inserts_row():
    """
    When the API key is set, the task must:
    - call _fetch_owm_data (mocked)
    - open a DB connection
    - execute an INSERT into weather_history
    - commit the transaction
    """
    mock_conn = _make_conn()

    with (
        patch.dict(os.environ, {"OPENWEATHERMAP_API_KEY": "test-key-123"}),
        patch("workers.weather._fetch_owm_data", return_value=_SAMPLE_OWM_RESPONSE),
        patch("workers.weather._sync_db_conn", return_value=mock_conn),
    ):
        from workers.weather import fetch_weather

        result = fetch_weather.apply(args=[]).result

    # Should not be skipped or errored
    assert "error" not in result
    assert result.get("skipped") is not True

    # INSERT must have been called
    # __enter__ returns self (the cursor mock), so cursor IS mock_conn.cursor.return_value
    cursor = mock_conn.cursor.return_value
    cursor.execute.assert_called_once()
    sql_called = cursor.execute.call_args[0][0]
    assert "weather_history" in sql_called.lower() or "weather_history" in sql_called
    assert "ON CONFLICT" in sql_called

    # Commit must have been called
    mock_conn.commit.assert_called_once()

    # Result should contain expected keys
    assert "ts" in result
    assert "h3_cell" in result
    assert result["temp_c"] == 22.5
    assert result["wind_ms"] == 5.2
    assert result["humidity_pct"] == 45


# ---------------------------------------------------------------------------
# Test 3: H3 cell is a valid non-empty string for Astana coordinates
# ---------------------------------------------------------------------------


def test_h3_cell_is_valid_string():
    """
    Compute h3 cell for Astana center at resolution 8.
    If h3 is installed, verify it returns a non-empty string.
    If h3 is not installed, skip.
    """
    pytest.importorskip("h3", reason="h3 package not installed")

    from workers.weather import _compute_h3_cell, ASTANA_LAT, ASTANA_LON, H3_RESOLUTION

    cell = _compute_h3_cell(ASTANA_LAT, ASTANA_LON, H3_RESOLUTION)

    assert isinstance(cell, str)
    assert len(cell) > 0
    assert cell != "h3_unavailable"


# ---------------------------------------------------------------------------
# Test 4: fetch_weather task is registered in celery_app
# ---------------------------------------------------------------------------


def test_weather_task_registered():
    """
    After importing workers.weather, the task workers.weather.fetch_weather
    must appear in celery_app.tasks.
    """
    from celery_app import celery_app
    import workers.weather  # noqa: F401 — side-effect: registers the task

    registered = list(celery_app.tasks.keys())
    assert "workers.weather.fetch_weather" in registered


# ---------------------------------------------------------------------------
# Test 5: fallback to "h3_unavailable" when h3 package is missing
# ---------------------------------------------------------------------------


def test_h3_cell_fallback_when_h3_missing():
    """
    When h3 is not importable, _compute_h3_cell must return 'h3_unavailable'
    instead of raising an exception.
    """
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "h3":
            raise ImportError("h3 not installed")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        # Re-import the function to use the patched import
        from workers.weather import _compute_h3_cell

        # Need to reload to pick up the mocked import within the function body
        # Instead, call with a fresh patch scope
        pass

    # Patch h3 at the module level in workers.weather
    with patch.dict("sys.modules", {"h3": None}):
        # Force re-evaluation by patching at call time
        import sys
        # Remove h3 from sys.modules to simulate it being absent
        h3_backup = sys.modules.pop("h3", None)
        try:
            from workers.weather import _compute_h3_cell
            cell = _compute_h3_cell(51.1801, 71.4460, 8)
            assert cell == "h3_unavailable"
        finally:
            if h3_backup is not None:
                sys.modules["h3"] = h3_backup


# ---------------------------------------------------------------------------
# Test 6: task never raises — exceptions are caught and returned as error dict
# ---------------------------------------------------------------------------


def test_fetch_weather_never_raises():
    """
    Even if _fetch_owm_data raises an unexpected exception, the task must
    not propagate it — it must return an error dict instead.
    """
    with (
        patch.dict(os.environ, {"OPENWEATHERMAP_API_KEY": "test-key-456"}),
        patch("workers.weather._fetch_owm_data", side_effect=RuntimeError("network failure")),
        patch("workers.weather._sync_db_conn"),
    ):
        from workers.weather import fetch_weather

        result = fetch_weather.apply(args=[]).result

    assert "error" in result
    assert "network failure" in result["error"]
