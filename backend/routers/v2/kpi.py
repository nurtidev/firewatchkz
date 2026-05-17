"""
routers/v2/kpi.py — KPI endpoint (API v2).

GET /api/v2/kpi?city=astana → aggregate KPI dict
Auth: require_analyst_or_above
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_analyst_or_above
from services.data_loader_v2 import DataLoaderV2

router = APIRouter()


@router.get("/kpi", tags=["kpi-v2"])
async def get_kpi(
    city: Optional[str] = Query(None, description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> Dict[str, Any]:
    """Return aggregate KPI metrics for the given city."""
    loader = DataLoaderV2()
    return await loader.get_kpi(city)
