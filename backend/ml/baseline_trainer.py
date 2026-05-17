"""
ml/baseline_trainer.py — XGBoost Poisson baseline training for building fire risk.

CLI usage:
    python -m ml.baseline_trainer --city astana [--save] [--min-date 2025-01-01]
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEATURE_COLS: List[str] = [
    "nearest_hydrant_m",
    "nearest_station_m",
    "incidents_500m_3y",
    "incidents_on_building_3y",
    "building_density_500m",
    "age_years",
    "population_estimate",
    "days_since_last_incident",
    "days_since_last_inspection",
]

CATEGORICAL_COL = "building_type"

MODELS_DIR = Path(__file__).resolve().parent / "models"

# ---------------------------------------------------------------------------
# DB loading
# ---------------------------------------------------------------------------


def _sync_db_url() -> str:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    return (
        db_url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


def load_building_features(city: str, min_date: Optional[str] = None) -> pd.DataFrame:
    """
    Load building_features for *city* from PostgreSQL using a sync psycopg
    connection (same pattern as workers/features.py).

    Returns a DataFrame with all feature columns plus `target_rate`.
    Raises RuntimeError if DATABASE_URL is not set.
    """
    import psycopg  # noqa: PLC0415
    from psycopg.rows import dict_row  # noqa: PLC0415

    db_url = _sync_db_url()

    query = """
        SELECT
            bf.building_id,
            bf.feature_date,
            bf.nearest_hydrant_m,
            bf.nearest_station_m,
            bf.incidents_500m_3y,
            bf.incidents_on_building_3y,
            bf.building_density_500m,
            bf.age_years,
            bf.population_estimate,
            bf.days_since_last_incident,
            bf.days_since_last_inspection,
            bf.building_type,
            COALESCE(bf.incidents_on_building_3y, 0) / 3.0 AS target_rate
        FROM building_features bf
        WHERE bf.city_id = %s
        ORDER BY bf.feature_date
    """
    params: List[Any] = [city]

    if min_date:
        query = query.replace(
            "WHERE bf.city_id = %s",
            "WHERE bf.city_id = %s AND bf.feature_date >= %s",
        )
        params.append(min_date)

    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    if not rows:
        raise ValueError(f"No building_features found for city={city!r}")

    df = pd.DataFrame(rows)
    df["feature_date"] = pd.to_datetime(df["feature_date"])
    return df


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_poisson_deviance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Poisson deviance: 2 * sum(y_pred - y_true + y_true * log(y_true / y_pred)).

    A small epsilon is added to avoid log(0).  Returns 0.0 when y_true == y_pred.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    eps = 1e-8
    # Guard: predictions must be positive
    y_pred = np.clip(y_pred, eps, None)
    deviance = 2.0 * np.sum(y_pred - y_true + y_true * np.log(y_true / y_pred + eps))
    return float(deviance)


def compute_top_decile_lift(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Top-decile lift: fraction of total incidents captured in top-10% riskiest
    buildings, divided by the fraction expected at random (0.1).

    Lift = (incidents_in_top_decile / total_incidents) / 0.10

    Returns NaN when there are no incidents.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    total_incidents = y_true.sum()
    if total_incidents == 0:
        return float("nan")

    n = len(y_true)
    top_n = max(1, int(np.ceil(n * 0.10)))

    # Sort descending by predicted risk
    order = np.argsort(y_pred)[::-1]
    top_incidents = y_true[order[:top_n]].sum()

    lift = (top_incidents / total_incidents) / 0.10
    return float(lift)


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def build_preprocessor(df: pd.DataFrame):
    """
    Fit a preprocessor on *df*.

    Returns (preprocessor, feature_names) where preprocessor is a
    sklearn ColumnTransformer with:
      - median imputation + identity for numeric cols
      - OneHotEncoder(handle_unknown='ignore') for building_type
    """
    from sklearn.compose import ColumnTransformer  # noqa: PLC0415
    from sklearn.impute import SimpleImputer  # noqa: PLC0415
    from sklearn.pipeline import Pipeline  # noqa: PLC0415
    from sklearn.preprocessing import OneHotEncoder  # noqa: PLC0415

    num_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )
    cat_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, FEATURE_COLS),
            ("cat", cat_pipeline, [CATEGORICAL_COL]),
        ],
        remainder="drop",
    )
    return preprocessor


# ---------------------------------------------------------------------------
# Train / evaluate
# ---------------------------------------------------------------------------


def train(
    df: pd.DataFrame,
) -> Tuple[Any, Any, Dict[str, float]]:
    """
    Train an XGBoost Poisson model on *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain FEATURE_COLS + [CATEGORICAL_COL, 'feature_date', 'target_rate'].

    Returns
    -------
    model : XGBRegressor (fitted)
    preprocessor : sklearn ColumnTransformer (fitted on train split)
    metrics : dict with keys train_deviance, valid_deviance, top_decile_lift
    """
    from xgboost import XGBRegressor  # noqa: PLC0415

    # ------------------------------------------------------------------ #
    # 1. Time-based split — fall back to random 80/20 if only one date bucket
    # ------------------------------------------------------------------ #
    cutoff = pd.Timestamp("2025-01-01")
    train_mask = df["feature_date"] < cutoff
    valid_mask = df["feature_date"] >= cutoff

    if train_mask.sum() == 0 or valid_mask.sum() == 0:
        # Synthetic data: single date bucket → random 80/20 split
        logger.info(
            "Only one date bucket detected — using random 80/20 split instead of temporal split"
        )
        from sklearn.model_selection import train_test_split  # noqa: PLC0415

        df_train, df_valid = train_test_split(df, test_size=0.20, random_state=42)
    else:
        df_train = df[train_mask].copy()
        df_valid = df[valid_mask].copy()

    logger.info(
        "Train size=%d  Valid size=%d", len(df_train), len(df_valid)
    )

    y_train = df_train["target_rate"].values.astype(float)
    y_valid = df_valid["target_rate"].values.astype(float)

    # ------------------------------------------------------------------ #
    # 2. Preprocess
    # ------------------------------------------------------------------ #
    preprocessor = build_preprocessor(df_train)
    X_train = preprocessor.fit_transform(df_train[FEATURE_COLS + [CATEGORICAL_COL]])
    X_valid = preprocessor.transform(df_valid[FEATURE_COLS + [CATEGORICAL_COL]])

    # ------------------------------------------------------------------ #
    # 3. Fit XGBoost
    # ------------------------------------------------------------------ #
    model = XGBRegressor(
        objective="count:poisson",
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        tree_method="hist",
        eval_metric="poisson-nloglik",
        early_stopping_rounds=20,
        verbosity=0,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_valid, y_valid)],
        verbose=False,
    )

    # ------------------------------------------------------------------ #
    # 4. Metrics
    # ------------------------------------------------------------------ #
    pred_train = model.predict(X_train)
    pred_valid = model.predict(X_valid)

    train_deviance = compute_poisson_deviance(y_train, pred_train)
    valid_deviance = compute_poisson_deviance(y_valid, pred_valid)
    lift = compute_top_decile_lift(y_valid, pred_valid)

    metrics: Dict[str, float] = {
        "train_deviance": train_deviance,
        "valid_deviance": valid_deviance,
        "top_decile_lift": lift,
    }

    print(f"[train]  Poisson deviance — train: {train_deviance:.4f}  valid: {valid_deviance:.4f}")
    print(f"[train]  Top-decile lift (valid): {lift:.3f}")

    return model, preprocessor, metrics


# ---------------------------------------------------------------------------
# Model save / load
# ---------------------------------------------------------------------------


def save_model(model: Any, preprocessor: Any, date_str: Optional[str] = None) -> Path:
    """
    Save model artefacts to MODELS_DIR.

    Saves two copies:
      - baseline_{YYYY-MM-DD}.pkl  (dated)
      - baseline_latest.pkl        (always overwritten)

    Returns the path of the dated file.
    """
    import sys  # noqa: PLC0415

    import joblib  # noqa: PLC0415

    # Read MODELS_DIR from the module at call time so tests can monkey-patch it.
    _models_dir: Path = sys.modules[__name__].MODELS_DIR  # type: ignore[attr-defined]
    _models_dir.mkdir(parents=True, exist_ok=True)

    if date_str is None:
        date_str = datetime.date.today().isoformat()

    payload = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_cols": FEATURE_COLS,
    }

    dated_path = _models_dir / f"baseline_{date_str}.pkl"
    latest_path = _models_dir / "baseline_latest.pkl"

    joblib.dump(payload, dated_path)
    shutil.copy2(dated_path, latest_path)

    logger.info("Model saved to %s and %s", dated_path, latest_path)
    print(f"[save]   Model saved → {dated_path}")
    print(f"[save]   Model saved → {latest_path}")
    return dated_path


def load_model(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load a model payload from *path* (defaults to baseline_latest.pkl).

    Returns dict with keys: model, preprocessor, feature_cols.
    """
    import joblib  # noqa: PLC0415

    if path is None:
        path = MODELS_DIR / "baseline_latest.pkl"
    return joblib.load(path)


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------


async def main(city: str, save: bool = False, min_date: Optional[str] = None) -> None:
    print(f"[main]   Loading building_features for city={city!r} ...")
    df = load_building_features(city, min_date=min_date)
    print(f"[main]   Loaded {len(df)} rows, {df['building_id'].nunique()} buildings")

    model, preprocessor, metrics = train(df)

    if save:
        save_model(model, preprocessor)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Train XGBoost Poisson baseline for building fire risk."
    )
    parser.add_argument("--city", default="astana", help="City slug (default: astana)")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save trained model to ml/models/",
    )
    parser.add_argument(
        "--min-date",
        default=None,
        help="Only use features from this date onward (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.city, save=args.save, min_date=args.min_date))
