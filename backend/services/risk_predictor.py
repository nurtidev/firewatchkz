"""
services/risk_predictor.py — XGBoost + SHAP risk predictor wrapper.

Loads the trained baseline model and provides:
  - predict(feature_row) → float  (incidents/year)
  - explain(feature_row) → List[dict]  (top-5 SHAP contributions)

Designed as a module-level singleton via get_instance().
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Path to the default model file
_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "models" / "baseline_latest.pkl"


class RiskPredictor:
    """Loads the trained XGBoost model and computes SHAP-based risk scores."""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self._model_path: Path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        self._payload: Optional[Dict[str, Any]] = None
        self._explainer: Optional[Any] = None  # shap.TreeExplainer, loaded lazily

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> bool:
        """Load the model payload. Returns True on success, False if file missing."""
        if self._payload is not None:
            return True

        if not self._model_path.exists():
            logger.warning(
                "RiskPredictor: model file not found at %s — predictions disabled",
                self._model_path,
            )
            return False

        try:
            from ml.baseline_trainer import load_model  # noqa: PLC0415

            self._payload = load_model(self._model_path)
            logger.info("RiskPredictor: loaded model from %s", self._model_path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("RiskPredictor: failed to load model — %s", exc)
            return False

    def _build_input_df(self, feature_row: Dict[str, Any]):
        """Convert a feature dict to a single-row DataFrame for the preprocessor."""
        import pandas as pd  # noqa: PLC0415

        from ml.baseline_trainer import CATEGORICAL_COL, FEATURE_COLS  # noqa: PLC0415

        all_cols = FEATURE_COLS + [CATEGORICAL_COL]
        row: Dict[str, Any] = {col: feature_row.get(col) for col in all_cols}
        return pd.DataFrame([row])

    def _get_explainer(self, model: Any) -> Any:
        """Return (cached) shap.TreeExplainer for *model*."""
        if self._explainer is None:
            import shap  # noqa: PLC0415

            self._explainer = shap.TreeExplainer(model)
        return self._explainer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, feature_row: Dict[str, Any]) -> Optional[float]:
        """Return predicted incidents/year for a single building.

        Returns None when the model file is unavailable.
        """
        if not self._load():
            return None

        assert self._payload is not None  # mypy
        model = self._payload["model"]
        preprocessor = self._payload["preprocessor"]

        df = self._build_input_df(feature_row)
        try:
            X = preprocessor.transform(df)
            pred = model.predict(X)
            return float(pred[0])
        except Exception as exc:  # noqa: BLE001
            logger.error("RiskPredictor.predict error: %s", exc)
            return None

    def explain(self, feature_row: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return top-5 SHAP contributions as [{feature, value, shap_value}, ...].

        Returns an empty list when the model or shap library is unavailable.
        """
        if not self._load():
            return []

        assert self._payload is not None  # mypy

        try:
            import shap  # noqa: PLC0415
        except ImportError:
            logger.warning("RiskPredictor.explain: shap not installed — no explanations")
            return []

        model = self._payload["model"]
        preprocessor = self._payload["preprocessor"]

        from ml.baseline_trainer import CATEGORICAL_COL, FEATURE_COLS  # noqa: PLC0415

        df = self._build_input_df(feature_row)
        try:
            X = preprocessor.transform(df)
            explainer = self._get_explainer(model)
            shap_vals = explainer.shap_values(X)

            # shap_vals shape: (1, n_features)
            if hasattr(shap_vals, "__len__") and len(shap_vals) > 0:
                row_shap = shap_vals[0]  # 1-D array of shap values for this row
            else:
                return []

            # Build feature names — numerics first, then OHE categories
            num_names: List[str] = list(FEATURE_COLS)
            try:
                ohe = preprocessor.named_transformers_["cat"]["ohe"]
                cat_names: List[str] = list(ohe.get_feature_names_out([CATEGORICAL_COL]))
            except Exception:  # noqa: BLE001
                cat_names = []
            all_feature_names: List[str] = num_names + cat_names

            # Pair feature names with shap values
            paired: List[Dict[str, Any]] = []
            for i, sv in enumerate(row_shap):
                fname = all_feature_names[i] if i < len(all_feature_names) else f"feature_{i}"
                fval = float(X[0, i]) if hasattr(X, "__getitem__") else None
                paired.append({"feature": fname, "value": fval, "shap_value": float(sv)})

            # Sort by |shap_value| descending, take top 5
            paired.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
            return paired[:5]

        except Exception as exc:  # noqa: BLE001
            logger.error("RiskPredictor.explain error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    _instance: Optional["RiskPredictor"] = None

    @classmethod
    def get_instance(cls) -> "RiskPredictor":
        """Return the module-level singleton (load once, reuse)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
