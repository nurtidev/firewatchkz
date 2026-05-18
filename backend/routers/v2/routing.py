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


# ---------------------------------------------------------------------------
# Blind zones — districts where avg emergency arrival exceeds a threshold.
# Presentation §2.5: "Автоматическая подсветка «слепых зон»."
# ---------------------------------------------------------------------------


class BlindDistrict(BaseModel):
    district: str
    lat: float
    lon: float
    total_buildings: int
    blind_buildings: int
    blind_pct: float
    avg_emergency_min: float
    max_emergency_min: float


class BlindZonesSummary(BaseModel):
    city: str
    threshold_min: float
    total_buildings: int
    blind_buildings: int
    blind_pct: float
    districts: List[BlindDistrict]


@router.get("/routing/blind-zones", response_model=BlindZonesSummary)
async def get_blind_zones(
    city: str = Query(..., description="Идентификатор города"),
    threshold_min: float = Query(
        10.0, ge=1.0, le=60.0, description="Норматив времени прибытия в минутах"
    ),
    session: AsyncSession = Depends(get_db),
) -> BlindZonesSummary:
    """Сводка районов, где среднее экстренное время прибытия превышает норматив.

    Считаем по каждому зданию: расстояние до ближайшей пожарной части
    (haversine + 30%), время в минутах при 60 км/ч (экстренный режим).
    Агрегируем по району.
    """

    # Все здания с координатами + район
    buildings_rows = await session.execute(
        text(
            """
            SELECT b.id,
                   ST_Y(b.centroid) AS lat,
                   ST_X(b.centroid) AS lon,
                   COALESCE(b.district, '—') AS district
            FROM buildings b
            WHERE b.city_id = :city AND b.centroid IS NOT NULL
            """
        ),
        {"city": city},
    )
    buildings = [dict(row) for row in buildings_rows.mappings().all()]

    # Все пожарные части города
    stations_rows = await session.execute(
        text(
            "SELECT id, lat, lon FROM fire_stations "
            "WHERE city = :city AND lat IS NOT NULL AND lon IS NOT NULL"
        ),
        {"city": city},
    )
    stations = [dict(row) for row in stations_rows.mappings().all()]

    if not stations or not buildings:
        return BlindZonesSummary(
            city=city,
            threshold_min=threshold_min,
            total_buildings=0,
            blind_buildings=0,
            blind_pct=0.0,
            districts=[],
        )

    # Агрегация по району
    district_stats: dict = {}
    for b in buildings:
        # ближайшая часть
        min_km = min(
            _haversine_km(float(b["lat"]), float(b["lon"]), float(s["lat"]), float(s["lon"]))
            for s in stations
        )
        emergency_min = (min_km * 1.3 / _EMERGENCY_KMH) * 60
        d = b["district"]
        stat = district_stats.setdefault(
            d,
            {
                "lat_sum": 0.0,
                "lon_sum": 0.0,
                "total": 0,
                "blind": 0,
                "time_sum": 0.0,
                "time_max": 0.0,
            },
        )
        stat["total"] += 1
        stat["lat_sum"] += float(b["lat"])
        stat["lon_sum"] += float(b["lon"])
        stat["time_sum"] += emergency_min
        if emergency_min > stat["time_max"]:
            stat["time_max"] = emergency_min
        if emergency_min > threshold_min:
            stat["blind"] += 1

    districts: List[BlindDistrict] = []
    total = 0
    total_blind = 0
    for name, stat in district_stats.items():
        n = stat["total"]
        total += n
        total_blind += stat["blind"]
        districts.append(
            BlindDistrict(
                district=name,
                lat=round(stat["lat_sum"] / n, 6),
                lon=round(stat["lon_sum"] / n, 6),
                total_buildings=n,
                blind_buildings=stat["blind"],
                blind_pct=round(stat["blind"] * 100.0 / n, 1),
                avg_emergency_min=round(stat["time_sum"] / n, 1),
                max_emergency_min=round(stat["time_max"], 1),
            )
        )

    districts.sort(key=lambda d: d.blind_pct, reverse=True)

    return BlindZonesSummary(
        city=city,
        threshold_min=threshold_min,
        total_buildings=total,
        blind_buildings=total_blind,
        blind_pct=round(total_blind * 100.0 / total, 1) if total else 0.0,
        districts=districts,
    )
