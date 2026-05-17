"""
routers/v2/risk_map.py — Risk map and incidents endpoints (API v2).

GET /api/v2/risk-map?city=astana
    → district risk array
    Auth: require_analyst_or_above

GET /api/v2/incidents?city=astana&district=&limit=50
    → paginated incident list
    Auth: none (public)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_analyst_or_above
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()


@router.get("/risk-map", tags=["risk-map-v2"])
async def get_risk_map(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> List[Dict[str, Any]]:
    """Return district risk array for the given city."""
    loader = DataLoaderV2()
    return await loader.get_district_stats(city)


@router.get("/incidents", tags=["incidents-v2"])
async def list_incidents(
    city: Optional[str] = Query(None, description="Идентификатор города (например, astana)"),
    district: Optional[str] = Query(None, description="Фильтр по району"),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Return paginated list of incidents. No auth required."""
    loader = DataLoaderV2()
    items = await loader.get_incidents(
        city=city,
        district=district,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"total": len(items), "items": items}
