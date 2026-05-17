"""
workers/features.py — Celery task for computing building features (H-4).

rebuild_features(city_id) computes 10 risk features per building and upserts
them into the building_features table. Runs in batches of 100 buildings.
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List, Optional

from celery_app import celery_app
from services.feature_builder import FeatureBuilder

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# DB helper — same pattern as workers/documents.py
# ---------------------------------------------------------------------------


def _sync_db_conn():
    """Return a psycopg (sync) connection using DATABASE_URL env var."""
    import psycopg  # noqa: PLC0415

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    return psycopg.connect(sync_url)


# ---------------------------------------------------------------------------
# Feature computation via SQL
# ---------------------------------------------------------------------------


def _compute_features_for_building(cur, building: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the per-building SQL queries and return a dict of feature values.

    building must have keys: id, city_id, centroid_wkt, year_built,
    floors_above, floors_below, total_area_sqm, building_type.
    """
    building_id: str = building["id"]
    city_id: str = building["city_id"]
    centroid_wkt: str = building["centroid_wkt"]

    # 1. nearest_hydrant_m
    cur.execute(
        """
        SELECT ST_Distance(h.geom::geography, ST_GeomFromText(%s, 4326)::geography)
        FROM hydrants h
        ORDER BY h.geom <-> ST_GeomFromText(%s, 4326)
        LIMIT 1
        """,
        (centroid_wkt, centroid_wkt),
    )
    row = cur.fetchone()
    nearest_hydrant_m: Optional[float] = float(row[0]) if row and row[0] is not None else None

    # 2. nearest_station_m
    cur.execute(
        """
        SELECT ST_Distance(fs.geom::geography, ST_GeomFromText(%s, 4326)::geography)
        FROM fire_stations fs
        ORDER BY fs.geom <-> ST_GeomFromText(%s, 4326)
        LIMIT 1
        """,
        (centroid_wkt, centroid_wkt),
    )
    row = cur.fetchone()
    nearest_station_m: Optional[float] = float(row[0]) if row and row[0] is not None else None

    # 3. incidents_500m_3y
    cur.execute(
        """
        SELECT COUNT(*)
        FROM incidents
        WHERE ST_DWithin(
            geom::geography,
            ST_GeomFromText(%s, 4326)::geography,
            500
        )
        AND occurred_at > NOW() - INTERVAL '3 years'
        """,
        (centroid_wkt,),
    )
    row = cur.fetchone()
    incidents_500m_3y: int = int(row[0]) if row else 0

    # 4. incidents_on_building_3y
    cur.execute(
        """
        SELECT COUNT(*)
        FROM incidents
        WHERE building_id = %s
        AND occurred_at > NOW() - INTERVAL '3 years'
        """,
        (building_id,),
    )
    row = cur.fetchone()
    incidents_on_building_3y: int = int(row[0]) if row else 0

    # 5. building_density_500m
    cur.execute(
        """
        SELECT COUNT(*)
        FROM buildings b2
        WHERE b2.city_id = %s
        AND ST_DWithin(
            b2.centroid::geography,
            ST_GeomFromText(%s, 4326)::geography,
            500
        )
        AND b2.id != %s
        """,
        (city_id, centroid_wkt, building_id),
    )
    row = cur.fetchone()
    building_density_500m: int = int(row[0]) if row else 0

    # 6 & 7. age_years and population_estimate — pure Python
    age_years: Optional[int] = FeatureBuilder.compute_age_years(building.get("year_built"))
    population_estimate: Optional[float] = FeatureBuilder.compute_population_estimate(
        building.get("floors_above"),
        building.get("total_area_sqm"),
    )

    # 8. days_since_last_incident
    cur.execute(
        """
        SELECT EXTRACT(DAY FROM NOW() - MAX(occurred_at))::int
        FROM incidents
        WHERE building_id = %s
        """,
        (building_id,),
    )
    row = cur.fetchone()
    days_since_last_incident: Optional[int] = int(row[0]) if (row and row[0] is not None) else None

    # 9. days_since_last_inspection
    cur.execute(
        """
        SELECT EXTRACT(DAY FROM NOW() - MAX(inspected_at))::int
        FROM inspections
        WHERE building_id = %s
        """,
        (building_id,),
    )
    row = cur.fetchone()
    days_since_last_inspection: Optional[int] = (
        int(row[0]) if (row and row[0] is not None) else None
    )

    # 10. building_type — taken directly from buildings row
    building_type: Optional[str] = building.get("building_type")

    return {
        "nearest_hydrant_m": nearest_hydrant_m,
        "nearest_station_m": nearest_station_m,
        "incidents_500m_3y": incidents_500m_3y,
        "incidents_on_building_3y": incidents_on_building_3y,
        "building_density_500m": building_density_500m,
        "age_years": age_years,
        "population_estimate": population_estimate,
        "days_since_last_incident": days_since_last_incident,
        "days_since_last_inspection": days_since_last_inspection,
        "building_type": building_type,
    }


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="workers.features.rebuild_features",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def rebuild_features(self, city_id: str) -> Dict[str, Any]:
    """
    Compute 10 risk features for every building in city_id and upsert into
    building_features. Buildings are processed in batches of 100.

    Returns {"city_id", "buildings_processed", "feature_date"}.
    """
    logger.info("rebuild_features started for city_id=%s", city_id)

    feature_date: str = datetime.date.today().isoformat()
    buildings_processed: int = 0

    conn = _sync_db_conn()
    try:
        # ------------------------------------------------------------------ #
        # 1. Fetch all buildings for the city
        # ------------------------------------------------------------------ #
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    city_id,
                    ST_AsText(centroid) AS centroid_wkt,
                    year_built,
                    floors_above,
                    floors_below,
                    total_area_sqm,
                    building_type
                FROM buildings
                WHERE city_id = %s
                """,
                (city_id,),
            )
            rows = cur.fetchall()

        if not rows:
            logger.info("rebuild_features: no buildings found for city_id=%s", city_id)
            return {
                "city_id": city_id,
                "buildings_processed": 0,
                "feature_date": feature_date,
            }

        # Convert rows to dicts
        columns: List[str] = [
            "id",
            "city_id",
            "centroid_wkt",
            "year_built",
            "floors_above",
            "floors_below",
            "total_area_sqm",
            "building_type",
        ]
        buildings: List[Dict[str, Any]] = [dict(zip(columns, row)) for row in rows]
        logger.info(
            "rebuild_features: %d buildings to process for city_id=%s",
            len(buildings),
            city_id,
        )

        # ------------------------------------------------------------------ #
        # 2. Process in batches
        # ------------------------------------------------------------------ #
        for batch_start in range(0, len(buildings), BATCH_SIZE):
            batch = buildings[batch_start : batch_start + BATCH_SIZE]

            with conn.cursor() as cur:
                for building in batch:
                    features = _compute_features_for_building(cur, building)

                    cur.execute(
                        """
                        INSERT INTO building_features (
                            building_id, city_id, feature_date,
                            nearest_hydrant_m, nearest_station_m,
                            incidents_500m_3y, incidents_on_building_3y,
                            building_density_500m, age_years,
                            population_estimate, days_since_last_incident,
                            days_since_last_inspection, building_type
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s
                        )
                        ON CONFLICT (building_id, feature_date) DO UPDATE SET
                            nearest_hydrant_m        = EXCLUDED.nearest_hydrant_m,
                            nearest_station_m        = EXCLUDED.nearest_station_m,
                            incidents_500m_3y        = EXCLUDED.incidents_500m_3y,
                            incidents_on_building_3y = EXCLUDED.incidents_on_building_3y,
                            building_density_500m    = EXCLUDED.building_density_500m,
                            age_years                = EXCLUDED.age_years,
                            population_estimate      = EXCLUDED.population_estimate,
                            days_since_last_incident = EXCLUDED.days_since_last_incident,
                            days_since_last_inspection = EXCLUDED.days_since_last_inspection,
                            building_type            = EXCLUDED.building_type
                        """,
                        (
                            building["id"],
                            building["city_id"],
                            feature_date,
                            features["nearest_hydrant_m"],
                            features["nearest_station_m"],
                            features["incidents_500m_3y"],
                            features["incidents_on_building_3y"],
                            features["building_density_500m"],
                            features["age_years"],
                            features["population_estimate"],
                            features["days_since_last_incident"],
                            features["days_since_last_inspection"],
                            features["building_type"],
                        ),
                    )
                    buildings_processed += 1

            conn.commit()
            logger.info(
                "rebuild_features: committed batch %d-%d for city_id=%s",
                batch_start,
                batch_start + len(batch) - 1,
                city_id,
            )

    finally:
        conn.close()

    logger.info(
        "rebuild_features finished: city_id=%s, buildings_processed=%d, feature_date=%s",
        city_id,
        buildings_processed,
        feature_date,
    )
    return {
        "city_id": city_id,
        "buildings_processed": buildings_processed,
        "feature_date": feature_date,
    }
