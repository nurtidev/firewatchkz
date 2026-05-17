"""
routers/v2/hydrants.py — Hydrant list endpoint (API v2).

GET /api/v2/hydrants
  Query params:
    city   : str (required)
    bbox   : str (optional) — "lon_min,lat_min,lon_max,lat_max"
    status : str (optional) — "working" | "maintenance" | "out_of_service"
    limit  : int (default 500, max 2000)
    offset : int (default 0)
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

VALID_STATUSES = {"working", "maintenance", "out_of_service"}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class HydrantOut(BaseModel):
    id: str
    city: str
    address: Optional[str]
    status: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    capacity_l_s: Optional[float]
    last_check_at: Optional[str]
    winter_access: Optional[bool]


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


@router.get("/hydrants", response_model=List[HydrantOut])
async def list_hydrants(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    bbox: Optional[str] = Query(None, description="lon_min,lat_min,lon_max,lat_max"),
    status: Optional[str] = Query(None, description="working | maintenance | out_of_service"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> List[HydrantOut]:
    """Return hydrants for a city, optionally filtered by bbox and status."""

    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Недопустимый статус: {status}. Допустимые значения: {', '.join(sorted(VALID_STATUSES))}",
        )

    filters = ["city = :city"]
    params: dict = {"city": city, "limit": limit, "offset": offset}

    if status is not None:
        filters.append("status = :status")
        params["status"] = status

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
            SELECT id, city, address, status, lat, lon,
                   capacity_l_s, last_check_at, winter_access
            FROM hydrants
            {where_clause}
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()

    return [
        HydrantOut(
            id=str(row["id"]),
            city=row["city"],
            address=row["address"],
            status=row["status"],
            lat=float(row["lat"]) if row["lat"] is not None else None,
            lon=float(row["lon"]) if row["lon"] is not None else None,
            capacity_l_s=float(row["capacity_l_s"]) if row["capacity_l_s"] is not None else None,
            last_check_at=str(row["last_check_at"]) if row["last_check_at"] is not None else None,
            winter_access=row["winter_access"],
        )
        for row in rows
    ]
