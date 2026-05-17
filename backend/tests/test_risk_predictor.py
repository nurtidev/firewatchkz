"""
tests/test_risk_predictor.py — Unit tests for H-6: RiskPredictor, workers/risk.py,
and /api/v2/buildings endpoints.

All tests run without a live DB or a real model file.
shap/xgboost are mocked so tests run even when those libs are installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_FEATURE_ROW: Dict[str, Any] = {
    "nearest_hydrant_m": 300.0,
    "nearest_station_m": 2000.0,
    "incidents_500m_3y": 5,
    "incidents_on_building_3y": 1,
    "building_density_500m": 20,
    "age_years": 40,
    "population_estimate": 150.0,
    "days_since_last_incident": 400,
    "days_since_last_inspection": 200,
    "building_type": "residential",
}


def _make_mock_model():
    """Return a mock XGBoost model that predicts 0.5."""
    import numpy as np  # noqa: PLC0415

    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([0.5])
    return mock_model


def _make_mock_preprocessor():
    """Return a mock sklearn preprocessor."""
    import numpy as np  # noqa: PLC0415

    mock_prep = MagicMock()
    mock_prep.transform.return_value = np.zeros((1, 12))
    mock_prep.named_transformers_ = {
        "cat": {
            "ohe": MagicMock(
                get_feature_names_out=MagicMock(
                    return_value=["building_type_residential", "building_type_commercial"]
                )
            )
        }
    }
    return mock_prep


def _make_mock_payload():
    return {
        "model": _make_mock_model(),
        "preprocessor": _make_mock_preprocessor(),
        "feature_cols": [
            "nearest_hydrant_m",
            "nearest_station_m",
            "incidents_500m_3y",
            "incidents_on_building_3y",
            "building_density_500m",
            "age_years",
            "population_estimate",
            "days_since_last_incident",
            "days_since_last_inspection",
        ],
    }


# ---------------------------------------------------------------------------
# 1. test_risk_predictor_returns_float_for_feature_row
# ---------------------------------------------------------------------------


class TestRiskPredictorPredict:
    def test_returns_float_for_feature_row(self, tmp_path: Path):
        """predict() returns a float when model is present."""
        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "fake_latest.pkl")

        # Inject payload directly so no file load is needed
        predictor._payload = _make_mock_payload()

        result = predictor.predict(SAMPLE_FEATURE_ROW)
        assert isinstance(result, float), f"Expected float, got {type(result)}"
        assert result == pytest.approx(0.5)

    def test_predict_calls_preprocessor_and_model(self, tmp_path: Path):
        """predict() must call preprocessor.transform then model.predict."""
        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "fake_latest.pkl")
        payload = _make_mock_payload()
        predictor._payload = payload

        predictor.predict(SAMPLE_FEATURE_ROW)

        payload["preprocessor"].transform.assert_called_once()
        payload["model"].predict.assert_called_once()


# ---------------------------------------------------------------------------
# 2. test_risk_predictor_explain_returns_top5
# ---------------------------------------------------------------------------


class TestRiskPredictorExplain:
    def test_explain_returns_top5(self, tmp_path: Path):
        """explain() returns a list of 5 dicts with required keys."""
        import numpy as np  # noqa: PLC0415

        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "fake_latest.pkl")
        predictor._payload = _make_mock_payload()

        # Mock shap values: 12 features, 1 row
        shap_vals = np.array([[0.1, -0.5, 0.3, 0.8, -0.2, 0.05, 0.4, -0.1, 0.15, 0.01, 0.02, -0.03]])

        mock_explainer = MagicMock()
        mock_explainer.shap_values.return_value = shap_vals
        predictor._explainer = mock_explainer

        # Patch shap to be importable
        with patch.dict("sys.modules", {"shap": MagicMock(TreeExplainer=MagicMock(return_value=mock_explainer))}):
            result = predictor.explain(SAMPLE_FEATURE_ROW)

        assert isinstance(result, list)
        assert len(result) == 5, f"Expected 5 factors, got {len(result)}"
        for item in result:
            assert "feature" in item, f"Missing 'feature' key in {item}"
            assert "value" in item, f"Missing 'value' key in {item}"
            assert "shap_value" in item, f"Missing 'shap_value' key in {item}"

    def test_explain_sorted_by_abs_shap(self, tmp_path: Path):
        """explain() returns factors sorted by |shap_value| descending."""
        import numpy as np  # noqa: PLC0415

        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "fake_latest.pkl")
        predictor._payload = _make_mock_payload()

        # Distinct absolute values so sorting is unambiguous
        shap_vals = np.array([[0.01, -0.9, 0.3, 0.5, -0.2, 0.05, 0.4, -0.1, 0.15, 0.001, 0.002, -0.003]])
        mock_explainer = MagicMock()
        mock_explainer.shap_values.return_value = shap_vals
        predictor._explainer = mock_explainer

        with patch.dict("sys.modules", {"shap": MagicMock(TreeExplainer=MagicMock(return_value=mock_explainer))}):
            result = predictor.explain(SAMPLE_FEATURE_ROW)

        abs_shaps = [abs(r["shap_value"]) for r in result]
        assert abs_shaps == sorted(abs_shaps, reverse=True)


# ---------------------------------------------------------------------------
# 3. test_risk_predictor_handles_missing_model
# ---------------------------------------------------------------------------


class TestRiskPredictorMissingModel:
    def test_predict_returns_none_when_file_missing(self, tmp_path: Path):
        """predict() returns None gracefully when pkl not found."""
        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "nonexistent.pkl")
        result = predictor.predict(SAMPLE_FEATURE_ROW)
        assert result is None

    def test_explain_returns_empty_list_when_file_missing(self, tmp_path: Path):
        """explain() returns [] gracefully when pkl not found."""
        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        predictor = RiskPredictor(model_path=tmp_path / "nonexistent.pkl")
        result = predictor.explain(SAMPLE_FEATURE_ROW)
        assert result == []

    def test_singleton_not_contaminated(self, tmp_path: Path):
        """get_instance() returns the same object on repeated calls."""
        from services.risk_predictor import RiskPredictor  # noqa: PLC0415

        # Reset singleton for isolation
        RiskPredictor._instance = None
        inst1 = RiskPredictor.get_instance()
        inst2 = RiskPredictor.get_instance()
        assert inst1 is inst2
        # Cleanup so other tests start fresh
        RiskPredictor._instance = None


# ---------------------------------------------------------------------------
# 4. test_compute_risk_scores_task_registered
# ---------------------------------------------------------------------------


class TestComputeRiskScoresTask:
    def test_task_registered_in_celery(self):
        """compute_risk_scores task must be registered in celery_app."""
        from celery_app import celery_app  # noqa: PLC0415
        import workers.risk  # noqa: F401, PLC0415  (registers the task)

        registered = list(celery_app.tasks.keys())
        assert "workers.risk.compute_risk_scores" in registered, (
            f"Task not found in: {registered}"
        )

    def test_task_is_callable(self):
        """The task object must be callable via .apply() with mocked DB."""
        from workers.risk import compute_risk_scores  # noqa: PLC0415

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        with patch("workers.risk._sync_db_conn", return_value=mock_conn):
            result = compute_risk_scores.apply(args=["astana"])

        assert result.result["city_id"] == "astana"
        assert result.result["buildings_processed"] == 0

    def test_task_beat_schedule_at_0400_utc(self):
        """Beat schedule for risk task must be set at 04:00 UTC."""
        from celery_app import celery_app  # noqa: PLC0415

        schedule = celery_app.conf.beat_schedule
        assert "compute-risk-scores-daily" in schedule, (
            "Beat entry 'compute-risk-scores-daily' not found"
        )
        entry = schedule["compute-risk-scores-daily"]
        assert entry["task"] == "workers.risk.compute_risk_scores"
        sched = entry["schedule"]
        assert sched.hour == {4} or getattr(sched, "_orig_hour", None) in (4, "4"), (
            f"Expected hour=4, got: {sched}"
        )
        assert entry["options"]["queue"] == "risk"


# ---------------------------------------------------------------------------
# 5. test_buildings_endpoint_returns_array
# ---------------------------------------------------------------------------


class TestBuildingsListEndpoint:
    """GET /api/v2/buildings?city=astana must return a JSON array."""

    def _make_app(self):
        from fastapi import FastAPI  # noqa: PLC0415
        from routers.v2 import buildings as v2_buildings  # noqa: PLC0415

        app = FastAPI()
        app.include_router(v2_buildings.router, prefix="/api/v2")
        return app

    def test_returns_array(self):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()

        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {
            "id": "test-user",
            "role": "admin",
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = lambda: mock_session

        client = TestClient(app)
        resp = client.get("/api/v2/buildings", params={"city": "astana"})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_city_param_required(self):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()
        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "u", "role": "admin"}
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        client = TestClient(app)
        resp = client.get("/api/v2/buildings")  # no city param

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 6. test_building_risk_endpoint
# ---------------------------------------------------------------------------


class TestBuildingRiskEndpoint:
    """GET /api/v2/buildings/{id}/risk returns expected keys."""

    def _make_app(self):
        from fastapi import FastAPI  # noqa: PLC0415
        from routers.v2 import buildings as v2_buildings  # noqa: PLC0415

        app = FastAPI()
        app.include_router(v2_buildings.router, prefix="/api/v2")
        return app

    def _mock_risk_row(self):
        row = MagicMock()
        row.__getitem__ = lambda self, key: {
            "baseline_score": 0.3,
            "dynamic_modifier": 1.1,
            "final_score": 0.33,
        }[key]
        row.get = lambda key, default=None: {
            "baseline_score": 0.3,
            "dynamic_modifier": 1.1,
            "final_score": 0.33,
        }.get(key, default)
        # Make it a proper mapping
        from unittest.mock import MagicMock as MM  # noqa: PLC0415

        m = MM()
        m.__getitem__ = lambda s, k: {"baseline_score": 0.3, "dynamic_modifier": 1.1, "final_score": 0.33}[k]
        return m

    def test_returns_expected_keys(self):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()

        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "u", "role": "admin"}

        mock_mapping = MagicMock()
        mock_mapping.__getitem__ = lambda s, k: {
            "baseline_score": 0.3,
            "dynamic_modifier": 1.1,
            "final_score": 0.33,
        }[k]

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_mapping
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = lambda: mock_session

        client = TestClient(app)
        resp = client.get("/api/v2/buildings/bld-001/risk", params={"horizon": 30})

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        expected_keys = {
            "baseline_score",
            "dynamic_modifier",
            "final_score",
            "horizon_days",
            "expected_incidents",
        }
        assert expected_keys <= data.keys(), f"Missing keys: {expected_keys - data.keys()}"

    def test_invalid_horizon_returns_422(self):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()
        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "u", "role": "admin"}
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        client = TestClient(app)
        resp = client.get("/api/v2/buildings/bld-001/risk", params={"horizon": 45})

        assert resp.status_code == 422

    def test_risk_not_found_returns_404(self):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()
        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "u", "role": "admin"}

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_db] = lambda: mock_session

        client = TestClient(app)
        resp = client.get("/api/v2/buildings/no-such-id/risk", params={"horizon": 30})

        assert resp.status_code == 404

    def test_expected_incidents_calculation(self):
        """expected_incidents == final_score * horizon / 365."""
        from fastapi.testclient import TestClient  # noqa: PLC0415

        app = self._make_app()
        from services.auth import require_inspector_or_above  # noqa: PLC0415
        from db.session import get_db  # noqa: PLC0415

        app.dependency_overrides[require_inspector_or_above] = lambda: {"id": "u", "role": "admin"}

        final_score = 1.0
        mock_mapping = MagicMock()
        mock_mapping.__getitem__ = lambda s, k: {
            "baseline_score": 1.0,
            "dynamic_modifier": 1.0,
            "final_score": final_score,
        }[k]

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_mapping
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_db] = lambda: mock_session

        client = TestClient(app)
        resp = client.get("/api/v2/buildings/bld-001/risk", params={"horizon": 90})

        data = resp.json()
        expected = round(final_score * 90 / 365, 6)
        assert data["expected_incidents"] == pytest.approx(expected, rel=1e-5)
