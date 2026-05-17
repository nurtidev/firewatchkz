"""
routers/v2/fire_stations.py — Fire station list endpoint (API v2).

GET /api/v2/fire-stations
  Query params:
    city  : str (required)
    bbox  : str (optional) — "lon_min,lat_min,lon_max,lat_max"
    limit : int (default 100, max 500)
  Auth: require_inspector_or_above
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_inspector_or_above

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class FireStationOut(BaseModel):
    id: str
    city: str
    name: Optional[str]
    address: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    units: Optional[int]
    staff_count: Optional[int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_bbox(bbox: str) -> tuple:
    """Parse bbox string "lon_min,lat_min,lon_max,lat_max".

    Returns (lon_min, lat_min, lon_max, lat_max) as floats.
    Raises HTTPException 422 if the string is malformed.
    """
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox должен содержать ровно 4 значения: lon_min,lat_min,lon_max,lat_max",
        )
    try:
        lon_min, lat_min, lon_max, lat_max = (float(p.strip()) for p in parts)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Все значения bbox должны быть числами",
        )
    return lon_min, lat_min, lon_max, lat_max


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/fire-stations", response_model=List[FireStationOut])
async def list_fire_stations(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    bbox: Optional[str] = Query(None, description="lon_min,lat_min,lon_max,lat_max"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> List[FireStationOut]:
    """Return fire stations for a city, optionally filtered by bbox."""

    filters = ["city = :city"]
    params: dict = {"city": city, "limit": limit}

    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = _parse_bbox(bbox)
        filters.append(
            "ST_Within(geom, ST_MakeEnvelope(:lon_min, :lat_min, :lon_max, :lat_max, 4326))"
        )
        params["lon_min"] = lon_min
        params["lat_min"] = lat_min
        params["lon_max"] = lon_max
        params["lat_max"] = lat_max

    where_clause = "WHERE " + " AND ".join(filters)

    result = await session.execute(
        text(
            f"""
            SELECT id, city, name, address, lat, lon, units, staff_count
            FROM fire_stations
            {where_clause}
            ORDER BY id
            LIMIT :limit
            """
        ),
        params,
    )
    rows = result.mappings().all()

    return [
        FireStationOut(
            id=str(row["id"]),
            city=row["city"],
            name=row["name"],
            address=row["address"],
            lat=float(row["lat"]) if row["lat"] is not None else None,
            lon=float(row["lon"]) if row["lon"] is not None else None,
            units=row["units"],
            staff_count=row["staff_count"],
        )
        for row in rows
    ]
