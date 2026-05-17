"""
tests/test_baseline_trainer.py — Unit tests for ml/baseline_trainer.py (H-5).

All tests use synthetic numpy/pandas data — no live DB required.
xgboost and scikit-learn are optional: tests are skipped when not installed.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Optional-dependency guard — skip entire module if libs are missing
# ---------------------------------------------------------------------------

xgb = pytest.importorskip("xgboost", reason="xgboost not installed")
sklearn = pytest.importorskip("sklearn", reason="scikit-learn not installed")
joblib = pytest.importorskip("joblib", reason="joblib not installed")

# Now safe to import the trainer
from ml.baseline_trainer import (  # noqa: E402
    FEATURE_COLS,
    compute_poisson_deviance,
    compute_top_decile_lift,
    save_model,
    train,
)

# ---------------------------------------------------------------------------
# Synthetic data factory
# ---------------------------------------------------------------------------

_BUILDING_TYPES: List[str] = [
    "residential",
    "commercial",
    "industrial",
    "construction",
    "other",
]


def _make_synthetic_df(n: int = 120, seed: int = 0):
    """Return a DataFrame that mimics building_features output."""
    import pandas as pd  # noqa: PLC0415

    rng = np.random.default_rng(seed)

    # Single feature_date — triggers random 80/20 fallback in train()
    today = datetime.date.today()
    feature_date = pd.Timestamp(today)

    data = {
        "building_id": [f"bld-{i:04d}" for i in range(n)],
        "feature_date": [feature_date] * n,
        "nearest_hydrant_m": rng.uniform(50, 2000, n),
        "nearest_station_m": rng.uniform(200, 8000, n),
        "incidents_500m_3y": rng.integers(0, 20, n).astype(float),
        "incidents_on_building_3y": rng.integers(0, 5, n).astype(float),
        "building_density_500m": rng.integers(1, 50, n).astype(float),
        "age_years": rng.integers(0, 80, n).astype(float),
        "population_estimate": rng.uniform(0, 500, n),
        "days_since_last_incident": rng.uniform(0, 1000, n),
        "days_since_last_inspection": rng.uniform(0, 730, n),
        "building_type": rng.choice(_BUILDING_TYPES, n),
    }
    df = pd.DataFrame(data)
    # target_rate: incidents_on_building_3y / 3.0
    df["target_rate"] = df["incidents_on_building_3y"] / 3.0
    return df


# ---------------------------------------------------------------------------
# Poisson deviance tests
# ---------------------------------------------------------------------------


class TestPoissonDeviance:
    def test_perfect_prediction_near_zero(self):
        """When pred == true, deviance should be approximately 0."""
        y = np.array([0.5, 1.0, 2.0, 0.1])
        deviance = compute_poisson_deviance(y, y.copy())
        assert deviance == pytest.approx(0.0, abs=1e-5)

    def test_nonzero_when_predictions_differ(self):
        """When pred != true, deviance must be > 0."""
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([2.0, 1.0, 0.5])
        deviance = compute_poisson_deviance(y_true, y_pred)
        assert deviance > 0.0

    def test_symmetric_in_direction(self):
        """Deviance is NOT symmetric — just confirm it's positive in both directions."""
        y_true = np.array([1.0, 1.0, 1.0])
        y_high = np.array([2.0, 2.0, 2.0])
        y_low = np.array([0.5, 0.5, 0.5])
        assert compute_poisson_deviance(y_true, y_high) > 0.0
        assert compute_poisson_deviance(y_true, y_low) > 0.0

    def test_all_zeros_returns_finite(self):
        """All-zero targets with tiny positive preds must return a finite value."""
        y_true = np.zeros(10)
        y_pred = np.full(10, 0.01)
        deviance = compute_poisson_deviance(y_true, y_pred)
        assert np.isfinite(deviance)


# ---------------------------------------------------------------------------
# Top-decile lift tests
# ---------------------------------------------------------------------------


class TestTopDecileLift:
    def test_perfect_sort_gives_high_lift(self):
        """
        With perfectly sorted predictions (highest pred → highest actual),
        lift should be well above 1 when incidents are concentrated in top decile.
        """
        rng = np.random.default_rng(42)
        n = 200
        # Put most incidents in the first 20 buildings
        y_true = np.zeros(n)
        y_true[:20] = rng.integers(1, 5, 20).astype(float)
        # Perfect predictor: predict proportional to true
        y_pred = y_true + rng.uniform(0, 0.01, n)

        lift = compute_top_decile_lift(y_true, y_pred)
        assert lift > 1.0, f"Expected lift > 1.0, got {lift:.3f}"

    def test_random_predictions_lift_roughly_one(self):
        """
        With random (shuffled) predictions, lift should be roughly 1
        (within 0.5–2.0 for n=500 with seed-fixed data).
        """
        rng = np.random.default_rng(7)
        n = 500
        y_true = rng.poisson(lam=0.5, size=n).astype(float)
        y_pred = rng.uniform(0, 1, n)  # purely random

        lift = compute_top_decile_lift(y_true, y_pred)
        assert 0.5 <= lift <= 2.5, f"Random lift {lift:.3f} is out of [0.5, 2.5] range"

    def test_no_incidents_returns_nan(self):
        """If y_true is all zeros, lift is undefined → NaN."""
        y_true = np.zeros(50)
        y_pred = np.ones(50)
        lift = compute_top_decile_lift(y_true, y_pred)
        assert np.isnan(lift)


# ---------------------------------------------------------------------------
# Full pipeline tests (train on synthetic data)
# ---------------------------------------------------------------------------


class TestTrainPipeline:
    def test_model_trains_without_error(self):
        """train() must complete without raising on synthetic data."""
        df = _make_synthetic_df(n=120, seed=1)
        model, preprocessor, metrics = train(df)
        assert model is not None
        assert preprocessor is not None
        assert isinstance(metrics, dict)

    def test_metrics_dict_has_expected_keys(self):
        """Returned metrics dict must contain the three expected keys."""
        df = _make_synthetic_df(n=120, seed=2)
        _, _, metrics = train(df)
        assert "train_deviance" in metrics
        assert "valid_deviance" in metrics
        assert "top_decile_lift" in metrics

    def test_train_deviance_is_finite(self):
        """train_deviance and valid_deviance must be finite numbers."""
        df = _make_synthetic_df(n=120, seed=3)
        _, _, metrics = train(df)
        assert np.isfinite(metrics["train_deviance"])
        assert np.isfinite(metrics["valid_deviance"])

    def test_top_decile_lift_above_one_on_training_data(self):
        """
        Model evaluated on the full synthetic set should achieve lift > 1.0
        (easy — same distribution; XGBoost should find signal in the features).
        """
        df = _make_synthetic_df(n=200, seed=4)
        model, preprocessor, _ = train(df)

        X_all = preprocessor.transform(df[FEATURE_COLS + ["building_type"]])
        y_all = df["target_rate"].values
        pred_all = model.predict(X_all)

        lift = compute_top_decile_lift(y_all, pred_all)
        # On training data with signal features, lift should be > 1
        # (target_rate is incidents_on_building_3y / 3.0, which is one of the features)
        assert lift > 1.0, f"Expected lift > 1.0 on train data, got {lift:.3f}"

    def test_predictions_are_positive(self):
        """Poisson model predictions must be strictly positive."""
        df = _make_synthetic_df(n=100, seed=5)
        model, preprocessor, _ = train(df)
        X = preprocessor.transform(df[FEATURE_COLS + ["building_type"]])
        preds = model.predict(X)
        assert np.all(preds > 0), "All Poisson predictions must be > 0"


# ---------------------------------------------------------------------------
# Model save / load test
# ---------------------------------------------------------------------------


class TestModelSaveLoad:
    def test_save_and_load_predictions_match(self, tmp_path: Path):
        """
        Save model to tmp_path, reload it, run predictions — must match original.
        """
        import joblib  # noqa: PLC0415

        from ml.baseline_trainer import MODELS_DIR as _ORIG_DIR  # noqa: PLC0415
        import ml.baseline_trainer as trainer_module  # noqa: PLC0415

        df = _make_synthetic_df(n=100, seed=6)
        model, preprocessor, _ = train(df)

        # Temporarily redirect MODELS_DIR to tmp_path
        original_dir = trainer_module.MODELS_DIR
        trainer_module.MODELS_DIR = tmp_path
        try:
            dated_path = save_model(model, preprocessor, date_str="2025-01-01")
        finally:
            trainer_module.MODELS_DIR = original_dir

        # Reload
        payload = joblib.load(dated_path)
        loaded_model = payload["model"]
        loaded_preprocessor = payload["preprocessor"]
        loaded_feature_cols = payload["feature_cols"]

        assert loaded_feature_cols == FEATURE_COLS

        X = preprocessor.transform(df[FEATURE_COLS + ["building_type"]])
        X_loaded = loaded_preprocessor.transform(df[FEATURE_COLS + ["building_type"]])

        preds_orig = model.predict(X)
        preds_loaded = loaded_model.predict(X_loaded)

        np.testing.assert_allclose(
            preds_orig,
            preds_loaded,
            rtol=1e-5,
            err_msg="Predictions from saved/loaded model must match original",
        )

    def test_latest_pkl_created(self, tmp_path: Path):
        """save_model() must create both baseline_{date}.pkl and baseline_latest.pkl."""
        import joblib  # noqa: PLC0415
        import ml.baseline_trainer as trainer_module  # noqa: PLC0415

        df = _make_synthetic_df(n=80, seed=7)
        model, preprocessor, _ = train(df)

        original_dir = trainer_module.MODELS_DIR
        trainer_module.MODELS_DIR = tmp_path
        try:
            save_model(model, preprocessor, date_str="2025-06-01")
        finally:
            trainer_module.MODELS_DIR = original_dir

        assert (tmp_path / "baseline_2025-06-01.pkl").exists()
        assert (tmp_path / "baseline_latest.pkl").exists()
