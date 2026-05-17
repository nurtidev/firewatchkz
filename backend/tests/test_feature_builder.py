"""
tests/test_feature_builder.py — Unit tests for FeatureBuilder and rebuild_features task (H-4).

All DB interactions are mocked so the tests run without a live database.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# FeatureBuilder — pure-Python unit tests (no DB)
# ---------------------------------------------------------------------------


class TestPopulationEstimate:
    def test_population_estimate_none_on_missing_data(self):
        """None inputs must return None."""
        from services.feature_builder import FeatureBuilder

        assert FeatureBuilder.compute_population_estimate(None, None) is None
        assert FeatureBuilder.compute_population_estimate(5, None) is None
        assert FeatureBuilder.compute_population_estimate(None, 1000) is None

    def test_population_estimate_basic(self):
        """floors=5, area=1000 → 5*1000*0.05 = 250."""
        from services.feature_builder import FeatureBuilder

        result = FeatureBuilder.compute_population_estimate(5, 1000)
        assert result == 250.0

    def test_population_estimate_zero_floors(self):
        """Zero floors → 0 population."""
        from services.feature_builder import FeatureBuilder

        result = FeatureBuilder.compute_population_estimate(0, 1000)
        assert result == 0.0

    def test_population_estimate_rounding(self):
        """Result should be rounded to 0 decimal places."""
        from services.feature_builder import FeatureBuilder

        result = FeatureBuilder.compute_population_estimate(3, 100)
        # 3 * 100 * 0.05 = 15.0 — exact, but verify it's a float rounded to 0dp
        assert result == 15.0
        assert isinstance(result, float)


class TestAgeYears:
    def test_age_years_computed(self):
        """year_built=2000 → approximately 25-26 years (within ±2 of current year)."""
        from services.feature_builder import FeatureBuilder

        result = FeatureBuilder.compute_age_years(2000)
        expected = datetime.datetime.now().year - 2000
        assert result is not None
        assert abs(result - expected) <= 2

    def test_age_years_none_on_null(self):
        """None year_built → None."""
        from services.feature_builder import FeatureBuilder

        assert FeatureBuilder.compute_age_years(None) is None

    def test_age_years_recent_building(self):
        """A building built this year should have age 0."""
        from services.feature_builder import FeatureBuilder

        current_year = datetime.datetime.now().year
        result = FeatureBuilder.compute_age_years(current_year)
        assert result == 0


# ---------------------------------------------------------------------------
# rebuild_features task — registry + mocked-DB tests
# ---------------------------------------------------------------------------


def _make_cursor(fetchone_return=None, fetchall_return=None):
    """Build a context-manager-compatible mock cursor."""
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    cursor.fetchall.return_value = fetchall_return or []
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_conn_with_empty_buildings():
    """
    Return a mock psycopg connection that answers the buildings SELECT with an
    empty list (so the task exits early without iterating).
    """
    # The task calls conn.cursor() once for the buildings SELECT (fetchall → []),
    # so we just need fetchall to return [].
    buildings_cursor = _make_cursor(fetchall_return=[])
    conn = MagicMock()
    conn.cursor.return_value = buildings_cursor
    return conn


class TestRebuildFeaturesTask:
    def test_rebuild_features_task_registered(self):
        """Task must appear in Celery's task registry after import."""
        import workers.features  # noqa: F401 — ensures registration

        from celery_app import celery_app

        assert "workers.features.rebuild_features" in celery_app.tasks

    def test_rebuild_features_returns_dict(self):
        """
        apply() with a mocked DB (no buildings) must return a dict with keys
        city_id, buildings_processed, feature_date.
        """
        mock_conn = _make_conn_with_empty_buildings()

        with patch("workers.features._sync_db_conn", return_value=mock_conn):
            from workers.features import rebuild_features

            result = rebuild_features.apply(args=["city-test-001"]).result

        assert isinstance(result, dict), "Result must be a dict"
        assert "city_id" in result
        assert "buildings_processed" in result
        assert "feature_date" in result

    def test_rebuild_features_city_id_echoed(self):
        """city_id passed to the task must appear in the result."""
        mock_conn = _make_conn_with_empty_buildings()

        with patch("workers.features._sync_db_conn", return_value=mock_conn):
            from workers.features import rebuild_features

            result = rebuild_features.apply(args=["astana"]).result

        assert result["city_id"] == "astana"

    def test_rebuild_features_zero_buildings(self):
        """No buildings in DB → buildings_processed == 0."""
        mock_conn = _make_conn_with_empty_buildings()

        with patch("workers.features._sync_db_conn", return_value=mock_conn):
            from workers.features import rebuild_features

            result = rebuild_features.apply(args=["empty-city"]).result

        assert result["buildings_processed"] == 0

    def test_rebuild_features_feature_date_format(self):
        """feature_date must be a valid ISO date string (YYYY-MM-DD)."""
        mock_conn = _make_conn_with_empty_buildings()

        with patch("workers.features._sync_db_conn", return_value=mock_conn):
            from workers.features import rebuild_features

            result = rebuild_features.apply(args=["city-date-check"]).result

        # Will raise ValueError if the format is wrong
        parsed = datetime.date.fromisoformat(result["feature_date"])
        assert parsed == datetime.date.today()

    def test_rebuild_features_route_configured(self):
        """The features queue route must be in celery_app task_routes."""
        from celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert "workers.features.*" in routes
        assert routes["workers.features.*"]["queue"] == "features"

    def test_rebuild_features_beat_schedule_configured(self):
        """rebuild-features-daily beat entry must be present and scheduled at 03:00 UTC."""
        from celery.schedules import crontab

        from celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "rebuild-features-daily" in schedule

        entry = schedule["rebuild-features-daily"]
        assert entry["task"] == "workers.features.rebuild_features"
        assert isinstance(entry["schedule"], crontab)
        # Verify hour=3, minute=0
        assert entry["schedule"].hour == {3}
        assert entry["schedule"].minute == {0}
