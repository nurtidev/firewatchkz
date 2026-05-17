"""
v2 data loader — async SQLAlchemy over PostgreSQL.
Replaces pandas/CSV data_loader.py for /api/v2/* endpoints.
v1 endpoints continue using the original data_loader.py unchanged.
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import AsyncSessionLocal


class DataLoaderV2:
    """
    Async data access layer for v2 endpoints.
    All methods return plain dicts/lists — no pandas DataFrames.
    """

    # ------------------------------------------------------------------ #
    # Cities                                                               #
    # ------------------------------------------------------------------ #

    async def get_cities(self) -> List[Dict[str, Any]]:
        """Return list of available cities."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT id, code, name,
                       ST_Y(center::geometry) AS lat,
                       ST_X(center::geometry) AS lon,
                       zoom
                FROM cities
                ORDER BY name
            """))
            rows = result.mappings().all()
            return [
                {
                    "id": r["code"],
                    "name": r["name"],
                    "center": [r["lat"], r["lon"]] if r["lat"] else [51.18, 71.45],
                    "zoom": r["zoom"] or 12,
                }
                for r in rows
            ]

    # ------------------------------------------------------------------ #
    # Districts (aggregate from incidents)                                 #
    # ------------------------------------------------------------------ #

    async def get_district_stats(self, city: str) -> List[Dict[str, Any]]:
        """
        Return risk stats per district, aggregated from incidents.
        risk_score = min(100, incidents_last_12m/max * 70 + avg_damage/max * 30)
        """
        async with AsyncSessionLocal() as session:
            cutoff_1y = datetime.now(timezone.utc) - timedelta(days=365)
            result = await session.execute(text("""
                WITH base AS (
                    SELECT
                        district,
                        COUNT(*) FILTER (WHERE occurred_at >= :cutoff) AS incidents_last_12m,
                        COUNT(*) AS total_incidents,
                        AVG(damage_tenge) AS avg_damage,
                        MODE() WITHIN GROUP (ORDER BY cause) AS top_cause
                    FROM incidents
                    WHERE district IS NOT NULL AND district != ''
                    GROUP BY district
                ),
                maxvals AS (
                    SELECT
                        MAX(incidents_last_12m) AS max_inc,
                        MAX(avg_damage) AS max_dmg
                    FROM base
                )
                SELECT
                    b.district,
                    b.total_incidents,
                    b.incidents_last_12m,
                    b.avg_damage,
                    b.top_cause,
                    LEAST(100, ROUND(
                        COALESCE(b.incidents_last_12m::float / NULLIF(m.max_inc,0), 0) * 70 +
                        COALESCE(b.avg_damage / NULLIF(m.max_dmg,0), 0) * 30
                    )) AS risk_score
                FROM base b, maxvals m
                ORDER BY risk_score DESC
            """), {"cutoff": cutoff_1y})
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Incidents                                                            #
    # ------------------------------------------------------------------ #

    async def get_incidents(
        self,
        city: Optional[str] = None,
        district: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Paginated incident list."""
        filters = ["1=1"]
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if district:
            filters.append("district = :district")
            params["district"] = district
        if date_from:
            filters.append("occurred_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            filters.append("occurred_at <= :date_to")
            params["date_to"] = date_to

        where = " AND ".join(filters)
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(f"""
                SELECT id, external_id, occurred_at, district, building_type,
                       cause, severity, damage_tenge, casualties,
                       lat, lon, address_text
                FROM incidents
                WHERE {where}
                ORDER BY occurred_at DESC
                LIMIT :limit OFFSET :offset
            """), params)
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    async def get_monthly_counts(self, city: Optional[str] = None) -> List[Dict[str, Any]]:
        """Monthly incident counts for forecast/chart."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT
                    TO_CHAR(DATE_TRUNC('month', occurred_at), 'YYYY-MM') AS year_month,
                    COUNT(*) AS count
                FROM incidents
                GROUP BY DATE_TRUNC('month', occurred_at)
                ORDER BY DATE_TRUNC('month', occurred_at)
            """))
            return [dict(r) for r in result.mappings().all()]

    # ------------------------------------------------------------------ #
    # KPI                                                                  #
    # ------------------------------------------------------------------ #

    async def get_kpi(self, city: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate KPI metrics."""
        async with AsyncSessionLocal() as session:
            this_year = datetime.now(timezone.utc).year
            last_year = this_year - 1

            r = await session.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM occurred_at) = :this_year) AS ytd,
                    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM occurred_at) = :last_year) AS prev_year,
                    COALESCE(SUM(damage_tenge) FILTER (
                        WHERE EXTRACT(YEAR FROM occurred_at) = :this_year), 0) AS damage_ytd
                FROM incidents
            """), {"this_year": this_year, "last_year": last_year})
            row = r.mappings().first() or {}

            ytd = row.get("ytd") or 0
            prev = row.get("prev_year") or 1
            damage = float(row.get("damage_ytd") or 0)
            vs_pct = round((ytd - prev) / prev * 100) if prev else 0

            # Highest risk district
            districts = await self.get_district_stats(city or "astana")
            top_district = districts[0]["district"] if districts else "—"

            # Top cause YTD
            r2 = await session.execute(text("""
                SELECT cause, COUNT(*) AS cnt
                FROM incidents
                WHERE EXTRACT(YEAR FROM occurred_at) = :this_year
                  AND cause IS NOT NULL
                GROUP BY cause ORDER BY cnt DESC LIMIT 1
            """), {"this_year": this_year})
            cause_row = r2.mappings().first()
            top_cause = cause_row["cause"] if cause_row else "—"

            return {
                "total_incidents_ytd": ytd,
                "vs_last_year_pct": vs_pct,
                "total_damage_tenge": damage,
                "highest_risk_district": top_district,
                "top_cause": top_cause,
                "prevention_potential_tenge": round(damage * 0.30),
                "prevention_potential_incidents": round(ytd * 0.30),
                "roi_note": "Estimated 30% reduction with AI prevention program",
            }

    # ------------------------------------------------------------------ #
    # Hydrants & Stations                                                  #
    # ------------------------------------------------------------------ #

    async def get_hydrants(
        self,
        city: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters = ["1=1"]
        params: Dict[str, Any] = {}
        if city:
            filters.append("city = :city")
            params["city"] = city
        if status:
            filters.append("status = :status")
            params["status"] = status
        where = " AND ".join(filters)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(f"SELECT id, city, district, address, status, lat, lon FROM hydrants WHERE {where} ORDER BY id"),
                params,
            )
            return [dict(r) for r in result.mappings().all()]

    async def get_stations(self, city: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        where = "1=1"
        if city:
            where = "city = :city"
            params["city"] = city
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(f"SELECT id, city, name, district, units, staff_count, lat, lon FROM fire_stations WHERE {where} ORDER BY name"),
                params,
            )
            return [dict(r) for r in result.mappings().all()]

    # ------------------------------------------------------------------ #
    # Buildings                                                            #
    # ------------------------------------------------------------------ #

    async def get_building(self, building_id: str) -> Optional[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT id, city_id, address, building_type, floors_above,
                       total_area_sqm, year_built, source, external_id,
                       ST_Y(centroid::geometry) AS lat,
                       ST_X(centroid::geometry) AS lon
                FROM buildings WHERE id = :id
            """), {"id": building_id})
            row = result.mappings().first()
            return dict(row) if row else None

    async def get_buildings(
        self,
        city_id: Optional[str] = None,
        bbox: Optional[Dict[str, float]] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        filters = ["1=1"]
        params: Dict[str, Any] = {"limit": limit}
        if city_id:
            filters.append("city_id = :city_id")
            params["city_id"] = city_id
        if bbox:
            filters.append("""
                ST_Within(centroid, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))
            """)
            params.update(bbox)
        where = " AND ".join(filters)
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(f"""
                SELECT id, city_id, address, building_type, floors_above,
                       source,
                       ST_Y(centroid::geometry) AS lat,
                       ST_X(centroid::geometry) AS lon
                FROM buildings WHERE {where} AND centroid IS NOT NULL
                LIMIT :limit
            """), params)
            return [dict(r) for r in result.mappings().all()]


# Module-level singleton
_loader: Optional[DataLoaderV2] = None

def get_data_loader_v2() -> DataLoaderV2:
    global _loader
    if _loader is None:
        _loader = DataLoaderV2()
    return _loader
