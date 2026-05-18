"""
routers/v2/operations.py — Operations endpoints (API v2).

GET /api/v2/operations?city=astana     → list operations from Postgres
GET /api/v2/operations/kpi?city=astana → aggregate KPI
Auth: require_analyst_or_above
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_analyst_or_above

router = APIRouter()


@router.get("/operations/kpi", tags=["operations-v2"])
async def get_operations_kpi(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> Dict[str, Any]:
    """Return aggregate operations KPI: avg response time, count, fastest station, slowest district."""
    # Overall aggregates
    agg_result = await session.execute(
        text("""
            SELECT
                COUNT(*) AS operations_count,
                AVG(response_time_min) AS avg_response_time
            FROM operations
            WHERE city_id = :city
        """),
        {"city": city},
    )
    agg_row = agg_result.mappings().first() or {}

    operations_count = int(agg_row.get("operations_count") or 0)
    avg_response_time = round(float(agg_row.get("avg_response_time") or 0.0), 1)

    # Fastest station (lowest avg response time)
    fastest_result = await session.execute(
        text("""
            SELECT station_id, AVG(response_time_min) AS avg_time
            FROM operations
            WHERE city_id = :city AND station_id IS NOT NULL
            GROUP BY station_id
            ORDER BY avg_time ASC
            LIMIT 1
        """),
        {"city": city},
    )
    fastest_row = fastest_result.mappings().first()
    fastest_station: Optional[str] = fastest_row["station_id"] if fastest_row else None

    # Slowest district (highest avg response time)
    slowest_result = await session.execute(
        text("""
            SELECT district, AVG(response_time_min) AS avg_time
            FROM operations
            WHERE city_id = :city AND district IS NOT NULL
            GROUP BY district
            ORDER BY avg_time DESC
            LIMIT 1
        """),
        {"city": city},
    )
    slowest_row = slowest_result.mappings().first()
    slowest_district: Optional[str] = slowest_row["district"] if slowest_row else None

    return {
        "city": city.lower(),
        "avg_response_time_min": avg_response_time,
        "operations_count": operations_count,
        "fastest_station": fastest_station,
        "slowest_district": slowest_district,
    }


@router.get("/operations", tags=["operations-v2"])
async def list_operations(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> Dict[str, Any]:
    """Return latest 200 operations for the given city."""
    result = await session.execute(
        text("""
            SELECT id, date, city_id, district, station_id,
                   response_time_min, outcome, notes
            FROM operations
            WHERE city_id = :city
            ORDER BY date DESC
            LIMIT 200
        """),
        {"city": city},
    )
    rows = result.mappings().all()
    items: List[Dict[str, Any]] = [dict(r) for r in rows]
    return {"total": len(items), "items": items}


@router.get("/operations/analytics", tags=["operations-v2"])
async def get_operations_analytics(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> Dict[str, Any]:
    """Аналитика последствий инцидентов: ущерб, жертвы, причины, тренд по месяцам.

    Использует таблицу incidents (агрегаты SQL). Дополнительно подмешивает
    среднее время реагирования из operations.
    """

    # Top-level aggregates
    totals_row = (await session.execute(
        text(
            """
            SELECT
                COUNT(*)::int AS total_incidents,
                COALESCE(SUM(damage_tenge), 0)::bigint AS total_damage,
                COALESCE(SUM(casualties), 0)::int AS total_casualties
            FROM incidents
            """
        ),
    )).mappings().first() or {}

    # By cause
    cause_rows = (await session.execute(
        text(
            """
            SELECT cause,
                   COUNT(*)::int AS count,
                   COALESCE(SUM(damage_tenge), 0)::bigint AS damage
            FROM incidents
            GROUP BY cause
            ORDER BY count DESC
            """
        ),
    )).mappings().all()

    # By severity
    severity_rows = (await session.execute(
        text(
            """
            SELECT severity, COUNT(*)::int AS count
            FROM incidents
            GROUP BY severity
            """
        ),
    )).mappings().all()

    # Monthly trend (last 12 months). Column is occurred_at, not date.
    monthly_rows = (await session.execute(
        text(
            """
            SELECT
                to_char(date_trunc('month', occurred_at), 'YYYY-MM') AS month,
                COUNT(*)::int AS count,
                COALESCE(SUM(damage_tenge), 0)::bigint AS damage
            FROM incidents
            WHERE occurred_at >= (CURRENT_DATE - INTERVAL '12 months')
            GROUP BY 1
            ORDER BY 1
            """
        ),
    )).mappings().all()

    # Avg response time from operations table.
    # Schema note: operations.city (not city_id) per migration 0003.
    avg_resp_row = (await session.execute(
        text(
            "SELECT AVG(response_time_min) AS avg_min FROM operations WHERE city = :city"
        ),
        {"city": city},
    )).mappings().first() or {}
    avg_response_min = (
        round(float(avg_resp_row["avg_min"]), 1)
        if avg_resp_row.get("avg_min") is not None
        else None
    )

    return {
        "city": city,
        "totals": {
            "incidents": int(totals_row.get("total_incidents") or 0),
            "damage_tenge": int(totals_row.get("total_damage") or 0),
            "casualties": int(totals_row.get("total_casualties") or 0),
            "avg_response_min": avg_response_min,
        },
        "by_cause": [
            {
                "cause": r["cause"],
                "count": int(r["count"]),
                "damage_tenge": int(r["damage"]),
            }
            for r in cause_rows
        ],
        "by_severity": [
            {"severity": r["severity"], "count": int(r["count"])} for r in severity_rows
        ],
        "monthly": [
            {
                "month": r["month"],
                "count": int(r["count"]),
                "damage_tenge": int(r["damage"]),
            }
            for r in monthly_rows
        ],
    }
