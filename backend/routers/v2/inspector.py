"""
routers/v2/inspector.py — Inspector endpoints with TSP-optimised route (H-8).

GET /api/v2/inspector?city=astana&top_n=50&min_risk=0.0
    Returns top-N high-risk buildings for the given city (latest risk score only).
    Auth: require_inspector_or_above

GET /api/v2/inspector/route?building_ids=["id1","id2",...]
    Accepts a JSON-array string of building IDs fetched from the first endpoint,
    returns a nearest-neighbour TSP-ordered route with waypoints, total distance
    and estimated travel time.
    Auth: require_inspector_or_above
"""
from __future__ import annotations

import json
import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_inspector_or_above

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two coordinates."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Risk level classifier
# ---------------------------------------------------------------------------


def classify_risk(score: float) -> str:
    """Return 'low', 'medium', or 'high' based on *score*."""
    if score < 0.5:
        return "low"
    if score <= 1.5:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Nearest-neighbour TSP
# ---------------------------------------------------------------------------


def nearest_neighbour_tsp(
    points: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Order *points* using a nearest-neighbour heuristic starting from the first
    point.  Each dict must have 'lat' and 'lon' keys.

    Returns a new list in visit order.
    """
    if not points:
        return []

    unvisited = list(points)
    ordered: List[Dict[str, Any]] = [unvisited.pop(0)]

    while unvisited:
        last = ordered[-1]
        best_idx = min(
            range(len(unvisited)),
            key=lambda i: haversine_km(
                float(last["lat"]), float(last["lon"]),
                float(unvisited[i]["lat"]), float(unvisited[i]["lon"]),
            ),
        )
        ordered.append(unvisited.pop(best_idx))

    return ordered


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class InspectorBuilding(BaseModel):
    building_id: str
    address: Optional[str]
    building_type: Optional[str]
    floors_above: Optional[int]
    lat: Optional[float]
    lon: Optional[float]
    final_score: float
    baseline_score: Optional[float]
    dynamic_modifier: Optional[float]
    risk_level: str


class InspectorFactor(BaseModel):
    matched: bool
    label: str


class InspectorAlert(BaseModel):
    district: str
    priority: str  # critical | high | medium | low
    matched_factors: int
    total_factors: int
    risk_score: float
    days_since_last_incident: Optional[int]
    avg_damage_tenge: float
    recommendation: str
    factors: List[InspectorFactor]


class Waypoint(BaseModel):
    building_id: str
    lat: Optional[float]
    lon: Optional[float]
    address: Optional[str]
    final_score: float


class RouteResponse(BaseModel):
    ordered_buildings: List[str]
    total_distance_km: float
    estimated_time_min: float
    waypoints: List[Waypoint]


# ---------------------------------------------------------------------------
# Endpoint 1 — list high-risk buildings
# ---------------------------------------------------------------------------


_PRIORITY_RECOMMENDATIONS = {
    "critical": "Экстренная проверка в течение 24 часов. Ситуация требует немедленного вмешательства руководства.",
    "high":     "Плановая проверка в течение недели. Согласовать график обходов с инспекторами.",
    "medium":   "Контрольная проверка в ближайший месяц. Обратить внимание на типовые причины пожаров.",
    "low":      "Ситуация под контролем — продолжать стандартный мониторинг и плановые обходы.",
}


def _priority_from_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


@router.get("/inspector/alerts", response_model=List[InspectorAlert])
async def list_inspector_alerts(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    session: AsyncSession = Depends(get_db),
) -> List[InspectorAlert]:
    """Алерты по районам (агрегат из таблицы incidents).

    Считаем risk_score district-level, последний пожар, средний ущерб.
    Используется на странице /dashboard/inspector в фронте.
    Auth не требуется — данные обезличенные, ровно как district stats.
    """
    # Таблица incidents в v2 не имеет колонки city — параметр оставляем для будущего
    # multi-city (нужна миграция), сейчас просто агрегируем по district.
    _ = city  # silence unused warning
    result = await session.execute(
        text(
            """
            WITH base AS (
                SELECT
                    district,
                    COUNT(*) FILTER (WHERE occurred_at >= now() - interval '365 days') AS inc_last_12m,
                    COUNT(*) AS total_inc,
                    AVG(damage_tenge) AS avg_damage,
                    MAX(occurred_at) AS last_occurred_at
                FROM incidents
                WHERE district IS NOT NULL AND district != ''
                GROUP BY district
            ),
            maxvals AS (
                SELECT MAX(inc_last_12m) AS mx_inc, MAX(avg_damage) AS mx_dmg FROM base
            )
            SELECT
                b.district,
                b.total_inc,
                b.inc_last_12m,
                COALESCE(b.avg_damage, 0) AS avg_damage,
                b.last_occurred_at,
                LEAST(100, ROUND(
                    COALESCE(b.inc_last_12m::float / NULLIF(m.mx_inc,0), 0) * 70 +
                    COALESCE(b.avg_damage / NULLIF(m.mx_dmg,0), 0) * 30
                )) AS risk_score
            FROM base b, maxvals m
            ORDER BY risk_score DESC
            """
        ),
    )

    alerts: List[InspectorAlert] = []
    for row in result.mappings().all():
        score = float(row["risk_score"] or 0)
        priority = _priority_from_score(score)
        avg_damage = float(row["avg_damage"] or 0)
        inc_12m = int(row["inc_last_12m"] or 0)

        # 5 простых факторов, "matched" если выполнено условие
        factors = [
            InspectorFactor(matched=inc_12m >= 5,        label="Более 5 пожаров за последний год"),
            InspectorFactor(matched=avg_damage >= 1e6,   label="Средний ущерб > 1 млн ₸"),
            InspectorFactor(matched=score >= 60,         label="Высокий итоговый риск (≥60)"),
            InspectorFactor(matched=int(row["total_inc"] or 0) >= 10, label="Накопленная история ≥10 пожаров"),
            InspectorFactor(matched=row["last_occurred_at"] is not None, label="Есть инциденты в районе"),
        ]
        matched = sum(1 for f in factors if f.matched)

        days_since = None
        if row["last_occurred_at"]:
            delta = datetime.now(timezone.utc) - row["last_occurred_at"]
            days_since = max(0, delta.days)

        alerts.append(
            InspectorAlert(
                district=row["district"],
                priority=priority,
                matched_factors=matched,
                total_factors=len(factors),
                risk_score=score,
                days_since_last_incident=days_since,
                avg_damage_tenge=avg_damage,
                recommendation=_PRIORITY_RECOMMENDATIONS[priority],
                factors=factors,
            )
        )
    return alerts


@router.get("/inspector", response_model=List[InspectorBuilding])
async def list_inspector_buildings(
    city: str = Query(..., description="Идентификатор города (например, astana)"),
    top_n: int = Query(50, ge=1, le=200, description="Максимальное число зданий"),
    min_risk: float = Query(0.0, ge=0.0, description="Минимальный балл риска"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> List[InspectorBuilding]:
    """Return top-N buildings ordered by risk score (latest scores only)."""

    result = await session.execute(
        text(
            """
            SELECT
                b.id,
                b.address,
                b.building_type,
                b.floors_above,
                ST_Y(b.centroid) AS lat,
                ST_X(b.centroid) AS lon,
                rs.final_score,
                rs.baseline_score,
                rs.dynamic_modifier,
                rs.shap_values,
                rs.score_date
            FROM risk_scores rs
            JOIN buildings b ON rs.building_id = b.id
            WHERE rs.city_id = :city
              AND rs.score_date = (
                  SELECT MAX(score_date) FROM risk_scores WHERE city_id = :city
              )
              AND rs.final_score >= :min_risk
            ORDER BY rs.final_score DESC
            LIMIT :top_n
            """
        ),
        {"city": city, "min_risk": min_risk, "top_n": top_n},
    )
    rows = result.mappings().all()

    buildings: List[InspectorBuilding] = []
    for row in rows:
        final_score = float(row["final_score"])
        buildings.append(
            InspectorBuilding(
                building_id=str(row["id"]),
                address=row["address"],
                building_type=row["building_type"],
                floors_above=row["floors_above"],
                lat=float(row["lat"]) if row["lat"] is not None else None,
                lon=float(row["lon"]) if row["lon"] is not None else None,
                final_score=final_score,
                baseline_score=float(row["baseline_score"]) if row["baseline_score"] is not None else None,
                dynamic_modifier=float(row["dynamic_modifier"]) if row["dynamic_modifier"] is not None else None,
                risk_level=classify_risk(final_score),
            )
        )

    return buildings


# ---------------------------------------------------------------------------
# Endpoint 2 — TSP-optimised inspection route
# ---------------------------------------------------------------------------


@router.get("/inspector/route", response_model=RouteResponse)
async def get_inspector_route(
    building_ids: str = Query(
        ...,
        description='JSON-массив идентификаторов зданий, например: ["id1","id2"]',
    ),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> RouteResponse:
    """
    Accept a JSON array of building IDs and return a nearest-neighbour TSP
    ordered route with total distance (km) and estimated travel time (min).
    """
    # Parse building_ids
    try:
        ids: List[str] = json.loads(building_ids)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="building_ids должен быть JSON-массивом строк",
        )

    if not isinstance(ids, list):
        raise HTTPException(
            status_code=422,
            detail="building_ids должен быть JSON-массивом строк",
        )

    # Reject empty list
    if len(ids) == 0:
        raise HTTPException(
            status_code=422,
            detail="building_ids не может быть пустым массивом",
        )

    # Fetch building coordinates and latest risk scores from DB
    result = await session.execute(
        text(
            """
            SELECT
                b.id,
                b.address,
                ST_Y(b.centroid) AS lat,
                ST_X(b.centroid) AS lon,
                rs.final_score
            FROM buildings b
            LEFT JOIN LATERAL (
                SELECT final_score
                FROM risk_scores rs2
                WHERE rs2.building_id = b.id
                ORDER BY rs2.score_date DESC
                LIMIT 1
            ) rs ON TRUE
            WHERE b.id = ANY(:ids)
            """
        ),
        {"ids": ids},
    )
    rows = result.mappings().all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Ни одно из указанных зданий не найдено в базе данных",
        )

    # Build point dicts preserving the user-supplied order where possible
    id_to_row: Dict[str, Any] = {str(row["id"]): row for row in rows}

    points: List[Dict[str, Any]] = []
    for bid in ids:
        if bid in id_to_row:
            row = id_to_row[bid]
            points.append(
                {
                    "building_id": bid,
                    "lat": float(row["lat"]) if row["lat"] is not None else 0.0,
                    "lon": float(row["lon"]) if row["lon"] is not None else 0.0,
                    "address": row["address"],
                    "final_score": float(row["final_score"]) if row["final_score"] is not None else 0.0,
                }
            )

    if not points:
        raise HTTPException(
            status_code=404,
            detail="Ни одно из указанных зданий не найдено в базе данных",
        )

    # Run nearest-neighbour TSP
    ordered = nearest_neighbour_tsp(points)

    # Compute total distance
    total_km = 0.0
    for i in range(len(ordered) - 1):
        total_km += haversine_km(
            ordered[i]["lat"], ordered[i]["lon"],
            ordered[i + 1]["lat"], ordered[i + 1]["lon"],
        )

    # Estimated time at average 30 km/h city speed
    estimated_min = (total_km / 30.0) * 60.0

    return RouteResponse(
        ordered_buildings=[p["building_id"] for p in ordered],
        total_distance_km=round(total_km, 3),
        estimated_time_min=round(estimated_min, 2),
        waypoints=[
            Waypoint(
                building_id=p["building_id"],
                lat=p["lat"],
                lon=p["lon"],
                address=p["address"],
                final_score=p["final_score"],
            )
            for p in ordered
        ],
    )
