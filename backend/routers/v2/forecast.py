"""
routers/v2/forecast.py — Forecast endpoint (API v2).

GET /api/v2/forecast?city=astana&months=6
Auth: none (same as v1)
Returns: {city, months, model, r_squared, historical, forecast}
"""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.data_loader_v2 import DataLoaderV2
from services.forecaster import Forecaster

router = APIRouter()


@router.get("/forecast", tags=["forecast-v2"])
async def get_forecast(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    months: int = Query(6, description="Горизонт прогноза: 3, 6 или 12 месяцев"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return Holt-Winters forecast for monthly incident counts."""
    if months not in (3, 6, 12):
        raise HTTPException(status_code=422, detail="months must be 3, 6, or 12")

    loader = DataLoaderV2()
    monthly = await loader.get_monthly_counts(city)

    if not monthly:
        raise HTTPException(
            status_code=404,
            detail=f"Нет данных об инцидентах для города '{city}'",
        )

    # Convert list of dicts → DataFrame with period index (matches v1 forecaster API)
    df = pd.DataFrame(monthly)
    df["year_month"] = pd.PeriodIndex(df["year_month"], freq="M")
    df["count"] = df["count"].astype(int)

    forecaster = Forecaster()
    return forecaster.generate_forecast(city=city, monthly_counts=df, months=months)
