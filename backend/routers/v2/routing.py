"""routers/v2/routing.py — Routing & ETA endpoints (frontend contract).

Эндпоинты, которые ждёт `frontend/src/lib/api.ts`:
  GET  /api/v2/routing/stations?city=astana
  POST /api/v2/routing/estimate    { from_lat, from_lon, to_lat, to_lon, city, station_id? }

ETA считается по haversine + средняя скорость, экстренный режим — с коэффициентом.
OSRM не подключён — возвращаем geometry=None и source="haversine".
"""
from __future__ import annotations

import math
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

router = APIRouter()

# Средние скорости в км/ч для расчёта ETA по прямой
_NORMAL_KMH = 35.0       # городской трафик
_EMERGENCY_KMH = 60.0    # с мигалкой/выделенкой


class RoutingStation(BaseModel):
    id: str
    name: str
    district: str
    lat: float
    lon: float


class RouteEstimateRequest(BaseModel):
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    city: str
    station_id: Optional[str] = None


class RouteEstimateResponse(BaseModel):
    normal_min: float
    emergency_min: float
    savings_min: float
    distance_km: float
    geometry: Optional[List[List[float]]] = None
    source: str = "haversine"
    route_notes: str
    city: str
    station_id: Optional[str] = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние «по дуге большого круга» в километрах."""
    r = 6371.0
    rad_lat1, rad_lat2 = math.radians(lat1), math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@router.get("/routing/stations", response_model=List[RoutingStation])
async def list_stations(
    city: str = Query(..., description="Идентификатор города"),
    session: AsyncSession = Depends(get_db),
) -> List[RoutingStation]:
    result = await session.execute(
        text(
            "SELECT id, name, COALESCE(district, '—') AS district, lat, lon "
            "FROM fire_stations WHERE city = :city AND lat IS NOT NULL AND lon IS NOT NULL "
            "ORDER BY id"
        ),
        {"city": city},
    )
    return [
        RoutingStation(
            id=row["id"],
            name=row["name"],
            district=row["district"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
        )
        for row in result.mappings().all()
    ]


@router.post("/routing/estimate", response_model=RouteEstimateResponse)
async def estimate_route(body: RouteEstimateRequest) -> RouteEstimateResponse:
    distance_km = _haversine_km(body.from_lat, body.from_lon, body.to_lat, body.to_lon)
    # Накидываем 30% к прямой — поправка на улицы (без OSRM)
    drive_km = distance_km * 1.3
    normal_min = (drive_km / _NORMAL_KMH) * 60
    emergency_min = (drive_km / _EMERGENCY_KMH) * 60
    return RouteEstimateResponse(
        normal_min=round(normal_min, 1),
        emergency_min=round(emergency_min, 1),
        savings_min=round(normal_min - emergency_min, 1),
        distance_km=round(drive_km, 1),
        geometry=None,
        source="haversine",
        route_notes="Оценка по прямой + 30% (без OSRM). Экстренный режим: выделенные полосы, проезд на красный.",
        city=body.city,
        station_id=body.station_id,
    )
