"""
workers/risk.py — Celery task for computing building risk scores (H-6).

compute_risk_scores(city_id) loads all buildings with their latest
building_features row, runs the XGBoost + SHAP predictor, and upserts
results into the risk_scores table.

Beat schedule: daily at 04:00 UTC, queue "risk".
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB helper — same pattern as workers/features.py
# ---------------------------------------------------------------------------


def _sync_db_conn():
    """Return a psycopg (sync) connection using DATABASE_URL env var."""
    import psycopg  # noqa: PLC0415

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    sync_url = (
        db_url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )
    return psycopg.connect(sync_url)


# ---------------------------------------------------------------------------
# Dynamic modifier — optional dependency
# ---------------------------------------------------------------------------


def _get_dynamic_modifier(building_id: str, city_id: str) -> float:
    """Return dynamic risk modifier.  Defaults to 1.0 if module not yet built."""
    try:
        from services.dynamic_modifier import compute_modifier  # noqa: PLC0415

        return float(compute_modifier(building_id, city_id))
    except ImportError:
        return 1.0
    except Exception as exc:  # noqa: BLE001
        logger.debug("dynamic_modifier error for %s: %s", building_id, exc)
        return 1.0


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="workers.risk.compute_risk_scores",
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
)
def compute_risk_scores(self, city_id: str) -> Dict[str, Any]:
    """
    Compute XGBoost + SHAP risk scores for every building in city_id and
    upsert into risk_scores.

    Returns {"city_id", "buildings_processed", "score_date"}.
    """
    logger.info("compute_risk_scores started for city_id=%s", city_id)

    from services.risk_predictor import RiskPredictor  # noqa: PLC0415

    predictor = RiskPredictor.get_instance()
    score_date: str = datetime.date.today().isoformat()
    buildings_processed: int = 0

    conn = _sync_db_conn()
    try:
        # ------------------------------------------------------------------ #
        # 1. Fetch all buildings with their latest building_features row
        # ------------------------------------------------------------------ #
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    b.id            AS building_id,
                    b.city_id,
                    bf.nearest_hydrant_m,
                    bf.nearest_station_m,
                    bf.incidents_500m_3y,
                    bf.incidents_on_building_3y,
                    bf.building_density_500m,
                    bf.age_years,
                    bf.population_estimate,
                    bf.days_since_last_incident,
                    bf.days_since_last_inspection,
                    bf.building_type
                FROM buildings b
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM building_features bf2
                    WHERE bf2.building_id = b.id
                    ORDER BY bf2.feature_date DESC
                    LIMIT 1
                ) bf ON TRUE
                WHERE b.city_id = %s
                """,
                (city_id,),
            )
            rows = cur.fetchall()

        if not rows:
            logger.info("compute_risk_scores: no buildings for city_id=%s", city_id)
            return {
                "city_id": city_id,
                "buildings_processed": 0,
                "score_date": score_date,
            }

        columns: List[str] = [
            "building_id",
            "city_id",
            "nearest_hydrant_m",
            "nearest_station_m",
            "incidents_500m_3y",
            "incidents_on_building_3y",
            "building_density_500m",
            "age_years",
            "population_estimate",
            "days_since_last_incident",
            "days_since_last_inspection",
            "building_type",
        ]
        buildings: List[Dict[str, Any]] = [dict(zip(columns, row)) for row in rows]
        logger.info(
            "compute_risk_scores: %d buildings to process for city_id=%s",
            len(buildings),
            city_id,
        )

        # ------------------------------------------------------------------ #
        # 2. Score each building and upsert
        # ------------------------------------------------------------------ #
        with conn.cursor() as cur:
            for building in buildings:
                building_id: str = building["building_id"]

                # Feature dict for predictor
                feature_row: Dict[str, Any] = {k: building[k] for k in columns[2:]}

                baseline: Optional[float] = predictor.predict(feature_row)
                if baseline is None:
                    baseline = 0.0

                shap_factors: List[Dict[str, Any]] = predictor.explain(feature_row)

                modifier: float = _get_dynamic_modifier(building_id, city_id)
                final_score: float = baseline * modifier

                cur.execute(
                    """
                    INSERT INTO risk_scores (
                        building_id, city_id, computed_at,
                        baseline_score, dynamic_modifier, final_score,
                        shap_values, score_date
                    ) VALUES (
                        %s, %s, NOW(),
                        %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (building_id, score_date) DO UPDATE SET
                        computed_at      = EXCLUDED.computed_at,
                        baseline_score   = EXCLUDED.baseline_score,
                        dynamic_modifier = EXCLUDED.dynamic_modifier,
                        final_score      = EXCLUDED.final_score,
                        shap_values      = EXCLUDED.shap_values
                    """,
                    (
                        building_id,
                        city_id,
                        baseline,
                        modifier,
                        final_score,
                        json.dumps(shap_factors) if shap_factors else None,
                        score_date,
                    ),
                )
                buildings_processed += 1

        conn.commit()
        logger.info(
            "compute_risk_scores finished: city_id=%s, buildings_processed=%d",
            city_id,
            buildings_processed,
        )

    finally:
        conn.close()

    return {
        "city_id": city_id,
        "buildings_processed": buildings_processed,
        "score_date": score_date,
    }
