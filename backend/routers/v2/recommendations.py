"""
routers/v2/recommendations.py — Recommendations endpoint (API v2).

GET /api/v2/recommendations?city=astana
Auth: none (same as v1)
Returns: list of {priority, title, description, expected_impact}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.claude_client import ClaudeClient
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()

# City display names (mirrors v1 CITY_CONFIG)
_CITY_NAMES: Dict[str, str] = {
    "astana": "Астана",
    "almaty": "Алматы",
    "shymkent": "Шымкент",
}


@router.get("/recommendations", tags=["recommendations-v2"])
async def get_recommendations(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return AI-generated fire safety recommendations for the city."""
    city_key = city.lower()
    loader = DataLoaderV2()
    district_stats = await loader.get_district_stats(city_key)
    kpi = await loader.get_kpi(city_key)

    # Build district stats table string (replicates v1 DataFrame.to_string)
    if district_stats:
        header = "  ".join(str(k) for k in district_stats[0].keys())
        rows = [header]
        for row in district_stats:
            rows.append("  ".join(str(v) for v in row.values()))
        district_stats_table = "\n".join(rows)
    else:
        district_stats_table = "Нет данных по районам"

    # Top 3 causes from district stats
    cause_counts: Dict[str, int] = {}
    for row in district_stats:
        cause = row.get("top_cause")
        if cause:
            cause_counts[cause] = cause_counts.get(cause, 0) + 1
    top_causes = ", ".join(list(cause_counts.keys())[:3]) if cause_counts else ""

    city_name = _CITY_NAMES.get(city_key, city_key.capitalize())

    # Build minimal buildings list for the prompt (no buildings table in v2,
    # use district names as building stand-ins to satisfy the v1 prompt structure)
    buildings: List[Dict[str, Any]] = [
        {
            "name": row.get("district", ""),
            "district": row.get("district", ""),
            "object_type": "district",
            "floors_count": None,
            "arrival_time_minutes": None,
            "potential_hazards": row.get("top_cause", ""),
        }
        for row in district_stats[:5]
    ]

    client = ClaudeClient()
    return client.get_recommendations(
        city=city_key,
        city_name=city_name,
        district_stats_table=district_stats_table,
        top_causes=top_causes,
        buildings=buildings,
    )
